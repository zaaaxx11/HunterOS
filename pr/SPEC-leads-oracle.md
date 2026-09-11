# SPEC — Lead Lifecycle + Observation Oracle untuk HUNT-OS v0.4

Status: DRAFT v1 (dibaca oleh implementer A dan auditor B; perubahan lewat arbiter).
Ruang lingkup: schema + db functions + CLI + tests. TIDAK termasuk: push/CI changes/M4 stats.

## 0. Konteks repo

- Repo: /root/Hunter (mirror remote main, 57 files, CI hijau dual-OS, 126 tests).
- App: /root/Hunter/app (stdlib-only, zero pip). Tests: PYTHONPATH=src python3 -m pytest tests/ -q (lokal) / unittest (CI).
- Gaya wajib: pesan BLOCKED: di ValueError; fail-closed; semua file write/read encoding='utf-8' eksplisit; tidak boleh locale-dependent; echo feedback per aksi (pola add_finding yang ada).
- JANGAN: git commit/push, ubah .push_api.py, ubah CI, install apapun.

## 1. Skema (SQL final — tanda tangan detail di §5)

```sql
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_id INTEGER NOT NULL REFERENCES targets(id),
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  payload TEXT,                                -- boleh NULL saat add (I3), wajib sebelum mutate pertama (I4)
  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','mutating','parked','killed','promoted')),
  trigger_verdict TEXT NOT NULL DEFAULT 'untraced'
    CHECK (trigger_verdict IN ('untraced','proven','refuted','ambiguous')),
  impact_verdict TEXT NOT NULL DEFAULT 'untraced'
    CHECK (impact_verdict IN ('untraced','proven','refuted','ambiguous')),
  trigger_evidence TEXT,
  impact_evidence TEXT,
  dismissal_count INTEGER NOT NULL DEFAULT 0,  -- dihitung tiap kill ditolak (I6)
  retrigger_condition TEXT,                    -- format 'observable :: check' (I7)
  promoted_finding_id INTEGER,                 -- diisi saat promote
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (target_id, number)
);

CREATE TABLE IF NOT EXISTS lead_preconditions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER NOT NULL REFERENCES leads(id),
  variable TEXT NOT NULL,
  value TEXT NOT NULL,
  description TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'missing' CHECK (status IN ('missing','present','refuted')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (lead_id, variable, value)
);

CREATE TABLE IF NOT EXISTS lead_mutations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lead_id INTEGER NOT NULL REFERENCES leads(id),
  variable TEXT NOT NULL,
  old_value TEXT,                              -- SENGAJA di luar UNIQUE key (I8)
  new_value TEXT NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('advanced','unchanged','refuted','unknown')),
  evidence TEXT NOT NULL,
  followup_precondition_id INTEGER,            -- wajib terisi saat result='unknown' (I9)
  oracle_event_id INTEGER,                     -- wajib terisi saat result di-set via oracle
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (lead_id, variable, new_value)        -- anti-repeat (I8)
);
```

Migrasi findings (guarded, idempotent):
```sql
ALTER TABLE findings ADD COLUMN lead_id INTEGER;
ALTER TABLE findings ADD COLUMN lead_provenance TEXT;  -- snapshot JSON FROZEN saat promote (I10)
```
(Cek pragma table_info dulu; kalau kolom sudah ada, skip. Legacy DB tanpa kolom tetap jalan — kolom NULL.)

## 2. Invariant (load-bearing — tiap invariant punya test)

- **I1 Dua-half independen**: trigger_verdict & impact_verdict masing-masing `untraced|proven|refuted|ambiguous`. CHECK dua-duanya benar (jangan copy-paste salah referensi).
- **I2 Ambiguous oracle-exclusive**: `ambiguous` HANYA bisa dipasang oleh `record_oracle_verdict` (ada oracle_event_id di belakangnya). `set-half --verdict ambiguous` manual = BLOCKED.
- **I3 Payload gate (b)**: payload boleh kosong saat add (recon-origin legal); `mutate` pertama pada lead payload-kosong = BLOCKED "payload required before the mutation loop".
- **I4 State gate**: mutate/open-wave-style aksi pada target `archived` = BLOCKED (konsisten A2). kill/park/mutate/set-half hanya di state yang sah.
- **I5 Kill guard**: kill butuh KEDUA half `refuted` + evidence non-empty KEDUANYA. Satu sisi saja → TOLAK kill: auto-park (dengan retrigger dari argumen kill, gate yang sama), `dismissal_count++`, event `lead_kill_refused`. Kill refusal tanpa retrigger valid = BLOCKED (park tanpa retrigger = lazy kill, I7).
- **I6 Park wajib retrigger testable**: `--retrigger` wajib, format `observable :: check` (separator ` :: ` wajib, kedua sisi non-empty). Park tanpa itu = BLOCKED.
- **I7 Anti-repeat**: `UNIQUE(lead_id, variable, new_value)` — repeat kombinasi = BLOCKED. old_value di luar key.
- **I8 Unknown-consumption (anti-starvation)**: mutation `result='unknown'` WAJIB melahirkan precondition baru (`--plan "variable|value|deskripsi"`) yang langsung di-INSERT (status missing), dan `followup_precondition_id` terisi. Tanpa plan = BLOCKED. Jadi loop tidak pernah buntu: unknown mengonsumsi pair DAN melahirkan pair.
- **I9 Provenance frozen**: promote men-SNAPSHOT (denormalized) ke findings.lead_provenance: `{"lead_number":N,"mutations":<count>,"preconditions_present":x,"preconditions_refuted":y,"parked_days":d,"promoted_at":ts,"lead_id":id}`. Setelah promote, edit lead TIDAK mengubah snapshot (history yang bisa ditulis-ulang = bukan history).
- **I10 Promote gate**: kedua half `proven` + payload non-empty + target tidak archived + klass di taxonomy + severity di allow-list → INSERT finding via add_finding yang ada (jadi kena semua gate findings), state lead → promoted, promoted_finding_id terisi. Klausa `--klass`/`--severity` wajib.
- **I11 Deterministic next**: `hunt lead next` = precondition pertama `status='missing'` yang `(variable,value)`-nya belum pernah dicoba di lead_mutations (urut id). Kalau habis dan lead open → saran park (dengan pesan, bukan error).
- **I12 Oracle rules (deterministik, bukan feeling)**: input dua file JSON feature: `{"status":<int>,"timing_ms":<finite number>,"body_sha":<64hex>,"size":<int>}`. Validasi: JSON parse gagal / key hilang / timing non-finite (NaN/inf — pelajaran A5: math.isfinite) = BLOCKED. Verdict:
  - `delta_status = c.status != b.status`; `delta_body = c.body_sha != b.body_sha`
  - `timing_anomaly = (c.timing_ms >= 3*max(b.timing_ms,1.0)) AND (c.timing_ms - b.timing_ms >= 500.0)`
  - Jika delta_status ATAU delta_body: `timing_anomaly → unknown`, selain itu → `confirmed`
  - Jika tidak ada delta: `timing_anomaly → unknown`, selain itu → `refuted`
  Verdict + kedua feature JSON disimpan sebagai event (artifact_type `oracle_verdict`, detail JSON) → kembali (verdict, event_id). UNKNOWN → set-half `ambiguous` sah pada half yang diminta.
- **I13 Claim gate L-binding**: marker (PROVEN/EXPLOITABLE/admin takeover) yang ter-bind ke `L-<n>` (pola `L-\d+`, BUKAN `#n` — hindari tabrakan dengan finding) lolos hanya jika lead `state='promoted'`; selain itu BLOCKED dengan pesan state. Perilaku finding (#F-n) tidak berubah.
- **I14 Brief**: `export_brief` menambah: leads open+mutating (dengan next mutation), parked (tripwire table: retrigger), killed-with-retrigger (tripwire). Killed tanpa retrigger & promoted → tidak di brief (promoted sudah hidup sebagai finding).
- **I15 Contradiction baru**: `find_contradictions` soft-flag lead `open` berumur >7 hari payload-kosong: "lead L-n still payload-less after N days".

## 3. CLI surface (main.py)

```
hunt lead add     --target T --title "..." [--payload "..."] [--precondition "var|value|deskripsi"] (boleh berulang)
hunt lead set-half --lead N --half trigger|impact --verdict proven|refuted --evidence "..."
hunt lead mutate  --lead N --variable v --old o --new n --result advanced|unchanged|refuted|unknown
                  --evidence "..." [--plan "var|value|deskripsi"] [--resolve <precondition_id>]
hunt lead next    --lead N
hunt lead park    --lead N --retrigger "observable :: check"
hunt lead kill    --lead N --trigger-refutation "..." --impact-refutation "..." [--retrigger "..."]
hunt lead promote --lead N --klass <taxonomy> --severity critical|high|medium|low|info
hunt lead list    --target T
hunt oracle       --lead N|--finding N --half trigger|impact --baseline b.json --candidate c.json
```
Echo wajib per aksi: id (L-n), state baru, dan hasil guard (mis. "kill refused → parked (dismissal #2)").

## 4. Test matrix (semua HARUS ada di tests/test_leads.py + beberapa menyentuh test_enforcement)

1. add tanpa payload OK (state open, echo L-n) — I3
2. add dengan 2 precondition OK; UNIQUE(target,number) naik per target
3. mutate pertama tanpa payload = BLOCKED — I3
4. mutate dengan payload: state → mutating; result advanced tersimpan
5. mutate repeat (var,new_value) sama = BLOCKED — I7; var sama value beda = OK
6. result unknown tanpa --plan = BLOCKED — I8; dengan plan: precondition baru status missing + followup_precondition_id terisi
7. set-half ambiguous manual = BLOCKED — I2
8. oracle: baseline==candidate → refuted + event tersimpan; set-half ambiguous setelah oracle unknown OK (I12)
9. oracle timing anomaly tanpa delta → unknown; delta body tanpa anomaly → confirmed
10. oracle file rusak / key hilang / timing NaN → BLOCKED — I12 (A5 lesson)
11. kill dengan 1 refutasi → ditolak, auto-park, dismissal_count=1, event lead_kill_refused — I5
12. kill dengan 2 refutasi OK; kill di state parked/promoted = BLOCKED
13. kill refusal tanpa --retrigger = BLOCKED — I6
14. park tanpa retrigger / retrigger tanpa ' :: ' = BLOCKED — I6
15. promote sebelum kedua half proven = BLOCKED; setelah dua-duanya proven → finding dibuat, provenance snapshot benar, lead promoted — I9/I10
16. promote klass di luar taxonomy = BLOCKED (kena gate findings yang ada)
17. aksi lead di target archived = BLOCKED — I4
18. next: deterministik urut id; habis → saran park — I11
19. claim gate: "PROVEN" dekat L-1 saat lead open → BLOCKED; setelah promoted → lolos; F-binding tak berubah — I13
20. brief menampilkan open/parked(killed-with-retrigger) sesuai I14
21. provenance TIDAK berubah setelah lead diedit pasca-promote — I10
22. legacy DB tanpa kolom lead_id: ALTER guarded jalan, add_finding lama tetap OK
23. semua file I/O utf-8 eksplisit (Windows-safe; CI windows-latest)
24. full suite lama tetap hijau (regression)

## 5. Detail tanda tangan (yang gampang salah — JANGAN)

- CHECK impact_verdict harus list 4-state sendiri (bug copy-paste = I1 mati diam-diam).
- dismissal_count SATU deklarasi (duplicate deklarasi = SQL gagal).
- `datetime('now')` (bukan 'command').
- old_value di LUAR unique key.
- number per target: `SELECT COALESCE(MAX(number),0)+1 FROM leads WHERE target_id=?` dalam transaksi yang sama dengan INSERT.
- Semua BLOCKED: pesan menyebut obyek: `BLOCKED: lead L-3 ...`.
- FaKT: kalau add_finding existing menuntut wave aktif dsb., promote harus melewatinya secara sah (jangan bypass) — kalau konteks wave dipersyaratkan, promote wajib menerima --wave atau gagal dengan pesan jelas. Dokumentasikan pilihan di docstring.

## 6. Deliverables

- db functions di app/src/huntos/core/db.py (lanjutan idiom file), CLI di app/src/huntos/cli/main.py, tests di app/tests/test_leads.py (+ klaim-gate test di test_claim_gate.py).
- FULL suite hijau di box ini (Linux) dan Windows-safe (utf-8, tanpa locale dependency).
- Catatan implementasi + hasil run: /root/Hunter/pr/IMPL-NOTES-leads.md (A), checklist serangan: /root/Hunter/pr/AUDIT-CHECKLIST-leads.md (B).
- TANPA push/commit. Laporkan hasil nyata, bukan rencana.
