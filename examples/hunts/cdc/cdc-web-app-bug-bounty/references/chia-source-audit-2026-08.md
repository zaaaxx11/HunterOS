# Chia Network Source-Code Audit Findings (2026-08) — clvm_rs, chiavdf, chiapos, chia_rs, chia-blockchain-gui

Chia H1 scope: vault.chiatest.net / vault.chia.net (web), chia-blockchain, clvm_rs, chiavdf, chiapos, chia_rs, chia-blockchain-gui, chia-signer (iOS). Cloned to /tmp/chia/{clvm-src,vdf-src,pos-src,rs-src,gui-src}.

## clvm_rs — CLVM execution engine (Rust)
- VM core is **solid**: safe Rust, monotonic cost (u64 checked every op), quota-enforced allocator (MAX_NUM_ATOMS/PAIRS 62.5M, heap ≤ u32::MAX), no `unsafe`.
- **Cost bypass via `wrapping_mul`** — `src/more_ops.rs:522` legacy cost model: unknown opcode + crafted multiplier → cost wraps to 0 → unbounded execution. Fix: `checked_mul`.
- **VM panic on pair-as-atom** — `src/allocator.rs:1034,1051,1084,1102,975` — 5 `panic!` sites reachable via 10+ operators from malformed CLVM → full node abort. `atom_eq()` on Pair → `panic!("atom_eq() called on pair")`.
- **Dialect divergence** — `src/runtime_dialect.rs:73-75` `softfork_extension()` always returns Default vs `src/chia_dialect.rs:295-319` handles ext 0/1/PreHardFork → same program different ops/cost on different nodes = **chain split**.
- **BLS validation bypass** — `RELAXED_BLS` flag → `g1_negate`/`g2_negate` return invalid curve points uncached → forged aggregate sigs (`src/bls_ops.rs:138,147,263,272`).
- **Memory exhaustion via ghost_heap** — nested softfork guards → `restore_checkpoint` overwrites `ghost_heap` with stale value → OOM bypass (`src/allocator.rs:485-499` + `run_program.rs:486-519`).
- Entry points: `src/serde/de.rs:44` (node_from_bytes), `src/serde_2026/de.rs:131,144` (2026 format), `src/run_program.rs:597`.
- Report: `/home/ubuntu/exploit_chains.md`.

## chiavdf — VDF for Timelords (C++ + Rust FFI)
**KEY INSIGHT: shipped binary (1.1.14 wheel) is UNPATCHED while source HEAD has fixes. Check the deployed binary, not just source.**
- **b0 proof malleability → CHAIN SPLIT (Critical, LIVE)**: `verify_n_wesolowski` uses `strict=false` in `DeserializeForm` — accepts inflated b0 encodings (±4, ±8 on byte 199). Two byte-distinct proof blobs both verify. Fix exists in HEAD (`strict=true` + `|b|≤a` check) but **never wired into the verify path**.
- **Oversized discriminant → SIGSEGV (Critical, reproduced)**: `create_discriminant(seed, 1032)` accepted by shipped wheel; `SerializeForm` ignores `bqfc_serialize` -1 error → garbage; `prove()` crashes SIGSEGV (exit -11). Rust `unsafe` wrapper can't catch SIGSEGV → node crash/RCE surface.
- **HashPrime infinite loop → CPU DoS (High, LIVE)**: crafted input loops forever.
- **Signed integer overflow in `Reducer.h::calc_uvwx` (UBSAN confirmed)**: lines 214 (`c<<1` negative shift), 223/225/228/230 (`c*s`, `s*v`, `s*x` multiply overflow), 162 (`-r` negation of INT64_MIN) — reachable from untrusted proof via `VerifyWesoSegment → FastPowFormNucomp → PulmarkReducer::reduce`. Wrong reduction → potential proof forgery.
- **FFI OOB read**: `x_s` length never passed through Rust FFI (`c_wrapper.h:20` has no x_s_size); C++ reads 100 bytes unconditionally → heap over-read if caller passes shorter.
- Report: `/home/ubuntu/CHIAVDF_EXPLOIT_CHAINS.md`, `/home/ubuntu/chiavdf_proof_chain.bin` (malleable proof).

## chiapos — Proof of Space plotter (C++)
- **Division by zero in DiskProver ctor** — `prover_disk.hpp:409` `c2_entries = (p10-p9)/c2_size`; plot header with k=0 → `c2_size=0` → SIGFPE. **No k validation in constructor** (accepts 0..255; verifier guards 18-50 but prover does not). Unauthorized DoS on plot load.
- **Division by zero in CompareProofBits** — `verifier.hpp:148` `size = left.GetSize()/k` with k=0 (GetQualityString bypasses ValidateProof's k≥18).
- **ChaCha8 RNG bug → 256× space amplification** — `calculate_bucket.hpp:88-92` F1 key uses only 31/32 bytes of plot ID (`memcpy(enc_key+1, orig_key, 31)`) → byte 31 ignored → attacker chooses plot ID with 256× farming advantage.
- **kRValues[7] only 6 values** — `pos_constants.hpp:75` → `kRValues[6]=0.0` → ANS infinite loop/UB.
- **Integer overflow** — `calculate_bucket.hpp:260` `end_bit = k+6+k*4` wraps at k=50 (256→0).
- OOB read: `validate_proof` memcpy 32B challenge without length check (python binding enforces 32B only on `get_qualities_for_challenge`, not `validate_proof`/`get_full_proof`).
- Report: `/home/ubuntu/chiapos_exploit_chains.md`, crashes at `/home/ubuntu/fuzzchop/crashes/`.

## chia_rs — Rust consensus protocol
- **SpendBundle double-spend (Critical)** — `crates/chia-protocol/src/spend_bundle.rs:25-36` `aggregate()` does NOT deduplicate coin_spends; double-spend same coin in aggregated bundle → aggregate BLS sig verifies → unauthorized spend accepted (`spendbundle_validation.rs:45-51` only verifies aggregate sig).
- **Panic on untrusted input (DoS)** — `fullblock.rs:72` `panic!("version field must be 0 or 1")` (version=255 via streamable macro pub fields); `proof_of_space.rs:90,111,156,200,255,339` multiple `panic!` on invalid version/missing pool key.
- **Weight proof overflow → chain split** — `u128::MAX` total_iters + `u8::MAX` num_blocks_overflow → weight wraps → attacker chain accepted as heaviest.
- **VDF proof no validation** — `vdf.rs:14-18` witness_type/witness length unchecked; `SubSlotData` all Option → None VDF proofs skip sampling.
- **Weight proof entirely unvalidated in Rust** — validation lives in Python; critical gap if called from Rust.
- Network entry: `Streamable::parse::<false>` enforces canonical encoding; trust boundary map at `/home/ubuntu/trust_boundary_graph.md`.

## chia-blockchain-gui — Electron (TypeScript)
- webPreferences **solid**: nodeIntegration=false, contextIsolation=true, sandbox=true, webSecurity=true (main.tsx:770-775, openReactDialog.tsx:280-285).
- **SSRF via FETCH_POOL_INFO** — `packages/gui/src/electron/main.tsx:515`: `ipcMainHandle(AppAPI.FETCH_POOL_INFO, async (poolUrl) => fetchJSON(${poolUrl}/pool_info))` — **no isValidURL check** (contrast FETCH_TEXT_RESPONSE at :474 which validates). poolUrl from user input (join pool flow). Other handlers: DOWNLOAD, START_MULTIPLE_DOWNLOAD, SHOW_OPEN_FILE_DIALOG_AND_READ, GET_CONFIG — all ipcMainHandle without sender validation (`ipcMainHandle.ts:4`).
- Path traversal via `cache://` protocol: **blocked** — `sanitizeFilename` uses `sanitize-filename` lib + strict equality (throws if changed).
- Dapp commands: whitelist + type validation (`parseDappParams.ts`), openExternal validated via `isValidURL` (https-only + ipfs gateway form).
- Note: `chia://` scheme NOT registered as privileged (only CACHE_PROTOCOL). open-url/open-file events forwarded to renderer.

## chia-signer iOS (bundle net.chia.ios-signer v1.2.1)
- Hardware wallet (Secure Enclave), local signing only. Backend = same `api.vault.chia.net` GraphQL.
- Signer-specific GraphQL: `signatureRequest(id)`, `appKeysSignatureRequests`, `signer(id)`, `signSignatureRequest(input:{message:Bytea!, publicKey:Bytea!, ...})` — **all permission-gated** (`signer.read`). ORGANIZATION_ADMIN session insufficient. Secure by design; low-ROI target.

## Chia vault web (api.vault.chia.net — production = same codebase as chiatest)
- better-auth cookie auth (`__Secure-better_auth_session=<token>.<base64url_sig>`), NOT Authorization header.
- Full signup chain proven on PROD: temp mail → OTP → userSignup → CDP WebAuthn (enableUI:false + Page.bringToFront + window.focus() for headless) → verifyPasskeyAssign → session cookie → ORGANIZATION_ADMIN.
- BFLA updateOrganization: rename org + sessionDuration 3600 on PRODUCTION (proven).
- Feature flag IDs: `FeatureFlag_<NAME>` (not UUID); plans query leaks all plans + flags unauthenticated.
- Auto-ORGANIZATION_ADMIN on signup = **by-design** (user creates own org) — do NOT report as vuln.
- Report: /tmp/chia/CHIA_SECURITY_REPORT.md (EN+ID).
