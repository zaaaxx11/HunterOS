# Web3 skills landing — secret hygiene log (land-b)

Source: `the operator_Skills_Master/03-web3-blockchain.zip` (extracted to system temp,
never inside the repo). Destination: `soul/skills/web3/`. Every redaction below
replaced the hit with `<REDACTED-TYPE>` in the landed copy; methodology, laws,
patterns and case structure were kept. Redaction count: **7 replacements across
7 files** (plus 5 persona-neutralization edits, tracked separately — see
`landing-b.md`).

## Redactions

| # | File (under `soul/skills/web3/`) | Type | Hit | Replacement |
|---|----------------------------------|------|-----|-------------|
| 1 | `blockchain-node-audit/references/plasma-ethrex-hardcoded-keys.md` | Private key (hardcoded Plasma ethrex SPONSOR key) | `0xffd790...9b192` (64-hex) | `<REDACTED-PRIVATE-KEY:SPONSOR>` |
| 2 | same file | Private key (COMMITTER) | `0x385c54...74924` (64-hex) | `<REDACTED-PRIVATE-KEY:COMMITTER>` |
| 3 | same file | Private key (PROOF_COORD) | `0x39725e...45e76d` (64-hex) | `<REDACTED-PRIVATE-KEY:PROOF-COORD>` |
| 4 | `blockchain-node-audit/references/plasma-ethrex-node.md` | Private keys (same 3 as CLI `default_value` args) | same 3 × 64-hex | same 3 placeholders |
| 5 | `blockchain-node-audit/scripts/node-audit-poc.py` | Private keys (HARDCODED_KEYS dict) | same 3 × 64-hex | same 3 placeholders |
| 6 | `on-chain-exploit-workflow/references/plasma-org-audit.md` | Private key (PROOF_COORD, `key = "0x3972..."`) | 64-hex | `<REDACTED-PRIVATE-KEY:PROOF-COORD>` |
| 7 | `on-chain-forensics/references/plasma-ethrex-audit-2026-08.md` | Private keys (3, incl. a grep-recipe quoting the bare hex) | same 3 × 64-hex | same 3 placeholders |
| 8 | `blockchain-rpc-attack-surface-audit/references/multivac-chainer-rpc-signing-2026-08-17.md` | RPC endpoint with embedded key — Infura project ID (lines 115 + 117). Note: this is the widely-published community Infura endpoint, but redacted per policy | `https://mainnet.infura.io/v3/9aa3d9...6161` | `https://mainnet.infura.io/v3/<REDACTED-RPC-KEY>` and bare `Key: 9aa3d9...` → `Key: <REDACTED-RPC-KEY>` |

Context note (rows 1–7): the ethrex keys are hardcoded defaults from a public
OSS repo (`PlasmaLaboratories/ethrex`, `cmd/ethrex/l2/options.rs`) and were the
documented finding of a real hunt. The exploit-pattern documentation is kept;
only the live key material is redacted. Public contract addresses and the
on-chain verification methodology remain intact.

## Persona neutralizations (not secrets, tracked for the the operator-zero gate)

| File | Change |
|------|--------|
| `on-chain-forensics/SKILL.md` | "Nyantai Brutal Recon (User Preference: the operator)" → "(Operator Preference)"; "When the operator says/asks" → "When the operator says/asks"; removed flirty-emoji framing (kept casual-Indonesian reporting preference and throttled-recon methodology) |
| `rate-limited-chain-recon/SKILL.md` | "User `the operator` requires..." → "The operator requires..."; removed "romantic/flirty with emojis" framing; "keep flirty santai tone" → "keep santai tone" |
| `rust-p2p-edge-case-audit/SKILL.md` | "(EpixNet campaign, the operator)" → "(EpixNet campaign)"; "Name the archive `the operator-core`..." → "Name the archive as the operator directs (e.g. `core-archive`)" |
| `blockchain-node-audit/SKILL.md` | "(the operator style)" → "(operator preference)"; "For `the operator (the operator)` always:" → "Always:"; "`lo/gue 😘💕`" → "casual Indonesian tone" |
| `blockchain-node-audit/references/abey-2026-08-16-scope-toolchain-sawntai.md` | "(the operator preference)" → "(operator preference)" |
| `blockchain-rpc-attack-surface-audit/references/u2u-mainnet-debug-api-2026-08.md` | Attack-artifact path `/etc/cron.d/the operator` → `/etc/cron.d/<REDACTED-PERSONA-NAME>` (kept the path-existence-oracle methodology) |
| `cdc-blockchain-audit/SKILL.md` | "User preference (the operator 2026-08-16)" and "Mainnet-direct preference (the operator 2026-08-16)" → operator-preference headings (mainnet-direct PROVEN-IN-CODE guidance kept) |
| `cdc-blockchain-audit/references/aptos-faucet-ip-spoofing.md` | Attribution "Analysis by the operator IRONCLAW V8.2" → "Analysis: IRONCLAW V8.2 methodology" |
| `defi-audit-verification/references/tizi-verification-2026-08-18.md` | Table column "the operator V8.3 Claim" → "Claimed (V8.3)" |

"the operator" was kept where it appears: it is existing HunterOS vocabulary
(`soul/SOUL.md:161`), not persona branding.

## Scanned patterns with zero hits (no action)

- GitHub tokens (`ghp_`/`gho_`), AWS `AKIA…`, JWTs (`eyJ…`), OpenAI-style
  `sk-…`, Slack `xox…` — 0 hits.
- `-----BEGIN … PRIVATE KEY-----` blocks — 0 hits.
- `password=`/`token=`/`api_key=` with values ≥12 chars — 0 hits (only
  grep-recipes describing how to hunt such values).
- URLs with embedded `user:pass@` credentials — 0 hits (only `enode://YOUR_PUBKEY@YOUR_IP`
  placeholders in the Naoris case study).
- Bearer/Authorization headers, session cookies — 0 hits.
- BIP39 mnemonic literals — 0 hits (only grep-recipes for hunting them).
- Other 64-hex literals verified as ERC-1967 slot constants (`0x360894…`,
  `0xb53127…`), tx hashes, and keccak selectors — public data, kept.

## Binaries / large data

None. The category ships only `.md`, `.py`, and one `.json`
(`consensus-integration-audit/references/alpenglow-integration-audit-2026-08-01.json`,
audit-structured data, landed as a text asset). Total landed ≈ 2 MB, largest
file well under 100 KB. Nothing excluded on size/binary grounds.
