# Governance Re-Read Signal (2026-08-11) (cut from rate-limited-chain-recon SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/web3/rate-limited-chain-recon/SKILL.md` during the S2b-2 content pass. The Sonic-FT / Gimo / Naoris case refs live in `examples/hunts/web3/rate-limited-chain-recon/references/`.

---

## Governance Re-Read Signal (2026-08-11)

When user says `coba kamu baca ulang governance, cari sesuatu celah` after a first pass already reported off-by-one/UUPS — do a line-by-line second pass focused on dead-code/trust assumptions. This session found 4 extra bugs missed first time:
1. `globalDelegators` never iterated in `castVote` (dead weight)
2. `IStaking` external CALL in loop without `nonReentrant`/`staticcall` (staking proxy upgrade → reenter)
3. `removeCancelledProposalData` leaves ghost weights + singleton lock
4. `p.highestWeight` vs `proposalHighestWeight` desync on Tie
Encode as checklist: always check global vs proposal delegator sets, reentrancy on view CALLs in voting loops, and singleton cleanup booleans.
