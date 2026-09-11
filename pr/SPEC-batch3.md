# SPEC — Batch 3: sisa P2/P3 dari AUDIT-v0.4-1 (engineering) + AUDIT-v0.4-2 (product)

Status: FINAL (arbiter). Implementer: Subagent A'. Reviewer adversarial: Subagent B'.
Scope: fix di bawah SATU-SATU. JANGAN sentuh yang bukan di daftar. Repo: /root/Hunter.

## C1. E3 — corrupt db file bocor traceback (main.py catch tuple)
main.py `main()` catch `(sqlite3.Error, OSError)` tapi `db.connect()` raise ValueError.
Fix: tambah ValueError ke tuple catch + BLOCKED message. Test: `printf 'garbage' > db` → setiap command = `BLOCKED: ... cannot open hunt db` rc 2, tanpa traceback. (Audit v0.3 A8 kontrak verbatim.)

## C2. E12 — promote_lead dua commit → orphan finding window
Satu promote = 2 COMMIT (trace-verified). Fix: promote_lead harus satu transaksi:
- simpan autocommit state, `BEGIN IMMEDIATE`, kerja, satu commit di akhir; atau
- add_finding dipanggil dengan flag `commit=False` internal dan promote_lead commit sendiri sekali.
Pilih desain yang tidak mengubah perilaku API lain. Test kontrak:
`test_promote_lead_single_commit` (trace callback hitung COMMIT == 1) + crash-injection monkeypatch → tidak ada orphan `lead_id IS NULL` finding, lead state konsisten.

## C3. E14 — zero indexes (fix 5 baris, efisiensi termurah)
SCHEMA db.py tambah (idempotent, `CREATE INDEX IF NOT EXISTS`):
`idx_events_finding ON events(finding_id)`,
`idx_events_target_kind ON events(target_id, kind)`,
`idx_findings_target ON findings(target_id)`,
`idx_findings_wave ON findings(wave_id)`,
`idx_leads_target_state ON leads(target_id, state)`,
`idx_mutations_lead ON lead_mutations(lead_id)`,
`idx_precond_lead ON lead_preconditions(lead_id)`.
Legacy DB: connect() idempotent (CREATE IF NOT EXISTS — sama seperti tabel). Test: index ada setelah connect() di DB lama (pragma index_list).

## C4. E5 — claim gate O(M×N), 100s di 5MB input
claims() scan full text per marker + nearest window per bare marker. Fix: pre-compute
posisi semua F-id/L-id SEKALI (satu pass regex gabungan), lalu nearest-id pakai binary
search / linear scan atas list posisi (bukan re-scan text). Struktur output claims()
TIDAK BOLEH BERUBAH (return shape sama persis — banyak test pegang). Test kontrak:
`test_claims_perf_5mb` — input 5MB/900 markers harus < 2 detik (sekarang 100s) + semua
existing claim_gate tests tetap hijau (behavioral no-change).

## C5. R2-06 — secrets gate cuma di payload
Wire `assert_no_secrets` + `redact` ke: set-half evidence, precondition description,
mutation evidence, reopen evidence, retrigger field (park/kill). Pesan BLOCKED style sama.
PERHATIAN: redact() display-only — untuk storage gunakan pola sama seperti payload gate.
Test: tiap field dengan `ghp_`/`sk-` shape = BLOCKED; brief tidak echo secret verbatim.

## C6. R2-08 — park membungkam flag 7-hari
`lead_contradictions`: flag `state IN ('open','mutating','parked') AND payload IS NULL`
age > 7 hari. Test: `test_payloadless_parked_lead_still_flagged` (audit sudah tulis bentuknya).

## C7. B-L21 — `next_mutation` di lead promoted mengembalikan langkah
State gate: promoted (dan killed) = BLOCKED dengan pesan jelas. Test: next di promoted = BLOCKED.

## C8. B-L24 — oracle feature absurd values
`_read_oracle_feature`: bound ranges — `status` 100-599, `size` >= 0, `timing_ms` >= 0
dan <= 3600000 (1 jam). Di luar = BLOCKED. Test: status=-5, size=-1, timing 10**12 = BLOCKED.

## C9. R2-07 — v0.4 invisible di doktrin (docs-only)
- README.md: tambah bullet leads/oracle + 1 baris L-binding.
- QUICKSTART.md: §4.5 "the observation lane": add → next → mutate → set-half → promote + hunt oracle (5-6 command nyata).
- docs/FRAMEWORK.md: L2 row leads, L4 tulis "v0.4".
- soul/bridge/HUNT-BRIDGE.md: 6 lead commands masuk gate list + CLAIMS line L-binding
  (`PROVEN[L-<n>]` binds the lead; a lead claim dies with its finding).
- CI gate: `grep -c 'hunt lead' soul/bridge/HUNT-BRIDGE.md` >= 5 (structure gate yang sudah ada).
JANGAN ubah SOUL.md. Jangan claim lebih dari yang kode lakukan.

## C10. E18 — dead code
Hapus `_t()` dan `nearest_finding()` dari claim_gate.py kalau benar tidak terpakai
(grep dulu; kalau dipakai, SKIP dan catat). Tidak boleh ada behavior change.

## Urutan & aturan
- Kerjakan C1..C10 berurutan; tiap fix = test hijau sebelum lanjut.
- Full suite harus hijau di akhir (168 sekarang; akan naik).
- JANGAN commit/push/CI/app structure di luar scope. JANGAN install deps.
- Tulis catatan: /root/Hunter/pr/IMPL-NOTES-batch3.md (real run output).
- DEFINISI DONE: semua C1-C10 done atau SKIP-dengan-alasan + suite hijau + notes ada.
