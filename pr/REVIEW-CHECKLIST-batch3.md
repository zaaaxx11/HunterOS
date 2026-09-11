# REVIEW-CHECKLIST-batch3 — acceptance checklist + adversarial attacks untuk C1–C10

- Penulis: Subagent B' (adversarial reviewer batch-3). Ditulis SEBELUM melihat hasil A'
  (IMPL-NOTES-batch3.md belum ada saat dokumen ini dikunci).
- Repo: `/root/Hunter` — read-only untuk saya kecuali file ini. Scratch: `/tmp/review-b3/`
  (`probe.py`, `probe2.py` — semua serangan pre-fix di bawah sudah dieksekusi nyata dan
  outputnya dikutip; jangan percaya teks, jalankan ulang).
- Baseline saat checklist ditulis: `pytest -q` → **168 passed** (app/, PYTHONPATH=src).
- **Status tree saat penulisan (A' mengerjakan paralel — beberapa fix sudah mid-flight):**
  C1 **SUDAH LANDED** (main.py:813 `except (sqlite3.Error, OSError, ValueError)` —
  garbage file sudah rc=2 tanpa traceback, diverifikasi). C5 **PARSIAL** (reopen evidence
  sudah ke-gate; set-half evidence / precond description / park-kill retrigger masih
  ACCEPTED). Lainnya masih pre-fix. Serangan di bawah tetap ditulis sebagai KONTRAK
  akhir — jalankan terhadap hasil final A', bukan kondisi sementara.

## Severity serangan (apa yang terbuka bila serangan BERHASIL menembus fix)
- **P1** = fix-nya salah / regresi nyata (behavior lama yang benar jadi rusak, crash, data hilang).
- **P2** = fix-nya setengah (gate ada di satu jalur, bocor di jalur lain; perf hanya di satu bentuk input).
- **P3** = polish (pesan, boundary kosmetik, konsistensi dok).

## Legenda hasil
- `rc 2` + stderr diawali `BLOCKED:` = kontrak standar CLI (A8). `rc 0` = sukses.
- Gate claim: exit 0 = pass, exit 2 = veto. Traceback = OTOMATIS gagal apa pun itemnya.

---

# C1 — E3: corrupt db file bocor traceback

**Fix yang disyaratkan:** `main()` catch `(sqlite3.Error, OSError, ValueError)`; pesan
BLOCKED gaya `cannot open the hunt db (<path>)`; TANPA traceback, di SEMUA command.

**Balance wajib (jangan fail-closed berlebihan):** file sqlite VALID harus tetap jalan
normal, dan **file kosong (0 byte) adalah db sqlite sah** (semantik sqlite: zero-length =
fresh db) → harus tetap rc 0, BUKAN BLOCKED.

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C1-1 | garbage file | `printf 'garbage' > /tmp/g.db; HUNT_DB=/tmp/g.db hunt status` (dan ulang untuk `hunt target list`, `hunt brief --target 1`) | rc 2, stderr `BLOCKED: cannot open the hunt db (/tmp/g.db) ...`, **tanpa** kata `Traceback`. (SUDAH terverifikasi landed: rc=2, no traceback.) |
| B3-C1-2 | file kosong = db sah | `: > /tmp/e.db; HUNT_DB=/tmp/e.db hunt status` | rc 0, output status normal (schema dibuat). Jika BLOCKED → **P1** (fail-closed berlebihan mematikan first-run UX; audit E3 hanya mensyaratkan no-traceback). |
| B3-C1-3 | direktori | `HUNT_DB=/root hunt status` | rc 2, BLOCKED, no traceback (jalur sqlite3.Error — sudah benar sebelumnya; regression pin). |
| B3-C1-4 | file valid-tapi-bukan-sqlite | `zip` kecil sebagai HUNT_DB (`notdb.zip` dari probe.py) | rc 2, BLOCKED, no traceback (bukan exit 1). |
| B3-C1-5 | file tanpa permission | chmod 000 (jalankan sebagai user NON-root; root menembus mode 000 — sudah diverifikasi) | rc 2, BLOCKED, no traceback. |
| B3-C1-6 | `/dev/null` | `HUNT_DB=/dev/null hunt status` | rc 2, BLOCKED (`disk I/O error` ter-wrap rapi — sudah terverifikasi). |
| B3-C1-7 | db VALID tidak rusak oleh fix | db beneran dipakai: add target → add lead → set-half → promote | Semua rc 0 seperti biasa; `hunt status` rc 0. Balance fail-open. |
| B3-C1-8 | jalur claim_gate tidak berubah | garbage HUNT_DB ke gate: `echo 'PROVEN[F-1]' \| HUNT_DB=/tmp/g.db python3 bridge/claim_gate.py` | Gate punya kontrak sendiri: exit 2, `BLOCKED: claim gate cannot reach the hunt db ...` — C1 TIDAK boleh mengubah pesan/exit gate. |
| B3-C1-9 | pesan tidak dobel-mengawali | perhatikan stderr B3-C1-1 | Tidak boleh `BLOCKED: ... BLOCKED: cannot open hunt db ...` di satu baris yang membingungkan — P3 bila dobel, gagal bila Traceback. (Saat ini terverifikasi memang dobel-nested: `BLOCKED: cannot open the hunt db (...): BLOCKED: cannot open hunt db (...)` — P3 polish, boleh diterima.) |

**Kontrak test yang harus ada:** `test_corrupt_db_blocked_no_traceback` (garbage file →
rc 2, stderr startswith `BLOCKED: cannot open`, `'Traceback' not in stderr`, parametrize
minimal di 2 command berbeda: `status` dan satu command tulis); `test_empty_db_file_is_fresh_db`
(rc 0); `test_valid_db_unaffected` (lifecycle pendek rc 0).

**Regresi yang bisa dipecahkan fix ini:** (a) menambah ValueError ke tuple TANPA cek —
ValueError dari gate lain di dalam `main()` (bukan connect) tidak pernah sampai situ
karena connect dipanggil pertama; aman — tapi bila A' me-restructure try/except dan
menelan ValueError dari `args.fn` (handler command), semua pesan BLOCKED ganda rc —
pin: `hunt target add X bad-url` tetap rc 2 dengan pesan gate semula. (b) Menyimpan
`db_path` variabel salah di handler error (pakai `os.environ` fallback lama, bukan
nilai HUNT_DB aktual) → pesan menunjuk path salah: P3.

---

# C2 — E12: promote_lead dua commit → orphan finding window

**Fix yang disyarakkan:** SATU transaksi per promote_lead. Pilihan desain bebas
(BEGIN IMMEDIATE...single commit, atau add_finding internal commit=False) ASAL:
trace COMMIT == 1 per promote, DAN add_finding langsung (jalur lain) masih commit sendiri,
DAN API add_finding lain tidak berubah perilaku.

Baseline terverifikasi (pre-fix, trace callback): in-wave promote = 2×COMMIT;
gap-promote = 2×COMMIT; direct add_finding = 1×COMMIT (probe2.py).

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C2-1 | single commit in-wave | trace callback (`conn.set_trace_callback`) hitung statement `COMMIT` selama SATU panggilan `db.promote_lead(...)` pada target dengan open wave | COMMIT terhitung == **1** (BEGIN opsional boleh ada). ≥2 → **P1** (fix gagal). |
| B3-C2-2 | single commit gap-promote | sama, tapi tanpa open wave (jalur yang menambah belt `UPDATE findings SET wave_id=NULL`) | COMMIT == 1; belt wave_id=NULL tetap dieksekusi (cek row). |
| B3-C2-3 | crash-injection: tidak ada orphan | monkeypatch `conn.execute` melempar exception TEPAT pada `UPDATE leads SET state='promoted'` di dalam promote_lead; tangkap exception; lalu query `SELECT COUNT(*) FROM findings WHERE lead_id IS NULL` dan `SELECT state FROM leads` | Tidak ada row finding (rollback), lead masih `open` + kedua half proven. Ulangi dengan injection di `UPDATE findings SET lead_id=...` — hasil sama. Ini inti E12. |
| B3-C2-4 | re-run setelah crash tepat satu finding | lanjutan B3-C2-3: panggil promote_lead lagi (transaction bersih) | rc sukses, `SELECT COUNT(*) FROM findings f JOIN leads l ON f.lead_id=l.id WHERE l.id=?` == 1; total finding untuk lead itu == 1 (tidak dobel). |
| B3-C2-5 | add_finding langsung tetap commit sendiri | trace `db.add_finding(conn, ...)` panggilan langsung (jalur `hunt finding add`) | COMMIT == 1 — flag internal (bila dipakai) TIDAK boleh mengubah default publik. |
| B3-C2-6 | caller add_finding lain tak berubah | grep seluruh caller `add_finding(` (main.py cmd_finding add, promote_lead); jalankan `hunt finding add` CLI | rc 0, finding tercatat, event `finding_added` ada. Bila A' menambah parameter wajib (bukan default) → **P1** API break. |
| B3-C2-7 | snapshot provenance tetap utuh | setelah promote sukses: `findings.lead_provenance` JSON valid, `lead_id` terisi, `leads.state='promoted'`, event `lead_promoted` ada | Semua bena — satu transaksi tidak boleh menghilangkan salah satu langkah. |

**Kontrak test:** `test_promote_lead_single_commit` (trace callback, in-wave, ==1),
`test_promote_lead_single_commit_gap` (gap-promote ==1),
`test_promote_crash_no_orphan_finding` (monkeypatch injection, kedua titik),
`test_promote_rerun_after_crash_exactly_one_finding`, `test_add_finding_still_commits`.

**Regresi yang bisa dipecahkan fix ini:** (a) add_finding diberi `commit=False` default
TANPA promote yang commit → `hunt finding add` CLI tidak menyimpan data (hilang saat
close) → B3-C2-5/6. (b) BEGIN IMMEDIATE dipanggil padahal transaksi implisit sqlite
sudah jalan (`sqlite3` module Python mulai transaksi saat DML) → `cannot start a
transaction within a transaction` → P1; pin: promote dari CLI rc 0. (c) open_wave
(retro-link) dan close_wave yang juga commit tidak ikut diubah — jangan sampai A'
me-refactor global; pin: suite wave tests hijau.

---

# C3 — E14: zero indexes

**Fix yang disyaratkan:** 7 index persis nama/kolom sesuai SPEC, `CREATE INDEX IF NOT
EXISTS`, idempotent, legacy db kebagian saat connect().

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C3-1 | 7 index ada di db baru | setelah connect(): `SELECT name FROM sqlite_master WHERE type='index'` | Berisi: `idx_events_finding`, `idx_events_target_kind`, `idx_findings_target`, `idx_findings_wave`, `idx_leads_target_state`, `idx_mutations_lead`, `idx_precond_lead` — nama & kolom persis SPEC (cek `sql` kolom: `events(finding_id)`, `events(target_id, kind)`, `findings(target_id)`, `findings(wave_id)`, `leads(target_id, state)`, `lead_mutations(lead_id)`, `lead_preconditions(lead_id)`). Kurang/salah kolom → **P2**. |
| B3-C3-2 | legacy db kebagian | buat db dengan SKHEMA lama (hapus index via `DROP INDEX` pada db baru, ATAU buat db dari dump pre-fix), connect() lagi | Index ada setelah connect (pragma index_list per tabel). Ini klausul "Legacy DB" di SPEC — skip tanpa test = **P2**. |
| B3-C3-3 | data legacy utuh | pada db legacy yang sama: row count tiap tabel + satu lead lifecycle pendek | Identik dengan sebelum connect; lifecycle rc 0. |
| B3-C3-4 | EXPLAIN memakai index | `EXPLAIN QUERY PLAN SELECT ... FROM lead_mutations WHERE lead_id=?` (dan preconditions) | `SEARCH ... USING INDEX idx_mutations_lead` — bukan `SCAN`. (E6's LIKE query boleh tetap SCAN sampai kind-filter E6 dipatch — bukan scope batch ini; jangan gagalkan C3 karena itu.) |
| B3-C3-5 | idempotent | connect() dua kali berturut-turut (dua proses) | Tidak ada error, index tidak dobel (sqlite_master count tetap 7 per nama unik — IF NOT EXISTS). |
| B3-C3-6 | perf tidak mundur | `pytest -q` penuh + micro-time export_brief | Suite hijau; brief tidak lebih lambat nyata. |

**Kontrak test:** `test_indexes_created_on_connect` (7 nama + kolom), 
`test_indexes_created_on_legacy_db` (drop → connect → ada), `test_schema_connect_idempotent`.

**Regresi:** (a) index di dalam SCHEMA script vs eksekusi terpisah — bila A' menaruh
`CREATE INDEX` di `connect()` SETIAP kali tanpa IF NOT EXISTS → error "already exists"
→ B3-C3-5. (b) Menambah index dengan nama berbeda dari SPEC → CI/arbiter mismatch → P2.

---

# C4 — E5: claim gate O(M×N) — 100s di 5MB

**Mekanisme terkalibrasi (wajib dibaca):** `nearest_binding` mengambil window = baris
marker (plus ±80 char). Biaya = O(M × panjang-baris). Input 5MB **TANPA newline** →
window = seluruh teks per marker: **1MB/900 marker = 27.9 detik (terukur) ≈ 140s di
5MB**. Input sama DENGAN newline antar record = **132 ms**. Tes perf yang pakai input
ber-newline TIDAK membuktikan apa pun → **bentuk no-newline wajib**.

**Kontrak perilaku yang TIDAK BOLEH BERUBAH (semua sudah dipin via probe, nilai aktual):**
`PROVEN[F-1] L-2` → (PROVEN, 1, None); `PROVEN[L-2] F-1` → (None, 2) [L-bracket menang];
`PROVEN L-2 near #9` → (None, 2) [race jarak, L lebih dekat]; `PROVEN F-1 L-1` vs
`PROVEN L-1 F-1` → masing-masing (1,None)/(None,1); `PROVEN L-1  F-1` tie → finding
menang (tie→F, v0.3); `PROVEN` di EOF → (None,None) → veto; marker 90+ char dari id
DI BARIS YANG SAMA → tetap ke-bind (window menyapu baris penuh): `x*90 PROVEN y*90 F-7`
→ (7,None); `XPROVEN` (glued) → bukan marker; unicode multibyte di window → offset aman.

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C4-1 | perf 5MB tanpa newline (bentuk audit) | `blob = ("PROVEN L-2 " + "lorem ipsum dolor sit " * 50) * 5000` (~5.5MB, 5000 bare marker, tanpa `\n`); time `cg.claims(blob)` | **< 2 detik** (SPEC: 5MB/900 marker < 2s; gunakan 900 marker bila ingin persis SPEC — keduanya harus lolos). >2s → **P2** (fix setengah: mungkin hanya per-marker yang di-explicit-bind yang cepat). |
| B3-C4-2 | perf VARIAN SPEC 900 marker | 5MB, 900 marker bare tanpa newline | < 2s. |
| B3-C4-3 | golden corpus equality | jalankan SEMUA bentuk di atas (14 semantics) terhadap claims() baru, bandingkan tuple-per-tuple dengan daftar expected di header C4 | Identik 100%. Satu saja beda (mis. tie berbalik ke lead) → **P1** — banyak test pegang shape ini. |
| B3-C4-4 | precedence F-bracket vs L-bracket bare | `PROVEN[F-1] L-2` → (1,None); `PROVEN[L-2] F-1` → (None,2) | Sesuai header. Fix yang memindahkan parse bracket ke pass gabungan sering menukar urutan ini → P1. |
| B3-C4-5 | boundary: marker di baris TERAKHIR | input berakhir tepat setelah marker tanpa trailing newline (`"...\nPROVEN"`) | (None,None) → veto tetap; tidak ada IndexError/off-by-one. |
| B3-C4-6 | input kosong & marker saja | `claims("")` → []; `claims("PROVEN")` → [(PROVEN,None,None)] | Sesuai; main() rc 0 untuk kosong, rc 2 veto untuk marker saja. |
| B3-C4-7 | unicode multibyte di window | `"PROVEN „ü™—nünü™ F-3"` → (3,None); input dengan emoji di dekat marker | Offset byte-vs-char tidak menggeser bind (python str = char — pastikan fix baru tidak mulai index byte). |
| B3-C4-8 | 5MB dengan newline TIDAK lebih lambat dari dulu | bentuk ber-newline 132ms baseline | < 2s juga (mencegah fix yang malah memperlambat bentuk sehat) — P3 bila melewati. |
| B3-C4-9 | suite claim_gate hijau | `pytest tests/test_claim_gate.py -q` | Semua hijau (behavioral no-change kontrak SPEC). |
| B3-C4-10 | adversarial no-boundary tidak meledak | `("PROVEN"+"x"*5500+"\n")*900` (~5MB, baris 5.5KB) | < 2s (bentuk antara — window per baris besar tapi tidak seluruh teks). |
| B3-C4-11 | exact-bind O(1) di teks raksasa | 5MB tanpa newline, SEMUA marker berbentuk `PROVEN[F-7]` | < 0.5s (explicit bind tidak boleh menyentuh nearest-scan sama sekali). |

**Kontrak test:** `test_claims_perf_5mb` (nama dari SPEC; **input tanpa newline**, 900
bare marker, assert < 2s, ukur via time.perf_counter); `test_claims_golden_corpus`
(parametrize seluruh 14 bentuk); `test_claims_unicode_offsets`; 
`test_claims_marker_last_line_boundary`.

**Regresi yang bisa dipecahkan fix ini:** (a) pass regex gabungan `(\bPROVEN\b|...)` dengan
posisi yang dihitung dari `m.start()` pola berbeda → salah offset saat marker overlap
(EXPLOITABLE di dalam admin takeover phrase) — pin EXPLOITABLE + "admin takeover" di
golden corpus. (b) Binary search atas posisi L-id: `_LEAD_ID` match `L-1` DI DALAM
`PROVEN[L-2]`? Sekarang: `L-2` di bracket TIDAK masuk nearest race karena explicit bind
meng-ccontinue sebelum nearest dipanggil — pass gabungan yang mengindeks semua posisi
tetap benar asal nearest hanya dipanggil untuk bare marker. (c) Tie-break terbalik
(L menang saat seri) → B3-C4-3/4.

---

# C5 — R2-06: secrets gate hanya di payload

**Fix yang disyaratkan:** `assert_no_secrets` (+redact display di brief) ke 5 field:
set-half evidence, precondition description, mutation evidence, reopen evidence,
retrigger (park & kill-refusal). Pesan BLOCKED style sama (`BLOCKED: <field> contains
what looks like a raw secret`). Storage menolak (bukan hanya menampilkan redacted).

Baseline pre-fix (probe2.py): set-half evidence ACCEPTED; precond description ACCEPTED;
park retrigger (ghp) ACCEPTED; kill-refusal retrigger (hex) ACCEPTED; reopen evidence
SUDAH BLOCKED (mid-flight). Hex non-token di brief: **echo verbatim = True**.

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C5-1 | set-half evidence | `db.set_lead_half(conn, lid, 'trigger', 'proven', 'ev <ghp-token-shape>')` | ValueError `BLOCKED: ... evidence contains what looks like a raw secret`; row half TIDAK berubah. |
| B3-C5-2 | precond description | `db.add_lead_precondition(conn, lid, 'role', 'admin', 'desc <sk-token-shape>')` | BLOCKED, row tidak ter-insert. |
| B3-C5-3 | mutation evidence | `db.mutate_lead(..., 'advanced', 'ev <ghp-token-shape>')` | BLOCKED, tidak ada row lead_mutations. |
| B3-C5-4 | reopen evidence | park → `db.reopen_lead(conn, lid, 'token <ghp-token-shape>')` | BLOCKED (sudah landed — regression pin, jangan sampai fix C5 lain menghapusnya). |
| B3-C5-5 | park retrigger | `db.park_lead(conn, lid, 'observable :: <ghp-token-shape>')` | BLOCKED, state tetap open. |
| B3-C5-6 | kill-refusal retrigger | kill dengan refutations + `retrigger='deploy log :: api key 9f8e7d6c5b4a3210fedcba9876543210'` | BLOCKED (jalur `_parse_retrigger` ke-gate — jalur yang sama dipakai park otomatis). |
| B3-C5-7 | brief tidak echo hex verbatim | park dengan `api key 9f8e7d6c5b4a3210fedcba9876543210` → TIDAK boleh lolos ke storage; kontrol: `export_brief` | `9f8e7d6c5b4a3210` TIDAK muncul di brief. Bila gate ada tapi brief masih menampilkan (jalur legacy row) → P2; bila gate baru tidak menutup hex (assignment-pattern) → P2. |
| B3-C5-8 | token-shape tetap ke-redact di display (jalur lama) | row lama (raw SQL insert) berisi `<ghp-token-shape>` → export_brief | `[REDACTED-GH-TOKEN]` (perilaku redact display yang sudah ada tidak rusak). |
| B3-C5-9 | assignment shape di field baru | evidence `password=hunter2secretvalue` | BLOCKED (assignment pattern ikut ke assert_no_secrets — jangan hanya token regex). |
| B3-C5-10 | teks bersih tidak over-blocked | evidence biasa (`admin panel reachable`, kata "task", "class", angka panjang 19 digit non-secret) | ACCEPTED rc 0 — false positive merusak workflow (P2 bila over-block). |
| B3-C5-11 | string kosong/None aman | evidence `''` di semua 5 field | Perilaku semula (tidak crash — beberapa field punya validasi non-empty sendiri). |
| B3-C5-12 | pesan konsisten | bandingkan pesan 5 field | Semua `BLOCKED: <field> contains what looks like a raw secret` — nama field benar (bukan semua "payload"). Salah nama → P3. |
| B3-C5-13 | storage menolak, bukan menyimpan redacted | setelah BLOCKED di masing-masing field: baca row | Tidak ada nilai tersimpan sama sekali (refuse), BUKAN row berisi `[REDACTED-KEY]` yang tersimpan diam-diam. SPEC: "redact() display-only — untuk storage gunakan pola sama seperti payload gate" (payload = refuse). Menyimpan redacted tanpa refusal → **P2**. |
| B3-C5-14 | jalur findings lama tetap ke-gate | `db.add_finding(..., notes='<ghp-token-shape>')` | BLOCKED (regression — C5 tidak boleh melemahkan gate payload/notes/falsifier/title yang ada). |

**Kontrak test:** `test_lead_free_text_secret_gates` (parametrize 5 field, tiap raw-secret
→ ValueError dengan pesan ter-pin), `test_brief_never_echoes_secrets` (hex non-token
shape via park → brief bersih), `test_clean_evidence_not_blocked` (anti-false-positive),
`test_finding_secrets_gate_unchanged`.

**Regresi:** (a) Gate dipasang di CLI saja (main.py) tanpa db-level → panggilan db langsung
(python API / jalur internal) bocor — pasang di db.py seperti payload gate. (b) A'
menambah gate di `set_lead_payload` dua kali → dobel pesan; P3. (c) Oracle evidence string
(baseline/candidate JSON) melewati field ini? `record_oracle_verdict` membangun evidence
dari angka+sha — aman; tapi bila A' menambah assert di _set_lead_half (semua verdict
path), evidence oracle yang panjang hex sha 64-char TIDAK boleh ketablok (64-hex bukan
pattern secret) — pin: oracle run sukses setelah fix → P1 bila oracle rusak.

---

# C6 — R2-08: park membungkam flag 7-hari

**Fix yang disyaratkan:** `lead_contradictions` flag `state IN ('open','mutating','parked')
AND payload IS NULL` age > 7 hari.

Baseline (probe2.py): open 8d payload-less → flag ADA; parked 8d payload-less → flags=[];
mutating 8d payload-less (payload di-NULL-kan setelah masuk mutating) → flags=[].

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C6-1 | parked tetap di-flag | lead payload-less, backdate 8d, park → `lead_contradictions` | Flag `!! lead L-n still payload-less after 8 days` MUNCUL (pre-fix: kosong). Kosong → **P2**. |
| B3-C6-2 | mutating ikut di-flag | lead bermutasi lalu payload NULL (backdate 8d) | Flag muncul. |
| B3-C6-3 | open tidak regresi | kondisi lama (open 8d) | Flag tetap muncul (sama seperti pre-fix). |
| B3-C6-4 | parked DENGAN payload tidak di-flag | park lead ber-payload, backdate 8d | flags=[] — jangan over-flag (flag = payload-less saja). |
| B3-C6-5 | boundary umur | umur tepat 7 hari (bukan >) → tidak flag; 7.5 hari → flag | Sesuai `> 7` (perilaku lama dipertahankan di state baru). |
| B3-C6-6 | payload='' vs NULL | dua lead, satu payload='' satu NULL (add_lead mengubah ''→None) | Keduanya di-flag di ketiga state. |
| B3-C6-7 | flag sampai ke brief | export_brief target dengan parked payload-less 8d | Baris flag tampil di bagian contradictions brief (surface tetap sampai operator). |
| B3-C6-8 | killed TIDAK di-flag | kill lead payload-less 8d | flags=[] (killed sudah diadili — spec hanya open/mutating/parked). Over-flag → P3. |

**Kontrak test:** `test_payloadless_parked_lead_still_flagged` (nama dari audit/SPEC),
`test_payloadless_mutating_lead_still_flagged`, `test_parked_with_payload_not_flagged`,
`test_payloadless_killed_not_flagged`.

**Regresi:** (a) Query baru lupa `target_id=?` → flag lead target lain bocor ke brief
target ini (cross-target pollution) — pin dengan 2 target. (b) Bila reopen (E1, sudah
landed) membawa lead parked→open, flag jalan lagi — pin transitions: park→flag ada →
reopen → set payload → flag hilang.

---

# C7 — B-L21: next_mutation di lead promoted mengembalikan langkah

**Fix yang disyaratkan:** promoted (dan killed) = BLOCKED dengan pesan jelas.

**⚠ REGRESI PALING BERBAHAYA BATCH INI:** `export_brief` (db.py:2021) memanggil
`next_mutation(conn, lead["id"])` untuk leads di brief. Pre-fix next_mutation TIDAK
me-raise (return dict/None). Bila A' mengubahnya me-raise ValueError untuk promoted
TANPA men-guard caller brief → **`hunt brief` crash** untuk setiap db yang punya lead
promoted. (Saat pre-fix, promoted leads disembunyikan brief — verifikasi apakah loop
brief benar-benar skip promoted; JANGAN asumsi.)

Baseline (probe2.py): promoted dengan precondition masih-missing → next_mutation
mengembalikan langkah actionable (bukti bug); killed dengan missing precond → juga.

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C7-1 | next di promoted BLOCKED | lead: precond missing + kedua half proven + promote; `hunt lead next --lead N` | rc 2, `BLOCKED: ... promoted ...` (pesan menyebut state; tidak ada langkah mutation bocor). |
| B3-C7-2 | next di killed BLOCKED | sama via kill | rc 2 BLOCKED menyebut killed. |
| B3-C7-3 | next di open/mutating tidak regresi | lead open dengan precond missing | `{'precondition_id': ..., 'variable': ...}` tetap keluar rc 0 (fungsi utama tidak rusak). |
| B3-C7-4 | next di parked | lead parked | BLOCKED juga (parked bukan lane mutation) — konsisten dengan pesan; bila A' hanya blok promoted → P2. |
| B3-C7-5 | **brief tetap hidup setelah promote** | db dengan lead promoted (dan killed), `hunt brief --target N` | **rc 0**, brief tercetak penuh, TIDAK ada traceback. INI SERANGAN TERSAKIT: bila next_mutation sekarang raise dan brief memanggilnya tanpa guard → crash. |
| B3-C7-6 | level db pesan tepat | `db.next_mutation(conn, promoted_id)` | ValueError `BLOCKED:` (bukan None, bukan return langkah). Return None tanpa pesan = **P2** (half-fix: CLI harus tetap bisa membedakan dari exhaustion). |

**Kontrak test:** `test_next_mutation_blocked_on_promoted`, 
`test_next_mutation_blocked_on_killed`, `test_next_mutation_open_lead_unchanged`,
`test_brief_survives_promoted_and_killed_leads` (brief rc 0 — anti-crash pin).

**Regresi:** (a) brief: guard dengan try/except per-lead ATAU skip non-(open/mutating)
sebelum memanggil — salah satu cukup; bila A' pilih mengubah next_mutation jadi return
None untuk terminal states, CLI `hunt lead next` harus tetap BLOCKED (pisahkan level db
vs CLI) — bila CLI jadi rc 0 tanpa output → P2. (b) `hunt lead list` render state —
pastikan tidak ikut menyentuh next_mutation.

---

# C8 — B-L24: oracle feature absurd values

**Fix yang disyaratkan:** `_read_oracle_feature`: status 100–599, size ≥ 0, timing ≥ 0
dan ≤ 3600000. Di luar = BLOCKED.

Baseline (probe2.py): SEMUA value absurd ACCEPTED pre-fix (status -5/99/600/999,
size -1, timing 10^12/3600001). Nilai legal: status 100 & 599, size 0, timing 0 &
3600000 — ACCEPTED (harus TETAP legal).

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C8-1 | status di luar range | `{"status": -5}` / `{"status": 99}` / `{"status": 600}` / `{"status": 999}` via _read_oracle_feature | BLOCKED per nilai. |
| B3-C8-2 | status boundary dalam | status=100 dan status=599 | ACCEPTED (jangan over-block: 599 = HTTP legal). |
| B3-C8-3 | size negatif | size=-1 | BLOCKED; size=0 ACCEPTED. |
| B3-C8-4 | timing range | timing=-1 → BLOCKED; 0 → ACCEPTED; 3600000 → ACCEPTED; 3600001 → BLOCKED; 10**12 → BLOCKED | Persis (1 jam bound). timing=-1 pre-fix ACCEPTED — fix E15-adjacent yang diminta SPEC (timing ≥ 0). |
| B3-C8-5 | bound berlaku kedua sisi | tulis baseline.json DENGAN timing 3600001, candidate normal → `hunt oracle --baseline base.json --candidate cand.json` | BLOCKED menyebut sisi baseline (side label benar: "baseline"/"candidate" di pesan). Salah sisi → P2. |
| B3-C8-6 | tipe tetap ketat | status=200.0 (float), size=10.0, status=true | BLOCKED (type check lama tidak boleh hilang demi range check). |
| B3-C8-7 | pesan kontekstual | baca pesan BLOCKED | Menyebut lead, side, file path, dan nilai (`got ...`) seperti style gate lain. |
| B3-C8-8 | verdict math tidak berubah | fitur legal: baseline(status=200, timing=10), candidate(status=403, timing=5000) → verdict | `unknown`/`confirmed` sesuai aturan lama — C8 murni validasi input, jangan sentuh oracle_verdict. |
| B3-C8-9 | timing=0 semantics | baseline timing 0 (legal sekarang), candidate timing 10 → verdict | max(baseline,1.0) guard lama tetap bekerja (tidak ZeroDivision/braking) — timing 0 dulu maupun sesudah fix legal. |

**Kontrak test:** `test_oracle_feature_ranges` (parametrize: status -5/99/600/999 BLOCKED,
100/599/200 OK; size -1 BLOCKED, 0 OK; timing -1/3600001/10**12 BLOCKED, 0/3600000 OK),
`test_oracle_feature_ranges_both_sides`.

**Regresi:** (a) A' mem-block timing 0 (salah baca "≥ 0") → mengubah verdict untuk
respons cepat — B3-C8-4/9. (b) Range check di oracle_verdict (pure function) alih-alih
_read_oracle_feature → file dengan nilai absurd lolos validasi tapi verdict aneh —
tempat yang benar: _read_oracle_feature (SPEC eksplisit).

---

# C9 — R2-07: v0.4 invisible di doktrin (docs-only)

**Fix yang disyaratkan:** README bullet + 1 baris L-binding; QUICKSTART §4.5 "the
observation lane" (add → next → mutate → set-half → promote + oracle, 5–6 command);
FRAMEWORK.md L2 row leads + L4 "v0.4"; HUNT-BRIDGE 6 lead commands di gate list + CLAIMS
L-binding line; CI gate `grep -c 'hunt lead' HUNT-BRIDGE.md >= 5`. SOUL.md TIDAK diubah.
Jangan claim lebih dari yang kode lakukan.

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C9-1 | jalankan SETIAP command yang docs ajarkan (JANGAN percaya teks) | fresh db; eksekusi verbatim persis urutan §4.5 QUICKSTART baru: `hunt target add` (→score→roe bila docs menyebut) → `hunt lead add` → `hunt lead next` → `hunt lead mutate` → `hunt lead set-half` ×2 → `hunt lead promote --roe-action read` → `hunt oracle ...` | SEMUA rc 0 DAN output cocok dengan yang diklaim docs. Satu saja gagal/berbeda → **P1** (doktrin mengajarkan command yang mati — persis E22 kemarin). Perhatikan: promote butuh `--roe-action` (E22) — bila §4.5 tidak menyebutnya dan command docs gagal parse → P1. |
| B3-C9-2 | CI structure gate | `grep -c 'hunt lead' soul/bridge/HUNT-BRIDGE.md` | ≥ 5; dan ci.yml benar-benar punya step gate ini (bukan hanya teks di docs). |
| B3-C9-3 | CLAIMS line L-binding akurat | baca baris `PROVEN[L-<n>]` di HUNT-BRIDGE; bandingkan dengan perilaku gate AKTUAL (claim_gate.py vet()) | Docs harus bilang lead claim diadili state lead **dan finding yang dimintanya masih proven-live** (R2-01 sudah landed). Bila docs bilang "dijuduli state lead saja" → **P1** (docs mengajarkan kontrak lama yang sudah dipatch). Uji silang: `PROVEN[L-1]` setelah overturn finding → rc 2 (perilaku nyata yang harus dideskripsi docs). |
| B3-C9-4 | README bullet truthful | setiap klaim faktual di bullet baru dicek ke kode | Tidak ada klaim yang tidak bisa dijalankan persis (mis. "hunt lead reopen" — ADA sekarang; "oracle cap 3 runs" — TIDAK ADA di kode, jangan sampai README mengklaim). Klaim kode-tidak-ada → P1. |
| B3-C9-5 | FRAMEWORK L2/L4 | `grep -n "v0.4" docs/FRAMEWORK.md` + row leads di tabel L2 | Ada; L4 tidak lagi bilang "v0.3" sebagai versi sekarang. |
| B3-C9-6 | SOUL.md untouched | `git diff --stat soul/SOUL.md` vs baseline | Kosong. |
| B3-C9-7 | secret-scan CI tetap hijau | docs baru tidak memuat `ghp_`/`sk-` shape (contoh command pakai placeholder non-secret) | `grep -rEn "ghp_ + [A-Za-z0-9]{20,} (token-shape regex, written split so this doc cannot self-match) | sk- + [A-Za-z0-9]{20,}" (dengan ghp_ ditulis ghp[_] agar scan tidak self-match) --include="*.md" .` → kosong. |
| B3-C9-8 | QUICKSTART tidak mengubah bagian lama yang benar | diff QUICKSTART | §1–§4 lama tetap benar (perintah lama tidak dihapus/diubah diam-diam); §4.5 tambahan. |

**Kontrak test:** CI step `hunt-bridge-lead-gate` (grep -c ≥ 5, exit 1 bila kurang);
opsional test python: baca QUICKSTART, ekstrak blok kode §4.5, jalankan tiap baris ke
fresh db (test doktrin-eksekusi — paling tajam).

**Regresi / klaim rawan:** (a) docs menulis `hunt lead promote --lead 1 --klass Access
--severity high` TANPA `--roe-action` → gagal parse (required) → P1 (B3-C9-1 menangkap).
(b) docs menulis `hunt oracle` tanpa `--half/--baseline/--candidate` (semua required) →
P1. (c) docs menyebut `hunt lead kill` tanpa menjelaskan refusal-park — bukan gagal,
tapi P3 (operator kaget). (d) L-binding line di HUNT-BRIDGE memakai bentuk `PROVEN[L-n]`
yang tidak persis dipahami gate (gate match `\[L-(\d+)\]`) — typo bentuk di docs
(`PROVEN [L-n]` dengan spasi) mengajarkan binding yang TIDAK eksis → P2.

---

# C10 — E18: dead code

**KOREKSI LOKASI (penting):** `_t()` TIDAK ADA di claim_gate.py — `_t` ada di
**main.py:100** (`def _t(v: str) -> str: return v`, zero-reference). `nearest_finding()`
ADA di **claim_gate.py:103** (wrapper nearest_binding, zero-reference di seluruh repo —
grep terverifikasi: hanya definisinya). SPEC/audit salah lokasi untuk `_t`. A' harus:
grep dulu, hapus `nearest_finding` dari claim_gate.py dan `_t` dari main.py (keduanya
aman dihapus), ATAU SKIP dengan catatan lokasi. Menghapus "dari claim_gate" saja tanpa
menemukan `_t` di main.py = **P2** (setengah).

| ID | Serangan | Langkah | Expected |
|---|---|---|---|
| B3-C10-1 | zero-reference terbukti | `grep -rn "nearest_finding\|\b_t(" app/src bridge app/tests` setelah fix | 0 hit (kecuali komentar). Sisa referensi → **P1** (NameError saat runtime). |
| B3-C10-2 | tidak ada behavior change | pytest penuh (168+) | Hijau semua. |
| B3-C10-3 | gate output identik | golden corpus C4 sebelum vs sesudah | Byte-identical (nearest_finding hanya wrapper — menghapusnya tidak boleh menyentuh claims()). |
| B3-C10-4 | bila diputuskan SKIP | IMPL-NOTES | Catatan alasan + grep output. Hapus sebagian (nearest_finding ya, _t tidak) tanpa alasan = P2. |
| B3-C10-5 | jangan kebawa hapus fungsi hidup | diff claim_gate.py hanya minus nearest_finding (dan docstring rujukannya bila ada); diff main.py hanya minus _t | Tidak ada fungsi lain terhapus. |

**Kontrak test:** Tidak perlu test baru (dead code); pin dengan grep-guard opsional:
`test_no_dead_helpers` (import module, assert not hasattr(claim_gate, 'nearest_finding')).

**Regresi:** (a) A' menghapus `nearest_binding` (yang HIDUP, dipakai claims) karena salah
baca — B3-C4-3 golden corpus + suite menangkap. (b) `_t` ternyata dipakai di bloat
fungsional yang direncanakan — grep 0 hit hari ini; bila ragu, SKIP-dengan-catatan lebih
baik daripada menghapus.

---

## Ringkasan jumlah serangan

| Item | Serangan | P1-potensial terbesar |
|---|---|---|
| C1 | 9 | fail-closed berlebihan (empty file) |
| C2 | 7 | orphan tetap ada / add_finding publik rusak |
| C3 | 6 | legacy db tidak kebagian index |
| C4 | 11 | perf test pakai bentuk salah (newline) → 100s lolos |
| C5 | 14 | gate di CLI saja / storage redact-diam |
| C6 | 8 | over-flag (payload lead di-flag) / cross-target |
| C7 | 6 | **brief crash** (next_mutation raise tanpa guard caller) |
| C8 | 9 | timing 0 over-blocked / salah sisi |
| C9 | 8 | §4.5 command gagal diparse (roe-action/oracle args) |
| C10 | 5 | lokasi _t salah / fungsi hidup terhapus |
| **Total** | **83** | |

## 5 serangan paling berbahaya (urut dampak)
1. **B3-C7-5** — brief crash: export_brief memanggil next_mutation per lead; fix C7 yang
   me-raise tanpa guard mematikan `hunt brief` untuk db mana pun yang punya lead promoted.
2. **B3-C4-1/2** — perf test bentuk salah: input ber-newline selesai 132ms walau fix
   gagal; hanya bentuk no-newline yang mengungkap O(M×N) (1MB/900 marker = 27.9s terukur).
3. **B3-C2-3/4** — crash-injection orphan: inti E12; dua titik injection harus sama-sama
   bersih, dan re-run tepat satu finding.
4. **B3-C9-1** — docs yang mengajarkan command mati: §4.5 wajib dieksekusi verbatim
   (promote tanpa --roe-action / oracle tanpa required flags = P1, pola E22 berulang).
5. **B3-C10-1/2** — lokasi `_t` di main.py:100 bukan claim_gate.py: hapus yang salah
   (nearest_binding yang hidup) mematikan claim gate; skip tanpa catatan = half-done.

## Catatan untuk arbiter
- Semua expected output di atas hasil eksekusi nyata pre-fix/landed-parsial di
  /tmp/review-b3 (probe.py, probe2.py) — bukan rekaan. Saat hasil A' keluar, jalankan
  ulang kedua probe + serangan bertanda P1 dulu, lalu sisanya.
- C1 dan reopen-gate (C5) sudah landed saat checklist ini ditulis; expected B3-C1-1,
  B3-C1-3, B3-C1-6, B3-C5-4 sudah terverifikasi hijau terhadap fix yang ada.
