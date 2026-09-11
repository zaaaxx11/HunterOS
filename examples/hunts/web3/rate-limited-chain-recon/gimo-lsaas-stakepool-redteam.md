# LSaaS StakePool Red-Team Pattern (0G Gimo 2026-08-12) (cut from rate-limited-chain-recon SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/web3/rate-limited-chain-recon/SKILL.md` during the S2b-2 content pass. The Sonic-FT / Gimo / Naoris case refs live in `examples/hunts/web3/rate-limited-chain-recon/references/`.

---

## LSaaS StakePool Red-Team Pattern (0G Gimo 2026-08-12)

Reuse for any LSaaS/StakePool on rate-limited L2 (0G, Sonic, etc.) when task mentions `Cr=(Qstk-...)`, `st0G rate`, `Era`, `relay`, `proxy upgrade takeover`:

1. **Live view sweep** — `cast call` every `cast selectors` result (59 at Gimo) + 0.6s 4byte.directory lookup; map slots via `cast storage $PROXY {0..40}` and ERC1967 `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc` → impl, `slot0 & 0x...` owner check (`SLOAD 0x00 >>160 == CALLER` / `0x010000 DIV AND`).
2. **Decompile offline** — `cast code $IMPL > /tmp/impl.hex` → `cast disassemble $(cat /tmp/impl.hex)` → PUSH4 `0x63` scan for fork selectors when 4byte unknown; build `selector→JUMPDEST` map (Gimo: stake `0x46f45b8d→0x0599`, unstake `0x2e17de78→0x04cb`, withdraw `0x3ccfd60b→0x054e`, upgrade `0x3659cfe6→0x0518`, relay `0x7b207727→0x0741`). Follow `PUSH2 <dest> JUMP` chains to internal handlers (`0x1360` stake logic, `0x0e4a` unstake, `0x1c4e` withdraw, `0x1d47` relay); grep `CALLVALUE`/`SELFBALANCE @0x363f`/`GAS CALL @0x36c5`/`SLOAD 0x05 (rate)`/`SLOAD 0x4910fdfa… (reentrancy guard)` to locate mint/reentrancy/balance checks.
3. **Rate inflation sim** — `Cr=(Qstk-Qred+Qrew*(1-Rcom))/(M-N)` where `M-N = st0G.totalSupply` (check `st0G 0x18160ddd` live). Python harness: `calc_cr()` then donation spike calc (balance-based `Qstk=address(this).balance` vs stored `SLOAD slot` — Gimo uses stored → safe; demonstrate dust if `M` small). If `rateChangeLimit()==0` → no cap (`GT limit` bypass), relay can set arbitrary rate → mint cheap → inflate → withdraw.
4. **Era/relay/upgrade leads** — `currentEra 0x973628f6` + `unbondingDuration 0xccf6802a` (Gimo 329+3=332); `keccak(CALLER.0x03)` for `isRelay` mapping `0x0b/0x77` vs owner slot0 bypass; enumerate all 59 selectors as attacker `cast call --from 0x111…` classify `0x2af07d20 OwnableUnauthorized` vs `0xfd8f8078 NotRelay` vs success; `upgradeTo 0x3659cfe6` vs `upgradeToAndCall 0x4f1ef286` auth delta + `proxiableUUID 0x52d1902d` EIP-1822 check at `0x2bce/0x3239`; check `Upgraded(address)` logs in 7M chunks (Gimo: 5065775→25708823) + timelock/pendingOwner.
5. **Reentrancy harness** — fork `anvil --fork-url https://evmrpc.0g.ai --fork-block-number <live>` + attacker `receive(){ withdraw(); }` against `0x3ccfd60b SELFBALANCE→CALL`; test `stake(string)` missing `nonReentrant` if st0G is ERC777.

See `examples/hunts/web3/rate-limited-chain-recon/references/gimo-stakepool-redteam-2026-08-12.md` for full 0x0599/0x363f disasm excerpts + python `calc_cr` template.
