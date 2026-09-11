# IMPL-NOTES — Lead Lifecycle + Observation Oracle (HUNT-OS v0.4)

Implementer: Subagent A (cross-correction scheme). Spec: `pr/SPEC-leads-oracle.md`.
Status: **DONE — full suite hijau di box ini (Linux), 160 tests** (126 lama + 34 baru).
Tidak ada commit/push, tidak ada perubahan CI/`.push_api.py`/SOUL, tidak ada dep baru (stdlib-only, sesuai kontrak spec §0).

---

## 1. Hasil run nyata (bukan rencana)

```
$ cd /root/Hunter/app
$ PYTHONPATH=src python3 -m pytest tests/ -q
..........                                                            [100%]
160 passed in ~7s            # sebelum: 126 passed (baseline v0.3)

$ PYTHONPATH=src python3 -m unittest discover -s tests
OK                            # jalur CI (unittest) juga hijau

Per file:
  tests/test_enforcement.py  109 passed (tidak ada test lama yang digugurkan; 1 disesuaikan — lihat §4.4)
  tests/test_leads.py         29 passed (baru, matrix [M1]-[M24])
  tests/test_claim_gate.py    22 passed (17 lama + 5 L-binding baru)
```

Rincian suite:
- `tests/test_enforcement.py` — 126 tests lama, tetap hijau (1 di antaranya disesuaikan, lihat §4.4).
- `tests/test_leads.py` — 29 tests baru (matrix §4 spec, item [M1]–[M24] di-numbering di docstring; beberapa item = 2 test).
- `tests/test_claim_gate.py` — 5 tests L-binding baru + 1 test lama disesuaikan ke bentuk return `claims()` yang baru (triple).

## 2. Yang dibangun

### 2.1 Schema (`app/src/huntos/core/db.py`, SCHEMA)
- `leads` — persis SQL spec §1 (CHECK 5 state, CHECK dua-duanya 4-verdict — I1 ditulis eksplisit dua kali, `dismissal_count` sekali deklarasi, `UNIQUE(target_id, number)`, `datetime('now')`).
- `lead_preconditions` — UNIQUE(lead_id, variable, value), status CHECK `missing|present|refuted`.
- `lead_mutations` — `old_value` SENGAJA di luar UNIQUE key; UNIQUE(lead_id, variable, new_value) anti-repeat (I7); `followup_precondition_id` + `oracle_event_id`.
- Migrasi findings guarded+idempotent di `connect()`: `PRAGMA table_info(findings)` → tambah `lead_id INTEGER` / `lead_provenance TEXT` hanya bila belum ada (pola B4/falsifier yang sudah ada). Legacy db tetap jalan (test M22 membuktikan: db v0.3-skeleton dimigrasi lama `add_finding` lama sukses).

### 2.2 Fungsi db (semua BLOCKED-messaging menyebut objek `lead L-n`, fail-closed, commit per aksi)
| Fungsi | Invariant yang dijaga |
|---|---|
| `add_lead(target, title, payload="", preconditions=[])` | I3 (payload→NULL bila kosong), number per-target via `COALESCE(MAX(number),0)+1` dalam transaksi yang sama dengan INSERT, secrets gate di payload |
| `set_lead_half(lead, half, verdict, evidence)` | I2 (manual `ambiguous` = BLOCKED dengan pesan "oracle-exclusive"), evidence non-empty wajib, state open/mutating saja |
| `mutate_lead(lead, variable, old, new, result, evidence, plan=None, resolve=None)` | I3 (payload gate pertama), I7 (anti-repeat, BLOCKED `already tried ...`), I8 (unknown tanpa `--plan` = BLOCKED; dengan plan → precondition baru status `missing` + `followup_precondition_id` terisi), `--resolve` menandai precondition `present` |
| `next_mutation(lead)` | I11 — precondition `missing` pertama (urut id) yang (variable,value)-nya belum pernah dicoba; `None` saat habis (panggilan CLI menyarankan park, bukan error) |
| `park_lead(lead, retrigger)` | I6 — `observable :: check` wajib (separator ` :: `, dua sisi non-empty); park tanpa itu BLOCKED |
| `kill_lead(lead, t_ref, i_ref, retrigger=None)` | I5 — dua-duanya `refuted` + evidence non-empty → killed; satu sisi → auto-park + `dismissal_count++` + event `lead_kill_refused`; refusal tanpa retrigger valid = BLOCKED (lazy kill ditolak). Keputusan tambahan: retrigger opsional pada kill BERSIH juga divalidasi & disimpan (tripwire), COALESCE menjaga nilai lama |
| `promote_lead(lead, klass, severity)` | I9/I10 — kedua half `proven` + payload non-empty + target aktif; INSERT lewat `add_finding` existing (kena semua gate findings: taxonomy/phase/secrets — tidak ada bypass); `findings.lead_id` + snapshot `lead_provenance` JSON frozen; state→promoted |
| `record_oracle_verdict(lead, half, baseline, candidate)` | I12 — verdict deterministik + kedua feature JSON disimpan sebagai event kind `oracle_verdict` (return `(verdict, event_id)`); `unknown` → set-half `ambiguous` (satu-satunya jalur, I2) |
| `set_lead_payload(lead, payload)` | Isi payload lead aktif; BLOCKED pasca-promote (I9 freeze) |
| `list_leads(conn, target_id)` | — |
| `oracle_verdict(baseline, candidate)` | Fungsi murni aturan I12 (tanpa db/I/O) — bisa dites terpisah |
| `_read_oracle_feature(path, side, lead_id)` | I12/A5 — JSON parse gagal / key hilang / timing non-finite (NaN/inf via `math.isfinite`) / body_sha bukan 64-hex / status-size bukan int = BLOCKED |
| `lead_contradictions(conn, target_id)` | I15 — soft-flag `!! lead L-n still payload-less after N days` (state open, payload NULL, umur >7 hari via `julianday`) |
| `_build_provenance` | I9 — `{lead_number, mutations, preconditions_present, preconditions_refuted, parked_days, promoted_at, lead_id}` (parked_days dihitung dari pasangan event lead_parked → reopen) |

Integrasi:
- **I14** `export_brief` sekarang punya section `## Leads`: open+mutating (dengan next mutation deterministic), parked (tripwire), killed-with-retrigger (tripwire). Killed tanpa retrigger & promoted tidak ditampilkan (promoted sudah hidup sebagai finding).
- **I15** `find_contradictions` mengembalikan flag lead juga (dipanggil dari situ; brief & status otomatis ikut — tanpa double-count).

### 2.3 CLI (`app/src/huntos/cli/main.py`) — lengkap sesuai spec §3
`hunt lead add|set-half|mutate|next|park|kill|promote|list` + `hunt oracle` (argparse subparser per-aksi, pola existing; echo wajib per aksi: `lead L-n ... state=...`, `kill refused -> parked (dismissal #N)`).

`hunt oracle` menerima `--lead N` ATAU `--finding N` (exactly-one di-parse-time-validate; `--finding N` resolve `findings.lead_id` — finding tanpa lead = BLOCKED dengan pesan jelas). Sesuai catatan §5/§6: `--finding` hanya bermakna untuk finding hasil promote (yang punya lead_id).

### 2.4 Claim gate L-binding (`bridge/claim_gate.py`, I13)
- `claims()` kini mengembalikan triple `(marker, finding_id|None, lead_id|None)`. Presedensi: `PROVEN[L-n]` explicit > `PROVEN[F-n]` explicit > nearest-id bare fallback.
- **Nearest-id kini fairness race antara F-id dan L-id berdasarkan jarak** (tie → F-id, mempertahankan perilaku v0.3). Alasan desain: spec minta L-3 jangan "launder" ke F-3 lewat shared prefix; membuang L-id dari window sama saja menukar bug dengan false-veto. Race jarak menyelesaikan keduanya: `PROVEN L-3` (tak ada F-id lain di window) → bind L-3 → ditanya state lead L-3; `PROVEN ... F-9` dekat L-3 → F menang bila lebih dekat.
- `vet()`: lead-bound lolos hanya bila `leads.state='promoted'`; pesan veto menyebut `lead L-n ... says the lead is '<state>'`. **F-binding path byte-for-byte tidak berubah.**
- DB dibuka read-only seperti dulu; tanpa tabel `leads` (db lama) → row None → "lead is 'not found'" → tetap fail-closed.

### 2.5 Tests
- `app/tests/test_leads.py` — 29 test, matrix §4 [M1]–[M24] lengkap (M24 = regression end-to-end; M23 = AST-walk `open()` di 3 file — semua harus `encoding=` eksplisit atau binary; M19 = delegasi ke test_claim_gate L-binding).
- `app/tests/test_claim_gate.py` — 5 test L-binding baru: open→BLOCKED, promoted→lolos, F-binding tak berubah (termasuk: finding hasil promote masih `theoretical` di ladder → F-claim tetap diveto), `PROVEN[L-n]` menang atas F-id terdekat, state live dibaca (killed → veto).
- `app/tests/test_enforcement.py` — 1 test disesuaikan (lihat §4.4).

## 3. Keputusan deviasi/penafsiran spec (semua didokumentasikan, tidak diam-diam)

1. **`record_poc_run` return `int` (event id), bukan digest str.** Spek I12 butuh `oracle_event_id` dan audit kebutuhan event-id stabil; poc_run adalah satu-satunya writer event yang di-return nilainya. Konsekuensi: 1 test lama (`test_record_poc_run_logs_event_and_returns_digest`) disesuaikan — memverifikasi event id int + detail event tetap membawa `poc sha256:`. Tidak ada pemanggil lain yang terdampak.
2. **`hunt oracle --finding N`** diimplementasi seperti di atas (resolve lead_id dari finding). Spek hanya menuliskan sintaks; ini penafsiran yang mencatat alasan di docstring.
3. **Kill bersih dengan `--retrigger` opsional**: retrigger tervalidasi dan disimpan (tripwire di brief, I14). Spek menempatkan `--retrigger` hanya pada jalur refusal; ini superset yang koheren dengan I14 dan tidak mengubah aturan refusal.
4. **Bare-marker L-binding = fairness race jarak** (lihat §2.4) alih-alih "L selalu kalah". Test `test_lead_binding_does_not_launder_into_finding_id` membuktikan kasus spesifikasi: `PROVEN L-3 ... (see F-1 ...)` → bind L-3, veto menyebut state lead.
5. **`payload=""` → NULL** saat add (I3 bilang "boleh NULL saat add"); `mutate` pertama tetap diblokir hingga payload diisi — jalur pengisiannya: `hunt lead add --payload ...` atau `hunt lead set --lead N --payload ...` (lihat 5b di §4).
6. **Pesanan pemeriksaan `promote_lead`**: state-promoted dicek lebih dulu ("already promoted (finding #n)") sebelum gate unproven — superset pesan yang lebih jelas; urutan gate lain sesuai I10.
7. **Tidak termasuk** (sesuai ruang lingkup spec §0): push/CI/M4 stats/checklist B (`pr/AUDIT-CHECKLIST-leads.md` — deliverable Subagent B).

## 4. Jebakan yang nyaris (atau sudah) terjadi — untuk auditor B

1. CHECK `impact_verdict` ditulis sebagai daftar 4-state sendiri (tidak copy-paste dari trigger) — sesuai peringatan §5. Grep-able: dua blok CHECK terpisah di SCHEMA.
2. `datetime('now')` di semua DEFAULT; pembaruan `updated_at` memakai `datetime('now')` di UPDATE (bukan 'command').
3. `old_value` DI LUAR unique key — test M5 membuktikan `role: admin->root` sah setelah `guest->admin`.
4. **Test lama yang menyentuh return `record_poc_run`**: `test_enforcement.py::test_record_poc_run_logs_event_and_returns_digest` — diubah ke event-id assertion (ini satu-satunya perubahan test lama, disengaja + didokumentasikan; perubahan perilaku db, bukan cherry-pick).
5. Bug yang ditemukan saat run dan diperbaiki: `days_parked` UnboundLocal di `_build_provenance` (lead tak pernah park); payload `''` tersimpan sebagai `''` bukan NULL; M22 awalnya menambah finding di phase `scoring` (kena phase gate v0.3 — memang benar; test diubah menelusuri phase dengan sah).

5b. **`hunt lead set --lead N --payload "..."`** adalah penambahan CLI kecil DI ATAS permukaan §3 (bukan deviasi): pesan BLOCKED payload-gate merujuk perintah itu, jadi subcommand `set` ditambahkan agar rujukan hidup. db-side: `set_lead_payload` (BLOCKED pasca-promote, I9). Diverifikasi end-to-end: add tanpa payload → mutate BLOCKED → set payload → mutate sukses.
6. `hunt oracle --lead N` pada lead `promoted` = BLOCKED "the oracle runs on open or mutating leads" (oracle bukan alat untuk menulis-ulang verdict lead yang sudah jadi finding).

## 5. Transkrip smoke CLI (run nyata, dipotong)

```
lead L-1 added (number 1, state=open) on target #1: Password reset poisons session
oracle verdict for lead #1 trigger: confirmed (oracle_verdict event #9 stored with both feature JSONs)
lead L-1 trigger set to proven
lead L-1 impact -> proven (state=open, trigger=proven, impact=proven)
lead L-1 promoted -> finding #1 [high] Access (provenance snapshot frozen)
claim gate PROVEN[L-1]: rc= 0 claim gate: no unbacked claims
```
Jalur guard (semua rc=2, pesan BLOCKED menyebut `lead L-n`):
```
BLOCKED: lead L-3 kill refusal requires --retrigger (the auto-park refuses to park without a tripwire — a park without a retrigger is a lazy kill)
BLOCKED: lead L-3 retrigger must be 'observable :: check' (separator' :: ' required, both sides non-empty); got: 'bad format'
kill refused -> parked (dismissal #1) — lead L-3 tripwire: webhook pinged externally :: recheck dns logs
BLOCKED: lead L-3 is parked — only open or mutating leads can be killed
BLOCKED: lead L-1 is promoted — the oracle runs on open or mutating leads
BLOCKED: lead L-3 is parked — only open or mutating leads promote
```
Brief (`## Leads` baru):
```
L-1 [mutating] (refuted/proven) Password reset poisons session — next: mail='deliverable'
L-2 [open] (untraced/ambiguous) Timing oracle on /admin — next: none left — consider park (with a retrigger)
```

## 6. Definisi done — checklist

- [x] Schema §1 persis (tiga tabel + migrasi guarded idempotent)
- [x] I1–I15 masing-masing punya test hijau
- [x] CLI §3 lengkap + echo per aksi
- [x] Claim gate L-binding (I13), F-binding tak berubah
- [x] Test matrix §4 24-butir lengkap di `tests/test_leads.py` + L-binding di `tests/test_claim_gate.py`
- [x] Full suite hijau: **pytest 160 passed**, unittest OK (Linux)
- [x] Windows-safe: encoding utf-8 eksplisit di semua open() baru (dites otomatis oleh M23), tanpa locale dependency, tanpa dep baru
- [x] Tidak ada commit/push/CI/`.push_api.py`/SOUL yang disentuh
- [x] Catatan implementasi = file ini

---

## 7. Arbitrase (parent, round 1) — B-L1 + B-L27 confirmed & patched

Auditor B menyerahkan `pr/AUDIT-CHECKLIST-leads.md` (27 temuan B-L + 9 regresi B-R).
Arbiter mereproduksi P1/P2 kunci terhadap KODE LANDED (bukan prototype) di `/tmp/arbiter/`:

- **B-L1 (P1) CONFIRMED + FIXED** — `set_lead_half` manual 'proven' di atas oracle-'ambiguous'
  diterima (laundering oracle verdict → promote fuel). Fix di `_set_lead_half`:
  manual path (`oracle_event_id=None`) atas half yang masih `ambiguous` = BLOCKED
  ("set by the oracle — rerun the oracle, or refute it with the oracle first").
  Regression pin: `test_bl1_manual_proven_over_oracle_ambiguous_blocked`.
- **B-L27 (P2) CONFIRMED + FIXED** — promote in wave-gap → finding `wave_id=NULL` →
  wave economics buta (arbiter: `findings_new=0` + economic-stop misfire hazard).
  Fix dua arah: `promote_lead` menegaskan NULL saat gap, dan `open_wave` RETRO-LINK
  findings gap (`wave_id IS NULL`, non-overturned) ke wave yang baru dibuka.
  Regression pin: `test_bl27_promote_in_gap_counts_in_next_wave`.
- **B-L5 (P1) ALREADY CLOSED by A** — duplicate `--plan` = BLOCKED dengan pesan
  bernama (arbiter reproduce: "an unknown must give birth to a NEW pair").
- **B-L9 (P2) PARTIALLY DISPUTED** — kedua jalur `PROVEN[L-1]` (lead open) dan
  laundering `Lead #1 ... PROVEN.` di-veto oleh claim gate landed (rc=2, arbiter
  reproduce). Klaim "lolos" tidak ter-reproduksi pada HEAD saat arbitrase; sisa
  temuan B-L9 (divergence bar L vs F untuk lead promoted dengan finding theoretical)
  tetap terbuka sebagai design note, bukan blocker.

Suite setelah patch: **pytest 162 passed** (160 + 2 regression pins). unittest OK.
Sisa temuan B (P2/P3) terdokumentasi di checklist untuk round 2 — tidak memblokir merge.
