# 375.ai Rewards Distributor — CDC Audit 2026-08-12 (No Pre-Auth RCE)

## Target
- **Repo:** 375-ai/program-library (single program `rewards-distributor`)
- **Program ID:** `2dUMVSQkKUu1YTUrt5xW1QKrYPaCS` (Anchor 0.29.0, declare_id! lib.rs:11)
- **Web:** www.375.ai — Webflow static (cdn.prod.website-files.com, webfont, jquery, gsap, recaptcha/turnstile). No api/edge subdomain, no SSR/RSC/Server Actions.
- **Scope:** web2 + web3, hiraukan audit files (user: "hiraukan tentang sesuatu repo/file yang berbau audit")

## Trust Graph
```
RewardsAccount (INIT_SPACE): manager, proposed_manager, agent, current_epoch_nr, current_approved_epoch, is_paused, withdrawal_period_secs (immutable)
EpochAccount (INIT_SPACE): epoch_nr, is_approved, approved_at, hash[32], bump u8, mint Pubkey, total_amount_claimed u64, num_nodes_claimed u64
ClaimStatus (LEN 1+32+8+8): is_claimed bool, receiver Pubkey, claimed_at i64, amount u64 — PDA [b"ClaimStatus", rewards.key, index LE, epoch.key] bump, payer=receiver
Epoch PDA: [b"EpochAccount", rewards.key, epoch_nr LE] bump
```
Roles: manager (has_one) → propose_manager, change_agent, approve_epoch, pause, unpause, withdraw_unclaimed; agent (has_one) → add_epoch, correct_epoch (!is_approved); anyone (receiver signer) → claim (needs valid merkle proof + is_approved + mint match).

## CDC Theories
| # | Theory | Checks | Verdict |
|---|---|---|---|
| A | Logic bypass / PrivEsc | has_one, is_paused, propose→accept race, change_agent, add_epoch mint swap | BLOCKED — all gates correct |
| B | Merkle + Token Account Confusion | address=from.owner, init_if_needed ATA, mint vs from.mint, amount inflation | BLOCKED as theft — merkle binds amount/receiver; InvalidProof holds |
| C | Web2 RCE | store.ts path.join, keyStore readFileSync, merkle-tree combinedHash(undefined), Webflow API leaks | BLOCKED — static site, no sink |

## Chainer Attempts (Adversarially Falsified)
1. `[Init attacker RewardsAccount_A] → [claim(rewards=A, epoch=V, from=V_vault ATA, to=attacker ATA, amount=1e9, proof=[])] → [address=from.owner passes (V PDA)] → [merkle_proof::verify([] , V_root, keccak(0‖attacker‖1e9)) → false → InvalidProof]` — STALL at leaf verify claim.rs:106-114.
2. Single-leaf edge: if tree had 1 leaf attacker could set proof=[] and leaf==root. Blocked: agent creates root; attacker never controls victim root pre-auth.
3. Bump DoS chain (proven): `[Agent add_epoch(bump=255 wrong)] → [store bump 255] → [claim/withdraw with_signer(&[255]) → InvalidSeeds → vault locked]` — DOS not theft.

## Findings (line-accurate)
1. **MED — Weak PDA binding claim.rs:18-21** `#[account(mut, address = from.owner)] pub epoch_account` vs approve/withdraw seeds derivation. Impact: ClaimStatus PDA reuse across different RewardsAccount for same index+epoch.key; no theft (merkle still checks) but inconsistency. Also withdraw_unclaimed.rs:52-67 missing `require!(epoch.mint == mint_account.key())`.
2. **MED — Unsafe bump add_epoch.rs:43,64** `bump: u8` user-supplied → `current_epoch_account.bump = bump` unchecked canonical. claim.rs:131-138 / withdraw_unclaimed.rs:122-128 sign with stored bump → wrong → permanent lock. Fix: `ctx.bumps.current_epoch_account` or `findProgramAddress` validation.
3. **LOW — Unchecked arithmetic claim.rs:154-155** `total_amount_claimed + amount` `num_nodes_claimed +=1` without checked_add. Merkle-bound but still wrap risk.
4. **LOW — Secret leak** `src/config/keys/payer.json` `<redacted>`, `distributor.json` `<redacted>`, `payer_pub.json` `56soKhmh…`, `distributor_pub.json` `HBSLiE4…`, `program_devnet_pub.json` `2dUMVS…`. Devnet but committed. Fix: git rm + gitignore + rotate.

## Merkle Details
- Off-chain: BalanceTree.toNode(index, account, amount) = keccak256(LE64(index)‖account 32‖LE64(amount)) balance-tree.ts:34-40; MerkleTree sorts leaves, dedup, combinedHash = keccak(sort(first,second)) merkle-tree.ts:89-99.
- On-chain: merkle_proof.rs:5-19 sorted keccak verify; claim.rs:106-110 leaf = keccak(index‖receiver‖amount). Amount inflation without valid proof impossible.

## Repro / Validation
```bash
# fetch
curl -L https://codeload.github.com/375-ai/program-library/zip/refs/heads/main -o /tmp/pl.zip && unzip -q /tmp/pl.zip -d /tmp
# audit fails vector
# claim with attacker rewards + victim epoch + 1e9 amount → InvalidProof (0x1770)
# bump DoS: add_epoch with bump 255 → claim → Privilege Escalation
```
Web check: `curl -s https://www.375.ai/ | grep -oE 'https://[^"]+'` — only webflow/CDN, no api. `git: remote-https is not a git command` workaround: curl zip not git clone.

## Mitigations
- claim: replace `address=from.owner` with `seeds=[b"EpochAccount", rewards_account.key(), epoch_nr] bump` + `associated_token::mint=mint_account` + `authority=epoch_account` checks
- add_epoch: drop `bump` param, use `ctx.bumps`
- claim arithmetic: `checked_add`
- withdraw: add mint check
- keys: remove committed JSON, env var

## Lesson
Anchor PDA anti-pattern: user-supplied bump + `address=owner` weak binding. Always canonical bump. Webflow static = no RCE — detect thin surface early, pivot to on-chain strategy.
