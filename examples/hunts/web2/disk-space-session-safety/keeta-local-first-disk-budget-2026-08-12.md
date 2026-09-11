# Keeta Local-First Disk Budget — Prove Without Burning 20G (2026-08-12)

## Signals
- `Local dulu deh, biar ga kebuang sia sia dana ku, cek dulu disknya biar ga OOM nnti` — operator explicitly asks to stay local and check disk first.
- `Oke gas dev` (chain dev branch before local check) followed by retraction to `Local dulu deh` — shows economy pivot after seeing mainnet `Internal error`.

## Host Facts (this VPS)
- `/dev/vda1 20G` (`/` 20G, `devtmpfs 4.0M`, `tmpfs 1.8G`), `Mem 3.6G` (`available 2.1G`), `swap 0B` — 20G is tight for Rust + Node.
- Before cleanup: `909M` free (`96%` used) — `cargo` fails:
  ```
  ar: /tmp/poc_dev/target/debug/build/aws-lc-sys-.../out/libaws_lc_0_44_0_crypto.a: error reading ...-bcm.o: No space left on device
  error occurred in cc-rs: command did not execute successfully (status code exit status: 1)
  cargo:rerun-if-env-changed=AR ... cargo:rerun-if-env-changed=ARFLAGS ...
  ```
  Repeats ~15x same env vars when OOM.
- After `rm -rf /tmp/poc_dev/target /tmp/poc_fund/target /tmp/poc_publish_main/target /tmp/keeta_src/node-rs-main/target ~/.cargo/registry/cache` → `2.5G` free (`88%` used) — safe.
- `/tmp` leaders pre-cleanup: `1.6G poc_dev` (the culprit), `40M keeta_src`, `7.8M keeta_zips` (8 zips: node-rs 883K, asn1 125K, explorer 444K, keetanet-client 4.6M, anchor-rs 699K/anchor 789K, ledger-js-sdk 78K, ledger-device 115K, swift-client 199K), `9.2M noise-xyz-brane-af9a276` etc.

## What Local Harness Would Cost
- `keetanetwork-utils/node-harness` (`package.json`: `@keetanetwork/keetanet-node 0.18.2`, `typia 9.3.1`, `typescript 5.6.3`, engines `node >=20`, scripts `build: tsc`) needs `npm install ~300-500M` + `cargo test --test e2e` target `3-4G` (aws-lc-sys alone ~1G). On `20G - 2.5G free` this = re-OOM.
- `/root/go 1.8G` is the only big releasable besides `target` — need explicit user consent before deleting.

## Hemat vs Full (Operator-Facing Choice)
- **1) Hemat (recommended):** single-crate `keetanetwork-block` validator POC (`BlockBuilder` with `date_ms` before/after `1763683200000`, `Amount(-1_000_000)`) already PROVEN `Main Before 2024 Ok 411222E0…` vs `AmountBelowZero` — report **High** validator bypass without npm. Ledger ghost-mint `0 - (-1e6)=+1e6` is spec, not need to deploy.
- **2) Full harness:** `npm install && cargo test --test e2e` with `init_supply 1jt → successor minus` needs `rm -rf /root/go` + targets, ~4G. Risk 50% OOM, burns operator time even if local.

## Pre-Flight Recipe (paste before every heavy `cargo run`)
```bash
df -h; free -h; du -sh /tmp/* 2>&1 | sort -rh | head -n 30; du -sh ~/.cargo/registry/cache 2>&1 | head -n 5
# if Avail <2.5G: rm -rf /tmp/poc_*/target /tmp/keeta_src/node-rs-main/target ~/.cargo/registry/cache; df -h
```

## Related
- `disk-space-session-safety` § Local-First Disk Budget
- `adversarial-bug-bounty-hunting` § Keeta infinite money (negative amount cutoff, Main 0x5382)
