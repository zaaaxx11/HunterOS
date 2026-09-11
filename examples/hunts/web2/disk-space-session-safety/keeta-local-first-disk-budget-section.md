# Local-First Disk Budget (Keeta 2026-08-12) - disk-space-session-safety

> Cut verbatim from `soul/skills/web2/disk-space-session-safety/SKILL.md` during the
> 2026-09-07 skills cull follow-up (S2b-1). Case session material (Keeta 2026-08-12);
> the skill body keeps the generic pre-flight discipline.

## Local-First Disk Budget — Check Before You Burn (2026-08-12 Keeta)

Operator signal `Local dulu deh, biar ga kebuang sia sia dana ku, cek dulu disknya biar ga OOM nnti` = check disk BEFORE spinning local harness. 20G VPS (`/dev/vda1 20G`) with 3.6G RAM, no swap. Keeta session validated OOM chain:

- Pre-flight: `df -h /` (96% → 909M free, `ar: No space left on device` on `aws-lc-sys` 4G build) → `free -h` (2.1G avail) → `du -sh /tmp/* | sort -rh | head -30` (1.6G `/tmp/poc_dev/target` + 40M `keeta_src` + 7.8M `keeta_zips` each repo). After `rm -rf /tmp/poc_*/target ~/.cargo/registry/cache` → 88% → 2.5G free (safe threshold: **keep >2.5G/3G free before any `cargo build`**).
- Harness budget: `node-harness` (`keetanet-node@0.18.2` + `typia` + `tsc`) = `npm install ~300-500M` + `cargo test --test e2e` target `3-4G` (`aws-lc-sys` alone 1G). On 20G host this = guaranteed OOM unless you `rm -rf /tmp/poc_* /tmp/keeta_src/node-rs-main/target`. Prefer **hemat mode**: single-crate `keetanetwork-block` validator POC (`<200M target`) + mock ledger `balance -= amount` (5 lines) without `aws-lc-sys`/`node_modules`. Report `Main Before 2024 Ok 411222E0…`Validator bypass** as High without full harness; full `init_supply 1jt → successor minus` only if operator explicitly asks after budget check.
- User economy rule: **local dulu, cloud jangan buang dana**. Always present choice: `1) Hemat (validator proof, 200M, no npm)` vs `2) Full harness (4G, need hapus /root/go 1.8G)`. Never auto-spawn full harness on 96% host.
- Copy-paste pre-flight (add to every long audit before `cargo run`):
  ```bash
  df -h; free -h; du -sh /tmp/* 2>&1 | sort -rh | head -n 30; du -sh ~/.cargo/registry/cache 2>&1 | head -n 5
  # if Avail <2.5G: rm -rf /tmp/poc_*/target /tmp/keeta_src/node-rs-main/target ~/.cargo/registry/cache
  df -h
  ```

See `examples/hunts/web2/disk-space-session-safety/keeta-local-first-disk-budget-2026-08-12.md` for full transcripts (aws-lc-sys error, 909M→2.5G cleanup, npm vs hemat decision).
