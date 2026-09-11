"""SQLite spine - state that cannot lie.

Enforcements (framework rules baked into the database):
  - finding.proven-live requires evidence_ref AND poc_path (no PoC = no proof)
  - promotion requires an EXECUTED PoC: a poc_run event (hunt poc run) whose
    recorded sha256 matches the promoted file — existence is not execution
  - proven-live is trigger-enforced on EVERY writer, app or raw sqlite: the
    verifier, adversary, and poc-run events must exist before the UPDATE lands
  - ladder transitions are monotone: theoretical < in-code < proven-live
  - overturned is terminal; overturned findings are never deleted (audit trail)
  - wave N+1 cannot be opened before wave N has a re-audit + ev_verdict
  - target phase transitions follow the pipeline order (no phase skipping)
  - a target cannot leave scoring with ev_score <= 0 (score gate); ev_score
    must be a finite number (NaN/inf are refused at the source)
  - leaving recon/classify/report requires the phase artifact on disk
    (FRAMEWORK.md L2 artifact contract: surface_map / attack_plan / disclosure_report)
  - leaving hunting requires at least one closed wave; leaving verify requires
    zero in-code findings (promote, overturn, or stay theoretical)
  - findings and waves belong to the hunting or verify phase; each artifact
    belongs to the phase that owns it (surface_map: recon, attack_plan:
    classify, disclosure_report: report)
  - every finding records its falsifier — the evidence that would DISPROVE it
  - surfaces are the Architect's map as data (endpoint / trust_boundary /
    invariant / component): a finding or lead can pin itself to one, and the
    blind spots (trust boundaries with no lead AND no finding) are computed
    mechanically by surface_coverage — displayed in the brief, never blocking
  - chains link findings/leads into an ordered gadget graph: step refs must
    exist, one step per position, a gadget appears at most once per chain,
    and pattern novelty is computed LEDGER-LOCALLY (never seen in your own
    recorded history — the system cannot see the outside world)
  - archived targets are locked: no findings, waves, promotions, verifications,
    overturns, re-audits, or wave closes. Lessons stay allowed on purpose:
    memory additions are not history rewrites.
  - archiving from report/retro requires the disclosure_report artifact;
    the economic stop from hunting stays exempt
  - finding.klass must exist in the taxonomies table (label discipline):
    raw-SQL cheats are trigger-blocked; new classes grow only at retro
  - rules of engagement per target, DEFAULT-DENY for mutate: a finding with
    action='mutate' cannot reach proven-live unless the target's RoE allows it
  - raw secrets are refused at the gates (assert_no_secrets); stored text is
    conservatively redacted (redact) as a safety net
  - conductor domain (blueprint §5): sessions/attempts/incidents are
    kernel-owned state machines — status value sets are CHECK-pinned, the
    transition graphs are enforced in the public API, and the status columns
    are trigger-guarded against naive raw writers (same app-session guard as
    the findings evidence columns). Ids S-<n>/A-<n>/I-<n> are minted by the
    kernel only, globally, and never reused: a retry is a NEW attempt id with
    parent_attempt_id pointing at the attempt it retries.

Honest boundary: the session guard and the triggers stop naive raw sessions and
bind every writer (app or raw sqlite) to the same evidence bar — but a hostile
process that registers the guard function (one line) or edits the db file
directly defeats the guard, and forged events satisfy the evidence triggers by
design. The triggers raise the bar; they do not certify truth. The db file is
the operator's seal; the CLI is the door.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import ARTIFACT_TYPES, KLASS, PHASE_ARTIFACTS, PHASE_RANK, PHASES, ROE_ACTIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    chain TEXT DEFAULT 'evm',
    age_days INTEGER DEFAULT 0,
    tvl_usd REAL DEFAULT 0,
    phase TEXT DEFAULT 'scoring',
    ev_score REAL DEFAULT 0,
    archive_reason TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    CHECK (phase IN ('scoring','recon','classify','hunting','verify','report','retro','archived'))
);

-- Surfaces (capability stack): the Architect's map becomes DATA. A surface is
-- a named place the hunt decided to look at (or decided existed); the blind
-- spots — trust boundaries nothing ever pointed at — fall out of the ledger
-- mechanically instead of living in someone's head.
CREATE TABLE IF NOT EXISTS surfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    kind TEXT NOT NULL CHECK (kind IN ('endpoint','trust_boundary','invariant','component')),
    name TEXT NOT NULL,
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    title TEXT NOT NULL,
    klass TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    ladder_status TEXT DEFAULT 'theoretical',
    evidence_ref TEXT DEFAULT '',
    poc_path TEXT DEFAULT '',
    poc_sha256 TEXT DEFAULT '',
    falsifier TEXT DEFAULT '',
    overturned_by TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    action TEXT DEFAULT 'read',
    wave_id INTEGER REFERENCES waves(id),
    surface_id INTEGER REFERENCES surfaces(id),
    created_at TEXT DEFAULT (datetime('now')),
    CHECK (ladder_status IN ('theoretical','in-code','proven-live','overturned')),
    CHECK (severity IN ('critical','high','medium','low','info'))
);

CREATE TABLE IF NOT EXISTS waves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    number INTEGER NOT NULL,
    lanes TEXT DEFAULT '',
    findings_new INTEGER DEFAULT 0,
    reaudit_done INTEGER DEFAULT 0,
    ev_verdict TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(target_id, number),
    CHECK (ev_verdict IN ('','continue','exhausted','pivot'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_target TEXT NOT NULL,
    pattern TEXT NOT NULL,
    scope TEXT DEFAULT 'skill',
    notes TEXT DEFAULT '',
    target_id INTEGER REFERENCES targets(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules_of_engagement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL UNIQUE REFERENCES targets(id),
    hosts TEXT DEFAULT '',
    actions TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS target_source (
    target_id INTEGER PRIMARY KEY REFERENCES targets(id),
    kind TEXT NOT NULL CHECK (kind IN ('url','github','folder')),
    canonical TEXT NOT NULL,
    display TEXT NOT NULL,
    workspace TEXT NOT NULL,
    revision TEXT NOT NULL,
    authorization_note TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Label discipline: the klass allow-list lives as DATA (not CHECK constraints)
-- so taxonomy growth at retro never needs a schema migration.
CREATE TABLE IF NOT EXISTS taxonomies (
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT DEFAULT 'seed',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(kind, value)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER,
    finding_id INTEGER,
    kind TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Lead lifecycle (v0.4): the observation ledger. A lead is a hypothesis with
-- two independent halves (trigger / impact), each traced separately; a lead
-- becomes a finding only through promote (both halves proven), and dies only
-- through kill (both halves refuted) or park (with a testable retrigger).
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_id INTEGER NOT NULL REFERENCES targets(id),
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  payload TEXT,                                -- may be NULL at add (recon-origin legal); required before the first mutate
  state TEXT NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','mutating','parked','killed','promoted')),
  trigger_verdict TEXT NOT NULL DEFAULT 'untraced'
    CHECK (trigger_verdict IN ('untraced','proven','refuted','ambiguous')),
  impact_verdict TEXT NOT NULL DEFAULT 'untraced'
    CHECK (impact_verdict IN ('untraced','proven','refuted','ambiguous')),
  trigger_evidence TEXT,
  impact_evidence TEXT,
  dismissal_count INTEGER NOT NULL DEFAULT 0,  -- incremented on every refused kill
  retrigger_condition TEXT,                    -- format 'observable :: check'
  promoted_finding_id INTEGER,                 -- set on promote
  surface_id INTEGER REFERENCES surfaces(id),  -- optional pin to the Architect's map
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
  old_value TEXT,                              -- deliberately OUTSIDE the unique key: re-arrivals at the same old value are legal
  new_value TEXT NOT NULL,
  result TEXT NOT NULL CHECK (result IN ('advanced','unchanged','refuted','unknown')),
  evidence TEXT NOT NULL,
  followup_precondition_id INTEGER,            -- required when result='unknown' (the loop never dead-ends)
  oracle_event_id INTEGER,                     -- set when the result was set via the oracle
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (lead_id, variable, new_value)        -- anti-repeat
);

-- Chains (capability stack): the Chainer's graph becomes the ledger's object.
-- A chain is an ordered sequence of steps pointing at findings ( klass carried
-- by the finding) or leads (pre-classification hypotheses, no klass of their
-- own). Novelty of the chain's PATTERN is checkable against ledger history.
CREATE TABLE IF NOT EXISTS chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    name TEXT NOT NULL,
    entry TEXT DEFAULT '',
    impact TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chain_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id INTEGER NOT NULL REFERENCES chains(id),
    position INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('finding','lead')),
    ref_id INTEGER NOT NULL,
    UNIQUE(chain_id, position)
);

CREATE TRIGGER IF NOT EXISTS findings_no_tamper
BEFORE UPDATE ON findings
WHEN OLD.ladder_status != NEW.ladder_status
  OR OLD.evidence_ref != NEW.evidence_ref
  OR OLD.poc_path != NEW.poc_path
  OR OLD.poc_sha256 != NEW.poc_sha256
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: evidence columns are session-protected (tamper attempt)')
    WHERE NOT huntos_session_guard_ok();
END;

-- A1: the proven-live evidence bar, enforced on EVERY writer (app or raw sqlite).
-- Honest limit: a forger can INSERT the evidence events raw too — the trigger
-- binds all writers to the same bar, it cannot certify that the evidence is true.
CREATE TRIGGER IF NOT EXISTS findings_proven_requires_evidence
BEFORE UPDATE OF ladder_status ON findings
WHEN NEW.ladder_status = 'proven-live' AND OLD.ladder_status != 'proven-live'
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: proven-live requires verifier, adversary, and poc-run events')
    WHERE NOT EXISTS (SELECT 1 FROM events WHERE finding_id = NEW.id AND kind = 'verifier_pass')
       OR NOT EXISTS (SELECT 1 FROM events WHERE finding_id = NEW.id AND kind = 'adversary_pass')
       OR NOT EXISTS (SELECT 1 FROM events WHERE finding_id = NEW.id AND kind = 'poc_run');
END;

CREATE TRIGGER IF NOT EXISTS targets_phase_guard
BEFORE UPDATE OF phase ON targets
WHEN OLD.phase != NEW.phase
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: illegal phase transition (backward or skip)')
    WHERE (
      CASE NEW.phase
        WHEN 'recon'     THEN OLD.phase != 'scoring'
        WHEN 'classify'  THEN OLD.phase != 'recon'
        WHEN 'hunting'   THEN OLD.phase != 'classify'
        WHEN 'verify'    THEN OLD.phase != 'hunting'
        WHEN 'report'    THEN OLD.phase != 'verify'
        WHEN 'retro'     THEN OLD.phase != 'report'
        WHEN 'archived'  THEN 0
        ELSE 1
      END
    );
END;

CREATE TRIGGER IF NOT EXISTS findings_klass_guard_insert
AFTER INSERT ON findings
WHEN NOT EXISTS (SELECT 1 FROM taxonomies WHERE kind='klass' AND value=NEW.klass)
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: klass not in taxonomy');
END;

CREATE TRIGGER IF NOT EXISTS findings_klass_guard_update
BEFORE UPDATE OF klass ON findings
WHEN NOT EXISTS (SELECT 1 FROM taxonomies WHERE kind='klass' AND value=NEW.klass)
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: klass not in taxonomy');
END;

-- Conductor domain (blueprint §5: session contract and persistence). The
-- conductor's operational state lives in the ledger as DATA: sessions
-- (S-<n>), attempts (A-<n>), incidents (I-<n>). The law: nothing writes to
-- these tables except through this module's public API — the orchestrator
-- never needs raw SQL. The CHECK constraints below pin the exact value sets
-- against raw writers; the transition GRAPHS are enforced in Python by
-- set_conductor_session_status / set_conductor_attempt_status; the tamper
-- triggers reuse the app-session guard (huntos_session_guard_ok) so a naive
-- raw sqlite session cannot flip conductor state either (same honest boundary
-- as findings_no_tamper). Ids are minted by the kernel (see
-- _mint_conductor_id): global, sequential, never reused — retries get a NEW
-- attempt id and point parent_attempt_id at the attempt they retry.
CREATE TABLE IF NOT EXISTS conductor_session (
    id TEXT PRIMARY KEY,                         -- 'S-<n>', minted by the kernel
    target_id INTEGER REFERENCES targets(id),    -- the hunt this session serves
    workspace TEXT DEFAULT '',
    db_fingerprint TEXT NOT NULL,                -- which ledger the session runs against
    status TEXT NOT NULL DEFAULT 'preflight'
      CHECK (status IN ('preflight','running','degraded','paused','completed','recovery_required','aborted')),
    started_at TEXT,
    ended_at TEXT,
    budget INTEGER,
    adapter_id TEXT,
    adapter_version TEXT,
    adapter_registry_name TEXT,
    model_profile_hash TEXT,
    skills_lock_hash TEXT,
    rounds INTEGER,                              -- declared round count of the managed loop (nullable)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conductor_attempt (
    id TEXT PRIMARY KEY,                         -- 'A-<n>', minted by the kernel
    session_id TEXT NOT NULL REFERENCES conductor_session(id),
    lane TEXT NOT NULL CHECK (lane IN ('architect','red_teamer','fuzz_engineer','chainer')),
    round INTEGER NOT NULL,
    parent_attempt_id TEXT,                      -- set on retries (a retry is a NEW id)
    model_profile TEXT,
    prompt_hash TEXT,
    status TEXT NOT NULL DEFAULT 'ready'
      CHECK (status IN ('ready','running','completed','research_blocked','interrupted','uncertain','cancelled')),
    started_at TEXT,
    ended_at TEXT,
    usage INTEGER DEFAULT 0,                     -- cumulative tokens (record_attempt_usage)
    error_class TEXT                             -- failure vocabulary; only on failure outcomes
      CHECK (error_class IN ('auth','rate_limit','crash','protocol','disk_full','timeout','cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conductor_incident (
    id TEXT PRIMARY KEY,                         -- 'I-<n>', minted by the kernel
    session_id TEXT NOT NULL REFERENCES conductor_session(id),
    class TEXT NOT NULL,
    detail TEXT,
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS conductor_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES conductor_session(id),
    attempt_id TEXT NOT NULL REFERENCES conductor_attempt(id),
    lane TEXT NOT NULL CHECK (lane IN ('architect','red_teamer','fuzz_engineer','chainer')),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
      'lane_start','tool_request','tool_result','assistant_output','usage',
      'claim_gate','completion','error'
    )),
    detail TEXT NOT NULL DEFAULT '',
    operation_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(attempt_id, sequence)
);

-- Status flips are API-protected on EVERY writer (app or raw sqlite): a raw
-- session that never registered the guard function cannot flip conductor
-- state, exactly like the findings evidence columns above.
CREATE TRIGGER IF NOT EXISTS conductor_session_status_tamper_guard
BEFORE UPDATE OF status ON conductor_session
WHEN OLD.status != NEW.status
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: conductor session status is API-protected (tamper attempt)')
    WHERE NOT huntos_session_guard_ok();
END;

CREATE TRIGGER IF NOT EXISTS conductor_attempt_status_tamper_guard
BEFORE UPDATE OF status ON conductor_attempt
WHEN OLD.status != NEW.status
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED: conductor attempt status is API-protected (tamper attempt)')
    WHERE NOT huntos_session_guard_ok();
END;
"""


# --- secret hygiene ---
# Two layers, on purpose:
#   assert_no_secrets() REFUSES raw secrets at the gates (store the fact, not
#   the secret); redact() is the conservative safety net for text that gets
#   stored anyway (log_event) or displayed (export_report).

_SECRET_PATTERNS = [
    # PEM private key blocks (any flavor: RSA, EC, OPENSSH, ...)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "[REDACTED-PRIVATE-KEY]"),
    # JWTs: three base64url segments
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "[REDACTED-JWT]"),
    # AWS access key ids
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED-AWS-KEY]"),
    # GitHub tokens (ghp_/gho_/ghu_/ghs_/ghr_)
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED-GH-TOKEN]"),
    # Generic sk- style API keys
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED-KEY]"),
]

# Credential assignments: keep the field name, drop the value.
# password/passwd values are ALWAYS redacted; token/secret/api_key values only
# when >= 12 chars, so honest prose like "token: present in table users" or
# "token=short-lived" passes through untouched (false-positive guard).
_ASSIGNMENT_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd)\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(token|secret|api[_-]?key)\s*[=:]\s*(\S{12,})"), r"\1=[REDACTED]"),
]

_SECRET_REJECT_MSG = (
    "contains what looks like a raw secret — "
    "store the fact ('reset token present in table X'), not the secret"
)


def redact(text: str) -> str:
    """Conservative redaction: known secret formats + credential assignments.

    Keeps the field name, drops the value: "password=hunter2" becomes
    "password=[REDACTED]". Short/ordinary values are left alone.
    """
    if not text:
        return text
    for pattern, label in _SECRET_PATTERNS:
        text = pattern.sub(label, text)
    for pattern, repl in _ASSIGNMENT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def assert_no_secrets(text: str, field: str) -> None:
    """Refuse raw secrets at the gates — store the fact, not the secret."""
    if not text:
        return
    for pattern, _label in _SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"BLOCKED: {field} {_SECRET_REJECT_MSG}")
    for pattern, _repl in _ASSIGNMENT_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"BLOCKED: {field} {_SECRET_REJECT_MSG}")


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = os.environ.get("HUNT_DB", os.path.expanduser("~/.huntos/hunt.db"))
    # bare filenames have no directory part — creating it would raise
    d = os.path.dirname(db_path)
    if d:
        os.makedirs(d, exist_ok=True)
    # timeout: concurrent sessions wait for the writer instead of dying with
    # 'database is locked'; WAL (below) lets readers proceed during a write.
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.execute("PRAGMA foreign_keys = ON")
        # Per-session guard: authorizes the app's own protected updates (ladder, phase).
        # SQLite forbids a main-database trigger from referencing temp tables directly,
        # so the findings_no_tamper trigger consults the huntos_session_guard_ok()
        # function instead. That function is registered ONLY on app sessions, so a
        # naive raw sqlite3.connect() session has no such function and its UPDATE on
        # protected columns aborts ("no such function"). Honest limits: a hostile
        # process can register the same function (one line) or edit the db file
        # directly and defeat the guard, and forged events satisfy the evidence
        # triggers by design. The db file is the operator's seal; the CLI is the door.
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS huntos_session_guard (token TEXT)")
        conn.execute("INSERT INTO huntos_session_guard (token) VALUES ('session')")
        conn.create_function("huntos_session_guard_ok", 0, lambda: 1)
        # Taxonomy seeds: the klass allow-list starts as DATA (source='seed') so
        # retro-gated growth (hunt klass add) never needs a schema migration.
        for k in KLASS:
            conn.execute(
                "INSERT OR IGNORE INTO taxonomies (kind, value, source) VALUES ('klass', ?, 'seed')",
                (k,),
            )
        # B4 migration: dbs created before the falsifier column get it on open.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(findings)").fetchall()}
        if "falsifier" not in cols:
            conn.execute("ALTER TABLE findings ADD COLUMN falsifier TEXT DEFAULT ''")
        # v0.4 migration (guarded, idempotent): dbs created before the lead
        # lifecycle get the promote provenance columns via pragma table_info —
        # a legacy db keeps working; the columns simply read NULL until a
        # promote fills them.
        if "lead_id" not in cols:
            conn.execute("ALTER TABLE findings ADD COLUMN lead_id INTEGER")
        if "lead_provenance" not in cols:
            conn.execute("ALTER TABLE findings ADD COLUMN lead_provenance TEXT")
        # Capability-stack migration (guarded, idempotent — same pattern as the
        # falsifier/lead migrations above): dbs created before surfaces/chains
        # get the surface linkage columns on open via pragma table_info, so a
        # legacy db keeps working. Each ALTER is additionally wrapped in
        # try/except sqlite3.Error: two sessions can race the same migration
        # (the loser's ALTER fails with 'duplicate column name') and the db
        # must still open — the column exists either way.
        if "surface_id" not in cols:
            try:
                conn.execute(
                    "ALTER TABLE findings ADD COLUMN surface_id INTEGER REFERENCES surfaces(id)"
                )
            except sqlite3.Error:
                pass
        session_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(conductor_session)").fetchall()
        }
        if "adapter_registry_name" not in session_cols:
            try:
                conn.execute(
                    "ALTER TABLE conductor_session ADD COLUMN adapter_registry_name TEXT"
                )
            except sqlite3.Error:
                pass
        lead_cols = {r[1] for r in conn.execute("PRAGMA table_info(leads)").fetchall()}
        if "surface_id" not in lead_cols:
            try:
                conn.execute(
                    "ALTER TABLE leads ADD COLUMN surface_id INTEGER REFERENCES surfaces(id)"
                )
            except sqlite3.Error:
                pass
        # E14 (batch 3): the hot query paths were full table scans (grep
        # "CREATE INDEX" -> 0 hits at audit). Idempotent CREATE IF NOT EXISTS
        # on every connect — the same pattern as the tables, so a LEGACY db
        # picks the indexes up on its next open. Column-guarded because a
        # legacy db may predate a column (m22's pre-v0.4 findings table has no
        # wave_id); that db must still open, just without the missing index.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_finding ON events(finding_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_target_kind ON events(target_id, kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_target ON findings(target_id)")
        if "wave_id" in cols:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_wave ON findings(wave_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_target_state ON leads(target_id, state)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mutations_lead ON lead_mutations(lead_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_precond_lead ON lead_preconditions(lead_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_surfaces_target ON surfaces(target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chains_target ON chains(target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chain_steps_chain ON chain_steps(chain_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_target_source_kind ON target_source(kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conductor_session_target ON conductor_session(target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conductor_attempt_session ON conductor_attempt(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conductor_incident_session ON conductor_incident(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conductor_event_session_id ON conductor_event(session_id, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conductor_event_attempt_sequence ON conductor_event(attempt_id, sequence)")
        conn.commit()
        # Database fingerprint: a stable identity so a swapped/recreated DB file is
        # detectable (report footers name the db they were generated from).
        if conn.execute("SELECT value FROM meta WHERE key='db_id'").fetchone() is None:
            conn.execute("INSERT INTO meta (key, value) VALUES ('db_id', ?)", (uuid.uuid4().hex,))
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('db_created', ?)",
                (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),),
            )
            conn.commit()
    except sqlite3.Error as e:
        # connect-time failures (corrupt file, locked schema write) exit cleanly
        # through the CLI's BLOCKED handler instead of leaking a traceback.
        raise ValueError(f"BLOCKED: cannot open hunt db ({db_path}): {e}")
    return conn


def get_meta(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def log_event(conn: sqlite3.Connection, target_id: Optional[int], kind: str, detail: str = "",
              finding_id: Optional[int] = None) -> int:
    # Gate FIRST, like every other free-text writer: raw secrets are refused,
    # not stored.
    assert_no_secrets(detail, "event detail")
    # Safety net: events are an audit trail, not a secret store. Anything that
    # slipped past the gate-level assert_no_secrets checks is redacted here.
    detail = redact(detail)
    cur = conn.execute(
        "INSERT INTO events (target_id, kind, detail, finding_id) VALUES (?, ?, ?, ?)",
        (target_id, kind, detail, finding_id),
    )
    return int(cur.lastrowid or 0)


def _row(conn: sqlite3.Connection, sql: str, args: tuple,
         label: Optional[str] = None) -> sqlite3.Row:
    """Fetch one row or refuse with a named not-found error (L2.3).

    `label` names the object the way the operator knows it ('target #2',
    'finding #3', 'wave #1', 'lead L-1'); the refusal is then
    'BLOCKED: <label> not found' — never the raw 'not found: id = ?' that
    leaked the SQL WHERE clause. Call sites without a label keep the legacy
    message (kernel-internal lookups the CLI never surfaces directly)."""
    row = conn.execute(sql, args).fetchone()
    if row is None:
        if label is not None:
            raise ValueError(f"BLOCKED: {label} not found")
        raise ValueError(f"not found: {sql.split('WHERE')[-1].strip()}")
    return row


def _require_active_target(conn: sqlite3.Connection, target_id: int) -> sqlite3.Row:
    """Archived lock: a closed hunt accepts no new writes. Returns the target row."""
    t = get_target(conn, target_id)
    if t["phase"] == "archived":
        raise ValueError(f"BLOCKED: target #{target_id} is archived — the hunt is closed")
    return t


# --- targets ---

def add_target(conn: sqlite3.Connection, name: str, url: str, chain: str = "evm",
               age_days: int = 0, tvl_usd: float = 0.0, notes: str = "") -> int:
    # E2: NaN/inf tvl binds as NULL in sqlite3 and poisons every later
    # list/report with a TypeError — refuse at the source (same lesson as A5).
    if isinstance(tvl_usd, float) and not math.isfinite(tvl_usd):
        raise ValueError(
            f"BLOCKED: tvl must be a finite number — got {tvl_usd!r} "
            "(NaN/inf poison the row: sqlite binds them as NULL)"
        )
    cur = conn.execute(
        "INSERT INTO targets (name, url, chain, age_days, tvl_usd, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (name, url, chain, age_days, tvl_usd, notes),
    )
    log_event(conn, cur.lastrowid, "target_added", f"{name} {url}")
    conn.commit()
    return int(cur.lastrowid)


def prepare_target(conn: sqlite3.Connection, name: str, source, chain: str,
                   hosts: str, actions: str, authorization_note: str) -> int:
    """Atomically create a target, its immutable source record, and its RoE."""
    required = {
        "name": name,
        "chain": chain,
        "authorization_note": authorization_note,
    }
    for field, value in required.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"BLOCKED: {field} is required")
        assert_no_secrets(value, field)
    source_fields = {}
    for field in ("kind", "canonical", "display", "workspace", "revision"):
        value = getattr(source, field, None)
        if not isinstance(value, str):
            raise ValueError(f"BLOCKED: target source {field} must be a string")
        if field in ("kind", "canonical", "display") and not value.strip():
            raise ValueError(f"BLOCKED: target source {field} is required")
        assert_no_secrets(value, f"target source {field}")
        source_fields[field] = value.strip() if field != "workspace" else value
    if source_fields["kind"] not in ("url", "github", "folder"):
        raise ValueError("BLOCKED: target source kind must be url, github, or folder")
    assert_no_secrets(hosts or "", "RoE hosts")
    parsed_actions = [a.strip() for a in (actions or "").split(",") if a.strip()]
    if not parsed_actions:
        raise ValueError("BLOCKED: RoE must allow at least one action")
    if any(action not in ROE_ACTIONS for action in parsed_actions):
        raise ValueError(
            f"BLOCKED: RoE actions must be a comma list from {sorted(ROE_ACTIONS)}"
        )
    normalized_actions = ",".join(sorted(set(parsed_actions)))
    savepoint = f"prepare_target_{uuid.uuid4().hex}"
    conn.execute(f"SAVEPOINT {savepoint}")
    try:
        cur = conn.execute(
            "INSERT INTO targets (name, url, chain) VALUES (?, ?, ?)",
            (redact(name.strip()), redact(source_fields["canonical"]), redact(chain.strip())),
        )
        target_id = int(cur.lastrowid or 0)
        conn.execute(
            "INSERT INTO target_source "
            "(target_id, kind, canonical, display, workspace, revision, authorization_note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target_id, source_fields["kind"], redact(source_fields["canonical"]),
             redact(source_fields["display"]), redact(source_fields["workspace"]),
             redact(source_fields["revision"]), redact(authorization_note.strip())),
        )
        conn.execute(
            "INSERT INTO rules_of_engagement (target_id, hosts, actions, notes) "
            "VALUES (?, ?, ?, ?)",
            (target_id, redact(hosts or ""), normalized_actions,
             redact(authorization_note.strip())),
        )
        log_event(conn, target_id, "target_added", f"{name.strip()} {source_fields['canonical']}")
        log_event(conn, target_id, "target_source_added",
                  f"kind={source_fields['kind']} display={source_fields['display']}")
        log_event(conn, target_id, "target_prepared",
                  f"workspace={source_fields['workspace']} revision={source_fields['revision']} "
                  f"actions={normalized_actions}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        conn.commit()
        return target_id
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
        conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        raise


def get_target_source(conn: sqlite3.Connection, target_id: int):
    return conn.execute(
        "SELECT * FROM target_source WHERE target_id=?", (target_id,)
    ).fetchone()


def get_target(conn: sqlite3.Connection, target_id: int) -> sqlite3.Row:
    return _row(conn, "SELECT * FROM targets WHERE id = ?", (target_id,),
                label=f"target #{target_id}")


def list_targets(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM targets ORDER BY id DESC").fetchall()


def score_target(conn: sqlite3.Connection, target_id: int, ev_score: float) -> None:
    row = get_target(conn, target_id)
    if row["phase"] not in ("scoring",):
        raise ValueError(
            f"BLOCKED: target {target_id} already past scoring phase (phase={row['phase']}) "
            f"| NEXT: hunt next --target {target_id}"
        )
    # NaN/inf would poison the row (sqlite binds NaN as NULL) and brick status.
    if not math.isfinite(ev_score):
        raise ValueError("BLOCKED: ev_score must be a finite number > 0")
    if ev_score <= 0:
        raise ValueError("BLOCKED: ev_score must be > 0")
    conn.execute("UPDATE targets SET ev_score = ? WHERE id = ?", (ev_score, target_id))
    log_event(conn, target_id, "scored", f"ev={ev_score}")
    conn.commit()


def archive_target(conn: sqlite3.Connection, target_id: int, reason: str) -> None:
    t = get_target(conn, target_id)
    # A completed hunt (report/retro) can only be sealed with its report evidence
    # on the ledger. The economic stop from hunting stays exempt: exhausted waves
    # archive mid-pipeline by design.
    if t["phase"] in ("report", "retro") and not _has_artifact(conn, target_id, "disclosure_report"):
        raise ValueError(
            "BLOCKED: archive requires the report phase evidence — hunt report --out first"
        )
    lesson = conn.execute(
        "SELECT 1 FROM lessons WHERE target_id=? LIMIT 1", (target_id,)
    ).fetchone()
    if lesson is None:
        raise ValueError(
            "BLOCKED: archive requires a retro lesson — "
            'hunt lesson add --target-id <id> "<pattern>" (memory compounds or it never happened)'
        )
    conn.execute("UPDATE targets SET phase='archived', archive_reason=? WHERE id=?", (reason, target_id))
    log_event(conn, target_id, "archived", reason)
    conn.commit()


def _has_artifact(conn: sqlite3.Connection, target_id: int, artifact_type: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM events WHERE target_id=? AND kind='phase_artifact' AND detail LIKE ? LIMIT 1",
        (target_id, artifact_type + ":%"),
    ).fetchone() is not None


def set_phase(conn: sqlite3.Connection, target_id: int, new_phase: str) -> None:
    row = get_target(conn, target_id)
    old = row["phase"]
    if new_phase not in PHASE_RANK or old not in PHASE_RANK:
        raise ValueError(f"unknown phase: {old} -> {new_phase}")
    if new_phase == "archived":
        raise ValueError("use archive_target() for archived")
    # pipeline order enforcement: forward-only, no skipping
    if PHASE_RANK[new_phase] != PHASE_RANK[old] + 1:
        nxt = PHASES[PHASE_RANK[old] + 1] if PHASE_RANK[old] + 1 < len(PHASES) else new_phase
        raise ValueError(
            f"BLOCKED: phase skip blocked: {old} -> {new_phase} not next in pipeline "
            f"| NEXT: hunt phase {target_id} {nxt}"
        )
    # phase exit gates: the phase being LEFT must have produced its evidence
    if old == "scoring" and row["ev_score"] <= 0:
        raise ValueError(
            "BLOCKED: target cannot leave scoring without a positive ev_score — "
            f"score it first | NEXT: hunt score {target_id} <ev>"
        )
    if old == "recon" and not _has_artifact(conn, target_id, "surface_map"):
        raise ValueError(
            "BLOCKED: cannot leave recon without a surface_map artifact — "
            f"hunt artifact {target_id} surface_map <file> "
            f"| NEXT: hunt artifact {target_id} surface_map <file>"
        )
    if old == "classify" and not _has_artifact(conn, target_id, "attack_plan"):
        raise ValueError(
            "BLOCKED: cannot leave classify without an attack_plan artifact — "
            f"hunt artifact {target_id} attack_plan <file> "
            f"| NEXT: hunt artifact {target_id} attack_plan <file>"
        )
    if old == "hunting":
        last = conn.execute(
            "SELECT ev_verdict FROM waves WHERE target_id=? ORDER BY number DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        if last is None or not last["ev_verdict"]:
            variant = "without a single closed wave" if last is None else "without a closed wave"
            raise ValueError(
                f"BLOCKED: cannot leave hunting {variant} — "
                "close the wave first "
                f"| NEXT: hunt next --target {target_id}"
            )
    if old == "verify":
        in_code = conn.execute(
            "SELECT COUNT(*) AS n FROM findings WHERE target_id=? AND ladder_status='in-code'",
            (target_id,),
        ).fetchone()["n"]
        if in_code:
            raise ValueError(
                f"BLOCKED: cannot leave verify with {in_code} in-code findings — "
                "promote, overturn, or deliberately leave each finding theoretical "
                f"| NEXT: hunt next --target {target_id}"
            )
    if old == "report" and not _has_artifact(conn, target_id, "disclosure_report"):
        raise ValueError(
            "BLOCKED: cannot leave report without a disclosure_report artifact — "
            f"hunt artifact {target_id} disclosure_report <file> "
            f"| NEXT: hunt artifact {target_id} disclosure_report <file>"
        )
    conn.execute("UPDATE targets SET phase=? WHERE id=?", (new_phase, target_id))
    log_event(conn, target_id, "phase", f"{old} -> {new_phase}")
    conn.commit()


# --- findings (evidence ladder enforcement lives here) ---

def add_finding(conn: sqlite3.Connection, target_id: int, title: str, klass: str,
                severity: str = "info", ladder_status: str = "theoretical",
                evidence_ref: str = "", poc_path: str = "", notes: str = "",
                action: str = "read", falsifier: str = "",
                commit: bool = True, surface_id: Optional[int] = None) -> int:
    if ladder_status != "theoretical":
        raise ValueError(
            "BLOCKED: findings must be inserted as 'theoretical' — the ladder is earned, not claimed"
        )
    if not klass or not klass.strip():
        raise ValueError("BLOCKED: klass is required")
    klass = klass.strip()
    known = conn.execute(
        "SELECT 1 FROM taxonomies WHERE kind='klass' AND value=? LIMIT 1", (klass,)
    ).fetchone()
    if known is None:
        raise ValueError(
            f"BLOCKED: unknown klass '{klass}' — insert as 'Unknown' and promote it at retro "
            f"(hunt klass add {klass} --from-finding <id>)"
        )
    if action not in ROE_ACTIONS:
        raise ValueError(f"BLOCKED: action must be one of {sorted(ROE_ACTIONS)}")
    t = _require_active_target(conn, target_id)
    # Phase scoping: the hunt executes in hunting/verify; the ledger refuses
    # findings recorded outside them (A6: the pipeline is not ceremony).
    if t["phase"] not in ("hunting", "verify"):
        raise ValueError(
            "BLOCKED: findings/waves belong to the hunting or verify phase "
            f"(current phase: {t['phase']})"
        )
    # Surface linkage (capability stack): a finding may pin itself to a surface
    # from the Architect's map. A dangling surface_id would silently corrupt
    # surface_coverage's blind-spot math, so existence is enforced here.
    if surface_id is not None:
        linked = conn.execute(
            "SELECT 1 FROM surfaces WHERE id=? LIMIT 1", (surface_id,)
        ).fetchone()
        if linked is None:
            raise ValueError(f"BLOCKED: surface #{surface_id} does not exist")
    # Raw secrets are refused; what gets stored is conservatively redacted.
    # Titles are display text and a favorite dumping ground for pasted secrets,
    # so they get the same safety net as notes. The falsifier is the evidence
    # that would DISPROVE the finding (B4) — same gates, it is stored prose.
    title = redact(title)
    assert_no_secrets(notes, "notes")
    notes = redact(notes)
    assert_no_secrets(falsifier, "falsifier")
    falsifier = redact(falsifier)
    cur = conn.execute(
        "INSERT INTO findings (target_id, title, klass, severity, ladder_status, evidence_ref, poc_path, notes, action, falsifier, surface_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (target_id, title, klass, severity, ladder_status, evidence_ref, poc_path, notes, action, falsifier, surface_id),
    )
    log_event(conn, target_id, "finding_added",
              f"[{severity}] {title} ({ladder_status})", finding_id=int(cur.lastrowid or 0))
    # auto-link the finding to the latest OPEN wave of this target (ev_verdict='')
    open_wave_row = conn.execute(
        "SELECT id FROM waves WHERE target_id=? AND ev_verdict='' ORDER BY number DESC LIMIT 1",
        (target_id,),
    ).fetchone()
    if open_wave_row is not None:
        conn.execute("UPDATE findings SET wave_id=? WHERE id=?", (open_wave_row["id"], cur.lastrowid))
    # E12: internal callers (promote_lead) pass commit=False and commit the
    # whole promote as ONE transaction — two commits left a crash window that
    # stranded an orphan finding (lead_id NULL) with the lead still promotable.
    if commit:
        conn.commit()
    return int(cur.lastrowid)


def record_poc_run(conn: sqlite3.Connection, finding_id: int, poc_path: str,
                   exit_code: int, output_tail: str) -> int:
    """Record an executed PoC run. The ladder requires it before promotion.

    Pins the PoC file's sha256 at run time: promote_finding later requires a
    poc_run event whose recorded digest matches the promoted file, so a PoC
    that never ran (or changed after running) cannot climb. Only exit 0 counts.
    Returns the event id of the recorded poc_run event.
    """
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    real_path = os.path.expanduser(poc_path)
    if not os.path.exists(real_path):
        raise ValueError(f"BLOCKED: poc_path does not exist: {poc_path}")
    if not os.path.isfile(real_path):
        raise ValueError(f"BLOCKED: poc_path is not a file: {poc_path}")
    if exit_code != 0:
        raise ValueError(
            f"BLOCKED: poc run failed with exit {exit_code} — a failed PoC is evidence of nothing"
        )
    with open(real_path, "rb") as fh:
        poc_bytes = fh.read()
    digest = hashlib.sha256(poc_bytes).hexdigest()
    # The tail is the only output text kept, redacted first: events are an audit
    # trail, not a secret store (log_event redacts again as a safety net).
    tail = redact(output_tail or "")[-160:]
    # The poc path rides at the END of the detail (' path=<poc_path>') so
    # `next_command` can name the executed PoC file in its row-13 promote
    # recommendation (the tail may contain anything, so the path goes last).
    # The digest prefix is unchanged: promote_finding matches
    # 'poc sha256:<16>%' and that contract is frozen.
    event_id = log_event(conn, row["target_id"], "poc_run",
                         f"poc sha256:{digest[:16]} exit=0 tail:{tail} path={poc_path}",
                         finding_id=finding_id)
    conn.commit()
    return event_id


def promote_finding(conn: sqlite3.Connection, finding_id: int, evidence_ref: str, poc_path: str) -> str:
    """theoretical -> in-code -> proven-live. Each step demands fresh, distinct
    work, and the PoC must have actually RUN (poc_run event matching this file's
    hash) — existence is not execution."""
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    status = row["ladder_status"]
    if status == "overturned":
        raise ValueError("overturned findings cannot be promoted")
    if status == "proven-live":
        raise ValueError("already proven-live")
    if not evidence_ref or not poc_path:
        raise ValueError("BLOCKED: promotion requires evidence_ref AND poc_path (no PoC = no proof)")
    assert_no_secrets(evidence_ref, "evidence_ref")
    path = os.path.expanduser(poc_path)
    if not os.path.exists(path):
        raise ValueError(f"BLOCKED: poc_path does not exist: {poc_path}")
    if not os.path.isfile(path):
        raise ValueError(f"BLOCKED: poc_path is not a file: {poc_path}")
    with open(path, "rb") as fh:
        poc_bytes = fh.read()
    if len(poc_bytes) == 0:
        raise ValueError("BLOCKED: poc file is empty — no PoC = no proof")
    digest = hashlib.sha256(poc_bytes).hexdigest()
    # A7: the ladder's core hole closed. "PoC exists" is not "PoC ran" — a
    # poc_run event whose recorded digest matches THIS file is required before
    # any promotion. The proven-live step is additionally trigger-enforced for
    # raw writers (findings_proven_requires_evidence).
    ran = conn.execute(
        "SELECT 1 FROM events WHERE finding_id=? AND kind='poc_run' AND detail LIKE ? LIMIT 1",
        (finding_id, f"poc sha256:{digest[:16]}%"),
    ).fetchone()
    if ran is None:
        raise ValueError(
            "BLOCKED: this PoC has never been executed — "
            f"hunt poc run --id {finding_id} --poc-path <file> (existence is not execution) "
            f"| NEXT: hunt poc run --id {finding_id} --poc-path <file>"
        )
    if status == "theoretical":
        new_status = "in-code"
    else:  # in-code
        new_status = "proven-live"
        if digest == row["poc_sha256"]:
            raise ValueError(
                "BLOCKED: proven-live requires a DIFFERENT PoC than the in-code step "
                f"(same sha256: {digest[:16]}...)"
            )
        if evidence_ref == row["evidence_ref"]:
            raise ValueError("BLOCKED: evidence_ref reused from the previous ladder step")
        verified = conn.execute(
            "SELECT 1 FROM events WHERE finding_id=? AND kind='verifier_pass' LIMIT 1",
            (finding_id,),
        ).fetchone()
        if verified is None:
            raise ValueError(
                "BLOCKED: proven-live requires a verifier event — "
                "hunt verify <finding_id> <fork_receipt|tx_hash|http_transcript> <body>"
            )
        challenged = conn.execute(
            "SELECT 1 FROM events WHERE finding_id=? AND kind='adversary_pass' LIMIT 1",
            (finding_id,),
        ).fetchone()
        if challenged is None:
            raise ValueError(
                "BLOCKED: proven-live requires an adversary review — "
                f'hunt challenge {finding_id} "<what you attacked and what held>"'
            )
        # Rules of engagement: default-deny for mutate. RoE is set per target;
        # a mutate finding cannot reach proven-live unless the target's RoE
        # explicitly allows the mutate action.
        if row["action"] == "mutate":
            roe = get_roe(conn, row["target_id"])
            allowed = roe["actions"].split(",") if roe is not None else []
            if "mutate" not in allowed:
                raise ValueError(
                    "BLOCKED: mutate finding cannot reach proven-live outside the rules of "
                    "engagement — hunt target roe "
                    f"{row['target_id']} --actions ... (default-deny)"
                )
    # Compare-and-swap (A3): the status read above is part of the WHERE, so a
    # concurrent overturn/promote between the SELECT and this UPDATE cannot be
    # clobbered — the ladder cannot rewrite a terminal state it did not see.
    cur = conn.execute(
        "UPDATE findings SET ladder_status=?, evidence_ref=?, poc_path=?, poc_sha256=? "
        "WHERE id=? AND ladder_status=?",
        (new_status, evidence_ref, poc_path, digest, finding_id, status),
    )
    if cur.rowcount != 1:
        raise ValueError(
            "BLOCKED: finding changed underneath this promotion (concurrent modification)"
        )
    log_event(conn, row["target_id"], "finding_promoted",
              f"#{finding_id} {status} -> {new_status}", finding_id=finding_id)
    conn.commit()
    return new_status


def record_verification(conn: sqlite3.Connection, finding_id: int, artifact_type: str,
                        body: str, role: str = "verifier") -> None:
    """Log a verifier event. required before any proven-live promotion."""
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"BLOCKED: artifact_type must be one of {ARTIFACT_TYPES}")
    if not body or not body.strip():
        raise ValueError("BLOCKED: verification body must not be empty")
    if artifact_type == "tx_hash" and not re.fullmatch(r"0x[0-9a-fA-F]{64}", body.strip()):
        raise ValueError("BLOCKED: tx_hash must be a 0x-prefixed 64-hex transaction hash")
    assert_no_secrets(body, "verification body")
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    if row["ladder_status"] == "overturned":
        raise ValueError("overturned findings cannot be verified")
    log_event(conn, row["target_id"], "verifier_pass",
              f"{artifact_type}: {body.strip()} (by {role})", finding_id=finding_id)
    conn.commit()


def record_adversary(conn: sqlite3.Connection, finding_id: int, notes: str,
                     role: str = "adversary") -> None:
    """Log an adversary pass. Required before any proven-live promotion."""
    if not notes or not notes.strip():
        raise ValueError(
            "BLOCKED: adversary review requires notes — what did you attack and what held?"
        )
    assert_no_secrets(notes, "adversary notes")
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    if row["ladder_status"] == "overturned":
        raise ValueError(
            "BLOCKED: an overturned finding is already falsified — it cannot be challenged"
        )
    log_event(conn, row["target_id"], "adversary_pass",
              f"{role}: {notes.strip()}", finding_id=finding_id)
    conn.commit()


# A6: which pipeline phase owns each L2 artifact (record_phase_artifact scoping)
_ARTIFACT_OWNER_PHASE = {v: k for k, v in PHASE_ARTIFACTS.items()}


def record_phase_artifact(conn: sqlite3.Connection, target_id: int,
                          artifact_type: str, path: str) -> None:
    """Record a phase exit artifact (FRAMEWORK.md L2 contract). Hashes the file.
    Each artifact belongs to the phase that owns it — surface_map: recon,
    attack_plan: classify, disclosure_report: report."""
    allowed = sorted(set(PHASE_ARTIFACTS.values()))
    if artifact_type not in allowed:
        raise ValueError(f"BLOCKED: artifact_type must be one of {allowed}")
    t = _require_active_target(conn, target_id)
    owner_phase = _ARTIFACT_OWNER_PHASE.get(artifact_type)
    if owner_phase is not None and t["phase"] != owner_phase:
        raise ValueError(
            f"BLOCKED: {artifact_type} belongs to the {owner_phase} phase "
            f"(current phase: {t['phase']})"
        )
    real_path = os.path.expanduser(path)
    if not os.path.exists(real_path):
        raise ValueError(f"BLOCKED: artifact file does not exist: {path}")
    if not os.path.isfile(real_path):
        raise ValueError(f"BLOCKED: artifact path is not a file: {path}")
    with open(real_path, "rb") as fh:
        data = fh.read()
    if len(data) == 0:
        raise ValueError("BLOCKED: artifact file is empty")
    digest = hashlib.sha256(data).hexdigest()
    log_event(conn, target_id, "phase_artifact",
              f"{artifact_type}: {path} sha256:{digest[:16]}")
    conn.commit()


def overturn_finding(conn: sqlite3.Connection, finding_id: int, overturned_by: str) -> None:
    """Adversary wins: status drops to overturned. Row is kept - audit trail is permanent."""
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    conn.execute("UPDATE findings SET ladder_status='overturned', overturned_by=? WHERE id=?", (overturned_by, finding_id))
    log_event(conn, row["target_id"], "finding_overturned", f"#{finding_id} by {overturned_by}")
    conn.commit()


def retitle_finding(conn: sqlite3.Connection, finding_id: int, title: str) -> None:
    """Retitle a finding (L2.1): bookkeeping, not evidence.

    A mangled/embarrassing title must not cost an overturn — retitling is the
    honest fix. Gates: the target is not archived (a closed hunt is history),
    the finding is not overturned (a falsified finding's record is audit
    trail), and the NEW title passes the secrets gate. Proven-live MAY retitle:
    the ladder columns (ladder_status/evidence_ref/poc_*) are untouched, so the
    evidence bar is unchanged. Logs a `finding_retitled` event carrying the OLD
    title, so the rename itself is auditable. Not a general edit API — klass,
    severity, and ladder are NOT editable here."""
    row = _row(conn, "SELECT * FROM findings WHERE id = ?", (finding_id,),
               label=f"finding #{finding_id}")
    _require_active_target(conn, row["target_id"])
    if row["ladder_status"] == "overturned":
        raise ValueError(
            f"BLOCKED: finding #{finding_id} is overturned — a falsified finding's "
            "record is audit trail and cannot be retitled"
        )
    clean = (title or "").strip()
    if not clean:
        raise ValueError("BLOCKED: retitle requires a non-empty title")
    assert_no_secrets(clean, "title")
    clean = redact(clean)
    conn.execute("UPDATE findings SET title=? WHERE id=?", (clean, finding_id))
    log_event(conn, row["target_id"], "finding_retitled",
              f"finding #{finding_id} retitled: {row['title']!r} -> {clean!r}",
              finding_id=finding_id)
    conn.commit()


def list_findings(conn: sqlite3.Connection, target_id: int) -> list:
    return conn.execute("SELECT * FROM findings WHERE target_id=? ORDER BY id", (target_id,)).fetchall()


def get_finding_wave_id(conn: sqlite3.Connection, finding_id: int) -> Optional[int]:
    """The wave a finding is linked to (None = it was born with no open wave).

    Read-only helper for the CLI's finding-add echo (L1.4): the echo reads the
    finding's wave_id AFTER the insert instead of changing add_finding's return
    contract (int finding id — callers and kernel tests depend on it)."""
    row = conn.execute("SELECT wave_id FROM findings WHERE id=?", (finding_id,)).fetchone()
    if row is None or row["wave_id"] is None:
        return None
    return int(row["wave_id"])


# --- leads (the observation ledger: hypotheses are first-class state) ---
# A lead is a hypothesis with two INDEPENDENT halves — trigger and impact —
# each traced separately. The lifecycle is a closed state machine:
#
#   add -> open -> mutating -> promoted (both halves proven -> a finding)
#        |          |
#        |          +-> parked (refused kill, or deliberate, always with a
#        |                     testable retrigger condition) -> open
#        +-> killed (both halves refuted with evidence on both)
#
# Guards: an archived target accepts no lead action (A2 consistency); payload
# may be empty at add (recon-origin) but is required before the mutation loop;
# `ambiguous` can only come from the oracle, never from a hand-typed verdict;
# every kill refusal parks with a retrigger and bumps dismissal_count instead
# of letting a half-refuted lead die quietly.

LEAD_STATES = ("open", "mutating", "parked", "killed", "promoted")
LEAD_VERDICTS = ("untraced", "proven", "refuted", "ambiguous")
LEAD_HALVES = ("trigger", "impact")
MUTATION_RESULTS = ("advanced", "unchanged", "refuted", "unknown")
RETRIGGER_SEPARATOR = " :: "

# kill refusal -> auto-park: the state a refused kill leaves the lead in
PARKED_BY_KILL_REFUSAL = "parked"


def get_lead(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row:
    return _row(conn, "SELECT * FROM leads WHERE id = ?", (lead_id,),
                label=_lead_labeled(lead_id))


def _lead_labeled(lead_id: int) -> str:
    """Every lead BLOCKED message names the object: `lead L-<id>` (the id is
    the row id, matching the L-n claim-gate binding)."""
    return f"lead L-{lead_id}"


def _validate_retrigger(retrigger: str, lead_id: int) -> str:
    """A retrigger condition must be a testable 'observable :: check' pair.

    A park without one is a lazy kill (I6): the lead dies in the brief with no
    tripwire to wake it — refused. Returns the validated string.
    """
    if not retrigger or not retrigger.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} cannot park without a retrigger condition — "
            "pass --retrigger \"observable :: check\" (a park without a tripwire is a lazy kill)"
        )
    parts = retrigger.split(RETRIGGER_SEPARATOR)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} retrigger must be 'observable :: check' "
            f"(separator{RETRIGGER_SEPARATOR!r} required, both sides non-empty); got: {retrigger!r}"
        )
    # R2-06: park/kill retriggers are lead free-text — same storage gate as
    # the payload (redact() alone is display-only; a token shape must not be
    # STORED verbatim behind a tripwire the brief echoes).
    assert_no_secrets(retrigger, "retrigger")
    return retrigger.strip()


def _set_lead_half(conn: sqlite3.Connection, lead_id: int, half: str, verdict: str,
                   evidence: str, oracle_event_id: Optional[int] = None) -> int:
    """Shared writer for set-half and record_oracle_verdict. Returns the event id.

    Guard set: active target, open/mutating state, verdict admissible for the
    writer (the oracle may set `ambiguous`; a manual call may not — I2).
    """
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "half verdicts are only admissible while open or mutating"
        )
    # B-L1 (P1, arbiter-confirmed): a verdict set BY THE ORACLE is owned by the
    # oracle. Manual proven/refuted over an oracle-installed 'ambiguous' (or
    # over an oracle-refuted half whose oracle event still stands) launders the
    # oracle's verdict into promote fuel. The manual path must start from
    # 'untraced' — rerun the oracle or refute from scratch instead.
    # R2-05 (round-2, both auditors independently): the same rule covers
    # oracle-'refuted' halves — a manual 'proven' over a live oracle refutation
    # contradicts the docstring's own claim and launders the refutation away.
    if oracle_event_id is None and verdict in ("proven", "refuted"):
        current = lead[f"{half}_verdict"]
        if current in ("ambiguous", "refuted"):
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} {half} verdict was set by the oracle "
                f"({current}) — manual overwrite to '{verdict}' refused (I2/B-L1/R2-05): "
                "rerun the oracle, or let the finding lane carry the story"
            )
    # R2-06: half evidence is lead free-text that lands verbatim in the leads
    # row AND the lead_half_set event — same storage gate as the payload
    # (refuse at the gate; redact() is display-only, not a storage defense).
    assert_no_secrets(evidence, f"{half} evidence")
    column = f"{half}_verdict"
    evidence_column = f"{half}_evidence"
    try:
        conn.execute(
            f"UPDATE leads SET {column}=?, {evidence_column}=?, updated_at=datetime('now') WHERE id=?",
            (verdict, evidence, lead_id),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} verdict '{verdict}' failed the schema CHECK — "
            f"{half} verdict must be one of {LEAD_VERDICTS}"
        )
    log_event(
        conn, lead["target_id"], "lead_half_set",
        f"{_lead_labeled(lead_id)} {half}={verdict} evidence={evidence}"
        + (f" oracle_event_id={oracle_event_id}" if oracle_event_id is not None else ""),
    )
    conn.commit()
    return 0


def set_lead_half(conn: sqlite3.Connection, lead_id: int, half: str, verdict: str,
                  evidence: str) -> int:
    """Set a half's verdict by hand. `proven` and `refuted` are admissible with
    non-empty evidence; `ambiguous` is oracle-exclusive (I2) — it can only be
    installed by record_oracle_verdict, so a manual call with it is BLOCKED."""
    if half not in LEAD_HALVES:
        raise ValueError(f"BLOCKED: half must be one of {LEAD_HALVES}, not '{half}'")
    if verdict not in ("proven", "refuted"):
        if verdict == "ambiguous":
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} 'ambiguous' is oracle-exclusive — "
                "run the oracle (hunt oracle ...) and it will set the half from the verdict"
            )
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} verdict must be 'proven' or 'refuted' "
            f"(untraced is the absence of a verdict, ambiguous comes only from the oracle); got '{verdict}'"
        )
    if not evidence or not evidence.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {half}={verdict} requires non-empty evidence "
            "(a verdict without evidence is a claim, not a trace)"
        )
    return _set_lead_half(conn, lead_id, half, verdict, evidence.strip())


def add_lead(conn: sqlite3.Connection, target_id: int, title: str,
             payload: Optional[str] = "", preconditions: Optional[list] = None,
             surface_id: Optional[int] = None) -> int:
    """Register an observation. Payload may be empty at add (recon-origin is
    legal); the mutation loop re-opens that gate. Preconditions arrive as
    (variable, value, description) tuples and are inserted status='missing'.
    The lead number is per-target (L-1 restarts on each target) and allocated
    in the same transaction as the INSERT. surface_id optionally pins the lead
    to a surface from the Architect's map (must exist when provided)."""
    _require_active_target(conn, target_id)
    title = redact(title)
    if not title or not title.strip():
        raise ValueError("BLOCKED: lead title must not be empty")
    if payload:
        assert_no_secrets(payload, "payload")
        payload = redact(payload)
    else:
        payload = None  # I3: payload may be NULL at add (recon-origin is legal)
    # Surface linkage (capability stack): same existence gate as add_finding —
    # a dangling pin would corrupt surface_coverage's blind-spot math.
    if surface_id is not None:
        linked = conn.execute(
            "SELECT 1 FROM surfaces WHERE id=? LIMIT 1", (surface_id,)
        ).fetchone()
        if linked is None:
            raise ValueError(f"BLOCKED: surface #{surface_id} does not exist")
    number = conn.execute(
        "SELECT COALESCE(MAX(number), 0) + 1 FROM leads WHERE target_id=?",
        (target_id,),
    ).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO leads (target_id, number, title, payload, surface_id) VALUES (?, ?, ?, ?, ?)",
        (target_id, number, title.strip(), payload, surface_id),
    )
    lead_id = int(cur.lastrowid)
    for variable, value, description in (preconditions or []):
        try:
            conn.execute(
                "INSERT INTO lead_preconditions (lead_id, variable, value, description) "
                "VALUES (?, ?, ?, ?)",
                (lead_id, variable, value, description),
            )
        except sqlite3.IntegrityError:
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} duplicate precondition "
                f"'{variable}|{value}' — a variable/value pair is declared once"
            )
    log_event(conn, target_id, "lead_added",
              f"{_lead_labeled(lead_id)} (number {number}) {title.strip()}")
    conn.commit()
    return lead_id


def add_lead_precondition(conn: sqlite3.Connection, lead_id: int, variable: str,
                          value: str, description: str = "") -> int:
    """Declare a precondition on an active lead. A duplicate (lead, variable,
    value) pair is BLOCKED (the UNIQUE key is the source of truth)."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "preconditions are declared on open or mutating leads"
        )
    # R2-06: the description is lead free-text stored verbatim — refuse raw
    # secret shapes at the gate (the payload gate is the template).
    assert_no_secrets(description, "precondition description")
    try:
        cur = conn.execute(
            "INSERT INTO lead_preconditions (lead_id, variable, value, description) "
            "VALUES (?, ?, ?, ?)",
            (lead_id, variable, value, description),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} duplicate precondition '{variable}|{value}'"
        )
    conn.commit()
    return int(cur.lastrowid)


def mutate_lead(conn: sqlite3.Connection, lead_id: int, variable: str, old_value: str,
                new_value: str, result: str, evidence: str,
                plan: Optional[str] = None, resolve: Optional[int] = None) -> int:
    """One step of the mutation loop. Anti-repeat (I7): UNIQUE(lead_id,
    variable, new_value) — the same new value for the same variable cannot be
    tried twice; old_value stays outside the key. Unknown-consumption (I8): a
    result='unknown' MUST give birth to a new precondition (--plan
    'variable|value|description'), so the loop consumes a pair and produces
    one and never dead-ends."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "the mutation loop runs on open or mutating leads"
        )
    if result not in MUTATION_RESULTS:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} result must be one of {MUTATION_RESULTS}; got '{result}'"
        )
    if not evidence or not evidence.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} mutation requires non-empty evidence"
        )
    # R2-06: mutation evidence lands verbatim in lead_mutations — refuse raw
    # secret shapes at the gate (same pattern as the payload gate).
    assert_no_secrets(evidence, "mutation evidence")
    if not lead["payload"]:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} payload required before the mutation loop — "
            "the hypothesis must be concrete enough to mutate (hunt lead set --payload ...)"
        )
    followup_id = None
    plan_parts = None
    if result == "unknown":
        if not plan:
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} result='unknown' requires --plan "
                "'variable|value|description' — an unknown consumes a precondition pair "
                "and must give birth to one (anti-starvation)"
            )
        plan_parts = plan.split("|")
        if len(plan_parts) != 3 or not plan_parts[0].strip() or not plan_parts[1].strip():
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} --plan must be "
                "'variable|value|description' with a non-empty variable and value"
            )
    if resolve is not None:
        pre = _row(conn, "SELECT * FROM lead_preconditions WHERE id = ?", (resolve,),
                   label=f"precondition #{resolve}")
        if pre["lead_id"] != lead_id:
            raise ValueError(
                f"BLOCKED: precondition #{resolve} does not belong to {_lead_labeled(lead_id)}"
            )
        _require_active_target(conn, lead["target_id"])
        conn.execute(
            "UPDATE lead_preconditions SET status='present' WHERE id=?", (resolve,)
        )
    try:
        cur = conn.execute(
            "INSERT INTO lead_mutations (lead_id, variable, old_value, new_value, result, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (lead_id, variable, old_value, new_value, result, evidence.strip()),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} already tried {variable} -> '{new_value}' "
            "(anti-repeat: UNIQUE(lead_id, variable, new_value) — vary the value or vary the variable)"
        )
    mutation_id = int(cur.lastrowid)
    if result == "unknown":
        assert plan_parts is not None  # validated above (result gating)
        try:
            fcur = conn.execute(
                "INSERT INTO lead_preconditions (lead_id, variable, value, description) "
                "VALUES (?, ?, ?, ?)",
                (lead_id, plan_parts[0].strip(), plan_parts[1].strip(), plan_parts[2].strip()),
            )
            followup_id = int(fcur.lastrowid or 0)
        except sqlite3.IntegrityError:
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} plan precondition "
                f"'{plan_parts[0].strip()}|{plan_parts[1].strip()}' already exists — an unknown "
                "must give birth to a NEW pair, not redeclare an old one"
            )
        conn.execute(
            "UPDATE lead_mutations SET followup_precondition_id=? WHERE id=?",
            (followup_id, mutation_id),
        )
    conn.execute(
        "UPDATE leads SET state='mutating', updated_at=datetime('now') WHERE id=?",
        (lead_id,),
    )
    log_event(conn, lead["target_id"], "lead_mutated",
              f"{_lead_labeled(lead_id)} {variable}: {old_value!r} -> {new_value!r} "
              f"result={result}" + (f" followup_precondition_id={followup_id}" if followup_id else ""))
    conn.commit()
    return mutation_id


def next_mutation(conn: sqlite3.Connection, lead_id: int) -> Optional[dict]:
    """The deterministic next step (I11): the FIRST missing precondition (by
    id) whose (variable, value) pair has never been tried in lead_mutations.

    Returns {precondition_id, variable, value, description} or None when every
    missing pair has been tried (the caller suggests parking — a suggestion,
    not an error: exhaustion is information, not misconduct).

    B-L21 (batch 3): the step only exists while the loop is alive. Promoted
    (and killed/parked) leads used to get an actionable step back — the brief
    correctly hides promoted leads, so the command must refuse the same way
    every other lead writer does."""
    lead = get_lead(conn, lead_id)
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — the mutation loop "
            "runs on open or mutating leads (a promoted lead lives as its finding, "
            "a killed lead died with both refutations, a parked lead waits on its tripwire)"
        )
    for pre in conn.execute(
        "SELECT * FROM lead_preconditions WHERE lead_id=? AND status='missing' ORDER BY id",
        (lead_id,),
    ).fetchall():
        tried = conn.execute(
            "SELECT 1 FROM lead_mutations WHERE lead_id=? AND variable=? AND new_value=? LIMIT 1",
            (lead_id, pre["variable"], pre["value"]),
        ).fetchone()
        if tried is None:
            return {
                "precondition_id": pre["id"],
                "variable": pre["variable"],
                "value": pre["value"],
                "description": pre["description"],
            }
    return None


def park_lead(conn: sqlite3.Connection, lead_id: int, retrigger: str,
              notes: str = "") -> None:
    """Park with a mandatory testable retrigger condition (I6). Parked leads
    stay in the brief as tripwires — the observable, when checked, wakes the
    lead. A park without a retrigger is a lazy kill: BLOCKED."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — only open or "
            "mutating leads can park"
        )
    validated = _validate_retrigger(retrigger, lead_id)
    conn.execute(
        "UPDATE leads SET state='parked', retrigger_condition=?, updated_at=datetime('now') "
        "WHERE id=?",
        (validated, lead_id),
    )
    log_event(conn, lead["target_id"], "lead_parked",
              f"{_lead_labeled(lead_id)} retrigger={validated}" + (f" notes={notes}" if notes else ""))
    conn.commit()


def reopen_lead(conn: sqlite3.Connection, lead_id: int, evidence: str) -> None:
    """E1/R2-04 (both auditors, converging): parked -> open. The tripwire
    fired — the operator observed the retrigger condition and the lead wakes.
    Requires the observation that fired (non-empty evidence), the target must
    be active, and the lead must actually be parked. Killed and promoted leads
    do not reopen: killed died with both refutations, promoted lives as a
    finding. A reopen event is journaled so the parked->open->parked loop is
    auditable (dismissal_count carries the history)."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] != "parked":
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "only parked leads reopen (killed died with both refutations, "
            "promoted lives as a finding)"
        )
    if not evidence or not evidence.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} reopen requires the observation "
            "that fired the tripwire (non-empty evidence)"
        )
    assert_no_secrets(evidence, "reopen evidence")
    conn.execute(
        "UPDATE leads SET state='open', updated_at=datetime('now') WHERE id=?",
        (lead_id,),
    )
    log_event(conn, lead["target_id"], "lead_reopened",
              f"{_lead_labeled(lead_id)} tripwire fired: {evidence.strip()} "
              f"(was parked with retrigger: {lead['retrigger_condition']})")
    conn.commit()


def _parse_retrigger(retrigger: Optional[str], lead_id: int) -> str:
    """Validate a kill's optional retrigger through the same gate as park —
    the auto-park on a refused kill must not be lazier than a deliberate park."""
    if retrigger is None:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} kill refusal requires --retrigger "
            "(the auto-park refuses to park without a tripwire — a park without a "
            "retrigger is a lazy kill)"
        )
    return _validate_retrigger(retrigger, lead_id)


def kill_lead(conn: sqlite3.Connection, lead_id: int, trigger_refutation: str,
              impact_refutation: str, retrigger: Optional[str] = None) -> str:
    """Kill requires BOTH halves refuted with non-empty evidence on both (I5).

    A one-sided kill is refused: the lead auto-parks (with the kill's
    retrigger, same gate as park_lead — no retrigger, no refusal path),
    dismissal_count is incremented, and a lead_kill_refused event is
    recorded. Returns 'killed' or 'refused'."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "only open or mutating leads can be killed"
        )
    if not trigger_refutation or not trigger_refutation.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} trigger refutation must be non-empty"
        )
    if not impact_refutation or not impact_refutation.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} impact refutation must be non-empty"
        )
    both_refuted = lead["trigger_verdict"] == "refuted" and lead["impact_verdict"] == "refuted"
    both_evidence = bool(lead["trigger_evidence"]) and bool(lead["impact_evidence"])
    if both_refuted and both_evidence:
        # An optional retrigger on a clean kill is still a tripwire: the lead
        # may wake if the refutation stops holding (I14 shows killed-with-
        # retrigger in the brief). Validated through the same gate as park.
        stored_retrigger = _validate_retrigger(retrigger, lead_id) if retrigger else None
        conn.execute(
            "UPDATE leads SET state='killed', trigger_evidence=?, impact_evidence=?, "
            "retrigger_condition=COALESCE(?, retrigger_condition), "
            "updated_at=datetime('now') WHERE id=?",
            (trigger_refutation.strip(), impact_refutation.strip(), stored_retrigger, lead_id),
        )
        log_event(conn, lead["target_id"], "lead_killed",
                  f"{_lead_labeled(lead_id)} killed: trigger + impact refuted")
        conn.commit()
        return "killed"
    # Kill refused: park (lazy kills are not allowed, so neither is a lazy refusal)
    validated = _parse_retrigger(retrigger, lead_id)
    new_dismissals = lead["dismissal_count"] + 1
    conn.execute(
        "UPDATE leads SET state='parked', retrigger_condition=?, dismissal_count=?, "
        "updated_at=datetime('now') WHERE id=?",
        (validated, new_dismissals, lead_id),
    )
    missing = [half for half, v, e in (
        ("trigger", lead["trigger_verdict"], lead["trigger_evidence"]),
        ("impact", lead["impact_verdict"], lead["impact_evidence"]),
    ) if v != "refuted" or not e]
    log_event(conn, lead["target_id"], "lead_kill_refused",
              f"{_lead_labeled(lead_id)} kill refused: {', '.join(missing)} still unrefuted; "
              f"auto-parked dismissal #{new_dismissals}")
    conn.commit()
    return "refused"


def _build_provenance(conn: sqlite3.Connection, lead: sqlite3.Row) -> dict:
    """The promote snapshot (I9/I10): denormalized history, FROZEN at promote
    time. After promote the lead is read-only for verdict edits, so the
    snapshot cannot drift from the history it summarizes."""
    # Count parked days from the parked/reopen event pair (created_at is
    # UTC from datetime('now')); a still-parked lead parks until now.
    days_parked = 0
    parked_since = None
    for ev in conn.execute(
        "SELECT kind, created_at FROM events WHERE detail LIKE ? ORDER BY id",
        (f"{_lead_labeled(lead['id'])} %",),
    ).fetchall():
        if ev["kind"] == "lead_parked":
            parked_since = ev["created_at"]
        elif ev["kind"] in ("lead_state_reset", "lead_killed"):
            parked_since = None
    if parked_since:
        try:
            start = datetime.strptime(parked_since, "%Y-%m-%d %H:%M:%S")
            end = (datetime.strptime(lead["updated_at"], "%Y-%m-%d %H:%M:%S")
                   if lead["state"] == "parked" else datetime.utcnow())
            days_parked = max(0, int((end - start).total_seconds() // 86400))
        except (TypeError, ValueError):
            days_parked = 0
    counts = conn.execute(
        "SELECT "
        "SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS present, "
        "SUM(CASE WHEN status='refuted' THEN 1 ELSE 0 END) AS refuted, "
        "COUNT(*) AS total "
        "FROM lead_preconditions WHERE lead_id=?",
        (lead["id"],),
    ).fetchone()
    mutations = conn.execute(
        "SELECT COUNT(*) AS n FROM lead_mutations WHERE lead_id=?",
        (lead["id"],),
    ).fetchone()["n"]
    return {
        "lead_number": lead["number"],
        "mutations": mutations,
        "preconditions_present": counts["present"] or 0,
        "preconditions_refuted": counts["refuted"] or 0,
        "parked_days": days_parked,
        "promoted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lead_id": lead["id"],
    }


def promote_lead(conn: sqlite3.Connection, lead_id: int, klass: str,
                 severity: str, action: str) -> int:
    """Lead -> finding (I9/I10). Gate: both halves proven, payload non-empty,
    active (non-archived) target, klass in taxonomy, severity in the
    allow-list. The finding is INSERTed through the existing add_finding (all
    finding gates apply unchanged — the lead adds its gates on top, it does
    not replace them), findings.lead_id is set, and the frozen provenance
    snapshot lands in findings.lead_provenance. After promote the lead's
    verdicts are immutable: editing history would rewrite the snapshot.

    R2-02: `action` is an explicit parameter (CLI --action, default 'read') —
    a mutate-flavored lead must be born as action='mutate' and therefore hits
    the same RoE default-deny gate as every other mutate finding; the lead
    lane must not be a quieter road around the rules of engagement.

    E12: the whole promote is ONE transaction (BEGIN IMMEDIATE ... one COMMIT
    at the end). It previously spanned two commits (inside add_finding, then
    here) — a crash between them stranded an orphan finding (lead_id IS NULL)
    with the lead still promotable, so a retry minted a duplicate."""
    lead = get_lead(conn, lead_id)
    target = _require_active_target(conn, lead["target_id"])
    if lead["state"] == "promoted":
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is already promoted "
            f"(finding #{lead['promoted_finding_id']})"
        )
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — only open or "
            "mutating leads promote"
        )
    unproven = [half for half in LEAD_HALVES if lead[f"{half}_verdict"] != "proven"]
    if unproven:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} promote requires BOTH halves proven — "
            f"still unproven: {', '.join(unproven)}"
        )
    if not lead["payload"]:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} promote requires a non-empty payload"
        )
    # One transaction from here to the single COMMIT below (E12). BEGIN
    # IMMEDIATE takes the write lock up front; every statement between here
    # and the final commit either lands together or not at all.
    conn.execute("BEGIN IMMEDIATE")
    try:
        # The finding is born through the existing add_finding gate (I10): klass
        # taxonomy, severity, phase scoping, secrets — the lead adds its gates,
        # it does not bypass theirs.
        finding_id = add_finding(
            conn, lead["target_id"], lead["title"], klass, severity,
            notes=f"promoted from {_lead_labeled(lead_id)} (payload: {lead['payload']})",
            action=action,
            commit=False,
        )
        # B-L27 (arbiter-confirmed): add_finding auto-links to the latest OPEN wave,
        # but a promote in the wave GAP (no open wave) leaves wave_id NULL and the
        # finding then vanishes from wave economics. Belt here + suspenders in
        # open_wave (retro-link of gap-born findings) close the class both ways.
        open_wave_row = conn.execute(
            "SELECT id FROM waves WHERE target_id=? AND ev_verdict='' ORDER BY number DESC LIMIT 1",
            (lead["target_id"],),
        ).fetchone()
        if open_wave_row is None:
            conn.execute(
                "UPDATE findings SET wave_id=NULL WHERE id=?", (finding_id,)
            )
        provenance = _build_provenance(conn, lead)
        conn.execute(
            "UPDATE findings SET lead_id=?, lead_provenance=? WHERE id=?",
            (lead_id, json.dumps(provenance, sort_keys=True), finding_id),
        )
        conn.execute(
            "UPDATE leads SET state='promoted', promoted_finding_id=?, updated_at=datetime('now') "
            "WHERE id=?",
            (finding_id, lead_id),
        )
        log_event(conn, target["id"], "lead_promoted",
                  f"{_lead_labeled(lead_id)} -> finding #{finding_id} [{severity}] {klass}")
    except BaseException:
        # Crash/gate-failure mid-promote: roll the partial birth back so no
        # orphan finding (lead_id NULL) can survive and the lead stays
        # promotable for a clean retry.
        conn.rollback()
        raise
    conn.commit()
    return finding_id


def set_lead_payload(conn: sqlite3.Connection, lead_id: int, payload: str) -> None:
    """Set (or fill) the payload of an active lead. This is the only lead edit
    that stays legal AFTER promote besides verdict reads — no: it is BLOCKED
    post-promote too, because the payload is part of the promoted finding's
    provenance trail (I9: the snapshot must not be rewriteable)."""
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — "
            "payload edits are only admissible while open or mutating "
            "(a promoted lead's provenance is frozen)"
        )
    if not payload or not payload.strip():
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} payload must be non-empty"
        )
    assert_no_secrets(payload, "payload")
    conn.execute(
        "UPDATE leads SET payload=?, updated_at=datetime('now') WHERE id=?",
        (redact(payload.strip()), lead_id),
    )
    log_event(conn, lead["target_id"], "lead_payload_set",
              f"{_lead_labeled(lead_id)} payload set ({len(payload.strip())} chars)")
    conn.commit()


def list_leads(conn: sqlite3.Connection, target_id: int) -> list:
    return conn.execute(
        "SELECT * FROM leads WHERE target_id=? ORDER BY id", (target_id,)
    ).fetchall()


# --- observation oracle (deterministic verdicts, not feelings) ---

ORACLE_ARTIFACT_TYPE = "oracle_verdict"
ORACLE_KEYS = ("status", "timing_ms", "body_sha", "size")


def _read_oracle_feature(path: str, side: str, lead_id: int) -> dict:
    """Read + validate one oracle feature file (I12, the A5 lesson: NaN/inf
    are refused at the source — sqlite would bind NaN as NULL). Required shape:
    {"status": int, "timing_ms": finite number, "body_sha": 64-hex, "size": int}."""
    real_path = os.path.expanduser(path)
    try:
        with open(real_path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} cannot read {side} feature file: {path}"
        )
    except UnicodeDecodeError:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} feature file is not valid utf-8: {path}"
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} feature file is not valid JSON: {path} ({e})"
        )
    if not isinstance(data, dict):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} feature must be a JSON object: {path}"
        )
    missing = [k for k in ORACLE_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} feature missing keys {missing} "
            f"(required: {list(ORACLE_KEYS)}): {path}"
        )
    timing = data["timing_ms"]
    if isinstance(timing, bool) or not isinstance(timing, (int, float)) or not math.isfinite(timing):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} timing_ms must be a finite number "
            f"(NaN/inf refused at the source — A5); got {timing!r}"
        )
    for key in ("status", "size"):
        val = data[key]
        if isinstance(val, bool) or not isinstance(val, int):
            raise ValueError(
                f"BLOCKED: {_lead_labeled(lead_id)} {side} {key} must be an integer; got {val!r}"
            )
    # B-L24 (batch 3): bound the physical ranges — a negative or absurd value
    # has no meaning for an HTTP observation (status -5, size -1, a timing of
    # 10**12 ms) and only feeds the anomaly path with fiction. Refuse at the
    # source (the A5 lesson): the oracle decides on numbers, not on stories.
    if not (100 <= data["status"] <= 599):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} status out of range "
            f"(100-599); got {data['status']}"
        )
    if data["size"] < 0:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} size must be >= 0; got {data['size']}"
        )
    if timing < 0 or timing > 3_600_000:
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} timing_ms out of range "
            f"(0..3600000 = 1 hour); got {timing!r}"
        )
    sha = data["body_sha"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} {side} body_sha must be a 64-hex sha256; got {sha!r}"
        )
    return data


def oracle_verdict(baseline: dict, candidate: dict) -> str:
    """The deterministic verdict rule (I12). Pure function of the two feature
    objects — no db, no I/O — so tests and the oracle cannot disagree.

    delta_status = candidate.status != baseline.status
    delta_body   = candidate.body_sha != baseline.body_sha
    timing_anomaly = candidate.timing_ms >= 3 * max(baseline.timing_ms, 1.0)
                     AND candidate.timing_ms - baseline.timing_ms >= 500.0
    delta (status or body): anomaly -> 'unknown', else 'confirmed'
    no delta:               anomaly -> 'unknown', else 'refuted'
    """
    delta_status = candidate["status"] != baseline["status"]
    delta_body = candidate["body_sha"].lower() != baseline["body_sha"].lower()
    timing_anomaly = (
        candidate["timing_ms"] >= 3 * max(baseline["timing_ms"], 1.0)
        and (candidate["timing_ms"] - baseline["timing_ms"]) >= 500.0
    )
    if delta_status or delta_body:
        return "unknown" if timing_anomaly else "confirmed"
    return "unknown" if timing_anomaly else "refuted"


def record_oracle_verdict(conn: sqlite3.Connection, lead_id: int, half: str,
                          baseline: dict, candidate: dict) -> tuple:
    """Run the deterministic rule on two validated feature objects, store the
    verdict + both raw feature JSONs as an event (artifact_type oracle_verdict),
    and return (verdict, event_id). 'unknown' licenses setting the half to
    'ambiguous' — the ONLY path to ambiguous (I2); 'confirmed' sets the half
    proven (with the evidence the features carry), 'refuted' sets it refuted.
    """
    if half not in LEAD_HALVES:
        raise ValueError(f"BLOCKED: half must be one of {LEAD_HALVES}, not '{half}'")
    lead = get_lead(conn, lead_id)
    _require_active_target(conn, lead["target_id"])
    if lead["state"] not in ("open", "mutating"):
        raise ValueError(
            f"BLOCKED: {_lead_labeled(lead_id)} is {lead['state']} — the oracle runs "
            "on open or mutating leads"
        )
    verdict = oracle_verdict(baseline, candidate)
    detail = json.dumps({
        "verdict": verdict,
        "baseline": baseline,
        "candidate": candidate,
        "half": half,
    }, sort_keys=True)
    event_id = log_event(conn, lead["target_id"], ORACLE_ARTIFACT_TYPE, detail)
    evidence = (
        f"oracle event #{event_id}: baseline(status={baseline['status']},"
        f"timing={baseline['timing_ms']}ms,sha={baseline['body_sha'][:12]}...) vs "
        f"candidate(status={candidate['status']},timing={candidate['timing_ms']}ms,"
        f"sha={candidate['body_sha'][:12]}...)"
    )
    if verdict == "unknown":
        # ambiguous is legal HERE and only here: the verdict carries its oracle
        # event id on the mutation row (I2's receipt).
        _set_lead_half(conn, lead_id, half, "ambiguous", evidence, oracle_event_id=event_id)
    elif verdict == "confirmed":
        _set_lead_half(conn, lead_id, half, "proven", evidence, oracle_event_id=event_id)
    else:  # refuted
        _set_lead_half(conn, lead_id, half, "refuted", evidence, oracle_event_id=event_id)
    return verdict, event_id


def lead_contradictions(conn: sqlite3.Connection, target_id: int) -> list:
    """Lead honesty flags (I15): an 'open' lead older than 7 days with no
    payload has not become concrete — soft-flag it. Display-only.

    R2-08 (B-L11 sharper): the flag is not state-blind anymore — a PARKED
    payload-less lead is flagged too. Park used to silence the flag forever
    (and parked had no exit): the honesty flag must survive the park, since
    the tripwire row still prints in the brief."""
    flags = []
    rows = conn.execute(
        "SELECT id, number, state, created_at, julianday('now') - julianday(created_at) AS age_days "
        "FROM leads WHERE target_id=? AND state IN ('open','parked') "
        "AND (payload IS NULL OR payload='') "
        "AND julianday('now') - julianday(created_at) > 7 ORDER BY id",
        (target_id,),
    ).fetchall()
    for row in rows:
        suffix = " (still parked)" if row["state"] == "parked" else ""
        flags.append(
            f"!! lead L-{row['id']} still payload-less after {int(row['age_days'])} days{suffix}"
        )
    return flags


# --- taxonomy (label discipline: growth is retro-gated) ---

def add_klass(conn: sqlite3.Connection, name: str, from_finding: Optional[int] = None) -> str:
    """Grow the taxonomy with a new klass. Only entry point for new classes —
    insert-time klass is locked to the taxonomies table (see triggers above).
    With from_finding, a quarantined 'Unknown' finding is re-tagged and a
    law_candidate lesson is recorded."""
    clean = (name or "").strip()
    if not clean or re.search(r"\s", clean) or len(clean) > 24:
        raise ValueError("BLOCKED: klass name must be a single word of at most 24 characters")
    dup = conn.execute(
        "SELECT 1 FROM taxonomies WHERE kind='klass' AND value=? LIMIT 1", (clean,)
    ).fetchone()
    if dup is not None:
        raise ValueError(f"BLOCKED: klass '{clean}' already exists")
    conn.execute("INSERT INTO taxonomies (kind, value, source) VALUES ('klass', ?, 'cli')", (clean,))
    log_event(conn, None, "klass_added", clean)
    if from_finding is not None:
        f = _row(conn, "SELECT * FROM findings WHERE id = ?", (from_finding,),
                 label=f"finding #{from_finding}")
        _require_active_target(conn, f["target_id"])
        conn.execute("UPDATE findings SET klass=? WHERE id=?", (clean, from_finding))
        t = get_target(conn, f["target_id"])
        log_event(conn, f["target_id"], "klass_added",
                  f"finding #{from_finding} re-tagged '{f['klass']}' -> '{clean}'",
                  finding_id=from_finding)
        add_lesson(conn, t["name"], f"new klass '{clean}' promoted from finding #{from_finding}",
                   scope="law_candidate", target_id=f["target_id"])
    conn.commit()
    return clean


def find_contradictions(conn: sqlite3.Connection, target_id: int) -> list:
    """Display-only honesty report. Returns a list of strings ('!! '-prefixed);
    [] when clean. Read-only by design: it reports, it never blocks."""
    flags = []
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE target_id=? "
        "AND severity IN ('critical','high') AND ladder_status='theoretical' AND evidence_ref=''",
        (target_id,),
    ).fetchone()["n"]
    if n:
        flags.append(f"!! {n} loud claim(s) (critical/high) still theoretical with no evidence")
    for w in conn.execute(
        "SELECT number FROM waves WHERE target_id=? AND ev_verdict='continue' AND findings_new=0 "
        "ORDER BY number",
        (target_id,),
    ).fetchall():
        flags.append(f"!! wave {w['number']} continued with 0 new findings")
    t = get_target(conn, target_id)
    if t["phase"] in ("report", "retro"):
        proven = conn.execute(
            "SELECT COUNT(*) AS n FROM findings WHERE target_id=? AND ladder_status='proven-live'",
            (target_id,),
        ).fetchone()["n"]
        if proven == 0:
            flags.append(f"!! in {t['phase']} with zero proven-live findings")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE target_id=? AND klass='Unknown'",
        (target_id,),
    ).fetchone()["n"]
    if n:
        flags.append(f"!! {n} unclassified finding(s) — taxonomy hasn't learned this yet")
    # retroactive self-authorization: RoE loosened after mutate findings existed
    earliest_mutate = conn.execute(
        "SELECT MIN(created_at) AS earliest FROM findings WHERE target_id=? AND action='mutate'",
        (target_id,),
    ).fetchone()["earliest"]
    if earliest_mutate:
        last_roe = conn.execute(
            "SELECT created_at FROM events WHERE target_id=? AND kind='roe_updated' "
            "ORDER BY id DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        if last_roe is not None and last_roe["created_at"] > earliest_mutate:
            flags.append(
                "!! RoE changed after mutate finding(s) existed — check for retroactive authorization"
            )
    # on-chain mismatch: a tx_hash verifier event means a real broadcast happened
    mismatch = conn.execute(
        "SELECT COUNT(*) AS n FROM findings f WHERE f.target_id=? AND f.action IN ('read','recon') "
        "AND EXISTS (SELECT 1 FROM events e WHERE e.finding_id=f.id "
        "AND e.kind='verifier_pass' AND e.detail LIKE 'tx_hash:%')",
        (target_id,),
    ).fetchone()["n"]
    if mismatch:
        flags.append(
            f"!! {mismatch} on-chain broadcast(s) (tx_hash) on non-mutate finding(s)"
        )
    return flags + lead_contradictions(conn, target_id)


# --- rules of engagement (per target, default-deny for mutate) ---
# NOTE: RoE `hosts` is INFORMATIONAL ONLY. The DB cannot verify what host a PoC
# actually touched — it has no view of the wire — so only `actions` is enforced
# (the mutate promote gate). Hosts are recorded for the audit trail and reports.


def set_roe(conn: sqlite3.Connection, target_id: int, hosts: str, actions: str,
            notes: str = "") -> None:
    """Set (or replace) the rules of engagement for a target.

    Default-deny: a target with no RoE row allows no mutate promotions. Every
    change logs a 'roe_updated' event, so loosening the RoE after mutate
    findings already exist is visible to `hunt status` (retroactive
    self-authorization check).
    """
    _require_active_target(conn, target_id)
    parsed = [a.strip() for a in actions.split(",") if a.strip()]
    if not parsed:
        raise ValueError("BLOCKED: RoE must allow at least one action")
    for a in parsed:
        if a not in ROE_ACTIONS:
            raise ValueError(
                f"BLOCKED: RoE actions must be a comma list from {sorted(ROE_ACTIONS)}"
            )
    normalized = ",".join(sorted(set(parsed)))
    existing = get_roe(conn, target_id)
    if existing is None:
        conn.execute(
            "INSERT INTO rules_of_engagement (target_id, hosts, actions, notes) VALUES (?, ?, ?, ?)",
            (target_id, hosts, normalized, notes),
        )
    else:
        conn.execute(
            "UPDATE rules_of_engagement SET hosts=?, actions=?, notes=? WHERE target_id=?",
            (hosts, normalized, notes, target_id),
        )
    log_event(conn, target_id, "roe_updated", f"actions={normalized} hosts={hosts}")
    conn.commit()


def get_roe(conn: sqlite3.Connection, target_id: int):
    return conn.execute(
        "SELECT * FROM rules_of_engagement WHERE target_id=?", (target_id,)
    ).fetchone()


# --- waves ---

def open_wave(conn: sqlite3.Connection, target_id: int, lanes: str) -> int:
    """Wave N+1 is LOCKED until wave N has ev_verdict AND re-audit recorded."""
    t = _require_active_target(conn, target_id)
    # Phase scoping: waves are hunting-phase work (verify may finish one out).
    if t["phase"] not in ("hunting", "verify"):
        raise ValueError(
            "BLOCKED: findings/waves belong to the hunting or verify phase "
            f"(current phase: {t['phase']}) "
            f"| NEXT: hunt next --target {target_id}"
        )
    last = conn.execute(
        "SELECT * FROM waves WHERE target_id=? ORDER BY number DESC LIMIT 1", (target_id,)
    ).fetchone()
    next_number = 1
    if last is not None:
        if not last["ev_verdict"]:
            raise ValueError(
                f"BLOCKED: wave {last['number']} has no ev_verdict (continue/exhausted/pivot). "
                f"Close the wave first. | NEXT: hunt wave close --wave-id {last['id']} --verdict exhausted"
            )
        if not last["reaudit_done"]:
            raise ValueError(
                f"BLOCKED: wave {last['number']} has no re-audit recorded. "
                "Re-audit previous wave claims (confirmed/overturned) before opening a new wave. "
                f"| NEXT: hunt wave reaudit --wave-id {last['id']} --summary \"confirmed <what>, overturned <what>, why\""
            )
        next_number = last["number"] + 1
    cur = conn.execute(
        "INSERT INTO waves (target_id, number, lanes, reaudit_done) VALUES (?, ?, ?, 0)",
        (target_id, next_number, lanes),
    )
    # B-L27: retro-link findings born in the wave GAP (promoted between waves,
    # wave_id NULL) to the wave that just opened, so close_wave economics count
    # them and the economic stop cannot misfire on hidden findings.
    conn.execute(
        "UPDATE findings SET wave_id=? WHERE target_id=? AND wave_id IS NULL "
        "AND ladder_status != 'overturned'",
        (int(cur.lastrowid), target_id),
    )
    log_event(conn, target_id, "wave_opened", f"wave {next_number} lanes={lanes}")
    conn.commit()
    return int(cur.lastrowid)


def record_reaudit(conn: sqlite3.Connection, wave_id: int, summary: str = "") -> None:
    """Mark wave as re-audited (claims confirmed/overturned recorded)."""
    if not summary or len(summary.strip()) < 20:
        raise ValueError(
            "BLOCKED: re-audit requires a real summary (min 20 chars) — "
            "what was confirmed, what was overturned, and why"
        )
    wave = _row(conn, "SELECT * FROM waves WHERE id = ?", (wave_id,),
                label=f"wave #{wave_id}")
    _require_active_target(conn, wave["target_id"])
    confirmed = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE wave_id=? AND ladder_status IN ('in-code','proven-live')",
        (wave_id,),
    ).fetchone()["n"]
    overturned = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE wave_id=? AND ladder_status='overturned'",
        (wave_id,),
    ).fetchone()["n"]
    conn.execute(
        "UPDATE waves SET reaudit_done=1, notes=notes || ? WHERE id=?",
        (f" reaudit: {summary.strip()} | confirmed={confirmed} overturned={overturned}", wave_id),
    )
    log_event(conn, None, "wave_reaudited",
              f"wave {wave_id} confirmed={confirmed} overturned={overturned} {summary.strip()}")
    conn.commit()


def close_wave(conn: sqlite3.Connection, wave_id: int, ev_verdict: str) -> None:
    """Close a wave. findings_new is COMPUTED from wave-linked findings, never claimed."""
    if ev_verdict not in ("continue", "exhausted", "pivot"):
        raise ValueError("ev_verdict must be: continue / exhausted / pivot")
    wave = _row(conn, "SELECT * FROM waves WHERE id = ?", (wave_id,),
                label=f"wave #{wave_id}")
    # A2: the archived lock fires before anything else — in particular before a
    # second exhausted close could re-run archive_target on a closed hunt.
    _require_active_target(conn, wave["target_id"])
    findings_new = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE wave_id=?", (wave_id,)
    ).fetchone()["n"]
    if findings_new == 0 and ev_verdict == "continue":
        prev = conn.execute(
            "SELECT * FROM waves WHERE target_id=? AND number<? ORDER BY number DESC LIMIT 1",
            (wave["target_id"], wave["number"]),
        ).fetchone()
        if prev is not None and prev["findings_new"] == 0 and prev["ev_verdict"] == "continue":
            raise ValueError(
                "BLOCKED: two consecutive waves with zero new findings — "
                "verdict must be 'exhausted' or 'pivot' (economic stop)"
            )
    conn.execute("UPDATE waves SET findings_new=?, ev_verdict=? WHERE id=?", (findings_new, ev_verdict, wave_id))
    if ev_verdict == "exhausted":
        archive_target(conn, wave["target_id"], f"wave {wave['number']} exhausted - economic stop")
    log_event(conn, wave["target_id"], "wave_closed",
              f"wave {wave['number']} verdict={ev_verdict} findings_new={findings_new}")
    conn.commit()


def list_waves(conn: sqlite3.Connection, target_id: int) -> list:
    return conn.execute("SELECT * FROM waves WHERE target_id=? ORDER BY number", (target_id,)).fetchall()


# --- surfaces & chains (capability stack: "0-day as a machine") ---
# The Architect's map and the Chainer's graph stop being prose and become
# ledger objects. Surfaces make the Blind Spot Scanner mechanical: a trust
# boundary that no lead and no finding ever pointed at IS the blind spot, and
# surface_coverage computes it instead of an operator remembering it. Chains
# make novelty checkable: the ordered klass pattern of a chain's finding steps
# (+ entry + impact) is compared against every chain recorded earlier in this
# ledger, across all targets — LEDGER-LOCAL novelty, honestly not world-novelty.

SURFACE_KINDS = ("endpoint", "trust_boundary", "invariant", "component")
CHAIN_STEP_KINDS = ("finding", "lead")


def add_surface(conn: sqlite3.Connection, target_id: int, kind: str, name: str,
                notes: str = "") -> int:
    """Record one surface from the Architect's map: a named endpoint, trust
    boundary, invariant, or component on an active (non-archived) target.

    The target must exist and not be archived; kind is validated against
    SURFACE_KINDS (the map is data, not free-form prose). Returns the surface id.
    """
    if kind not in SURFACE_KINDS:
        raise ValueError(
            f"BLOCKED: surface kind must be one of {list(SURFACE_KINDS)}; got '{kind}'"
        )
    _require_active_target(conn, target_id)
    name = redact(name or "")
    notes = redact(notes or "")
    cur = conn.execute(
        "INSERT INTO surfaces (target_id, kind, name, notes) VALUES (?, ?, ?, ?)",
        (target_id, kind, name, notes),
    )
    log_event(conn, target_id, "surface_added", f"{kind}: {name}")
    conn.commit()
    return int(cur.lastrowid)


def list_surfaces(conn: sqlite3.Connection, target_id: int) -> list:
    return conn.execute(
        "SELECT * FROM surfaces WHERE target_id=? ORDER BY id", (target_id,)
    ).fetchall()


def surface_coverage(conn: sqlite3.Connection, target_id: int) -> dict:
    """The Blind Spot Scanner, mechanical. For every surface of the target:

      has_lead    — any lead row pins to it (leads.surface_id)
      has_finding — any finding row pins to it (findings.surface_id)

    Returns {"rows": [...], "blind_spots": [...]}. rows are dicts
    {id, kind, name, has_lead, has_finding}; blind_spots is the subset where
    kind='trust_boundary' AND has_lead=False AND has_finding=False — the
    mechanically-computed answer to "what did I NOT look at".

    Honest limit: coverage means "the ledger contains a pointer", not "the
    pointer was ever probed". It is display-only by design — a blind spot is
    missing work, not a contradiction, so it never feeds find_contradictions.
    """
    rows = []
    for s in conn.execute(
        "SELECT s.id, s.kind, s.name, "
        "EXISTS(SELECT 1 FROM leads l WHERE l.surface_id = s.id) AS has_lead, "
        "EXISTS(SELECT 1 FROM findings f WHERE f.surface_id = s.id) AS has_finding "
        "FROM surfaces s WHERE s.target_id=? ORDER BY s.id",
        (target_id,),
    ).fetchall():
        rows.append({
            "id": s["id"],
            "kind": s["kind"],
            "name": s["name"],
            "has_lead": bool(s["has_lead"]),
            "has_finding": bool(s["has_finding"]),
        })
    blind_spots = [
        r for r in rows
        if r["kind"] == "trust_boundary" and not r["has_lead"] and not r["has_finding"]
    ]
    return {"rows": rows, "blind_spots": blind_spots}


def add_chain(conn: sqlite3.Connection, target_id: int, name: str, entry: str = "",
              impact: str = "", notes: str = "") -> int:
    """Register a chain (the Chainer's gadget graph) on an active target.
    Name is required — an unnamed chain cannot be claimed later. entry/impact
    are the chain story's first and last words; both participate in the
    pattern-novelty key, so say what the chain actually does. Returns the id."""
    clean = (name or "").strip()
    if not clean:
        raise ValueError("BLOCKED: chain name must not be empty")
    _require_active_target(conn, target_id)
    name = redact(clean)
    entry = redact(entry or "")
    impact = redact(impact or "")
    notes = redact(notes or "")
    cur = conn.execute(
        "INSERT INTO chains (target_id, name, entry, impact, notes) VALUES (?, ?, ?, ?, ?)",
        (target_id, name, entry, impact, notes),
    )
    log_event(conn, target_id, "chain_added", f"chain #{cur.lastrowid}: {name}")
    conn.commit()
    return int(cur.lastrowid)


def link_step(conn: sqlite3.Connection, chain_id: int, position: int, kind: str,
              ref_id: int) -> None:
    """Append one ordered step to a chain: kind='finding' points at
    findings.id, kind='lead' points at leads.id. Guards: the step kind is one
    of CHAIN_STEP_KINDS, position is an integer >= 1 and unique per chain
    (UNIQUE(chain_id, position) is the source of truth), the referenced
    finding/lead must exist, and the same (kind, ref_id) gadget may not appear
    twice in one chain — a chain that crosses the same gadget twice is a
    rendering error, not a deeper exploit."""
    if kind not in CHAIN_STEP_KINDS:
        raise ValueError(
            f"BLOCKED: step kind must be one of {list(CHAIN_STEP_KINDS)}; got '{kind}'"
        )
    if isinstance(position, bool) or not isinstance(position, int) or position < 1:
        raise ValueError(f"BLOCKED: position must be an integer >= 1; got {position!r}")
    chain = conn.execute("SELECT * FROM chains WHERE id=?", (chain_id,)).fetchone()
    if chain is None:
        raise ValueError(f"BLOCKED: chain #{chain_id} does not exist")
    table = "findings" if kind == "finding" else "leads"
    ref = conn.execute(
        f"SELECT 1 FROM {table} WHERE id=? LIMIT 1", (ref_id,)
    ).fetchone()
    if ref is None:
        raise ValueError(
            f"BLOCKED: chain step kind='{kind}' ref #{ref_id} does not exist"
        )
    dup = conn.execute(
        "SELECT 1 FROM chain_steps WHERE chain_id=? AND kind=? AND ref_id=? LIMIT 1",
        (chain_id, kind, ref_id),
    ).fetchone()
    if dup is not None:
        label = f"F-{ref_id}" if kind == "finding" else f"L-{ref_id}"
        raise ValueError(
            f"BLOCKED: {label} is already a step of chain #{chain_id} — "
            "a gadget appears at most once per chain"
        )
    try:
        conn.execute(
            "INSERT INTO chain_steps (chain_id, position, kind, ref_id) VALUES (?, ?, ?, ?)",
            (chain_id, position, kind, ref_id),
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"BLOCKED: position {position} in chain #{chain_id} is already occupied — "
            "one step per position (UNIQUE(chain_id, position))"
        )
    label = f"F-{ref_id}" if kind == "finding" else f"L-{ref_id}"
    log_event(conn, chain["target_id"], "chain_step_linked",
              f"chain #{chain_id} step {position}: {kind} {label}")
    conn.commit()


def _chain_pattern_key(conn: sqlite3.Connection, chain: sqlite3.Row) -> str:
    """The canonical novelty key for one chain.

    Pattern key = the ORDERED tuple of klass values of the chain's FINDING
    steps (by position) + the entry string + the impact string. Built the same
    way for every chain, so equality means "same gadget classes in the same
    order, entering and landing the same way".

    Leads: this repo's leads table has NO klass column — a lead is a
    pre-classification hypothesis and klass is assigned only when a lead
    promotes into a finding. Lead steps therefore contribute nothing to the
    key (they mark the chain's narrative positions only); the pattern is
    carried by the finding steps alone. Documented deliberate choice.
    """
    klasses = [
        r["klass"] for r in conn.execute(
            "SELECT f.klass AS klass FROM chain_steps cs JOIN findings f ON f.id = cs.ref_id "
            "WHERE cs.chain_id = ? AND cs.kind = 'finding' ORDER BY cs.position",
            (chain["id"],),
        ).fetchall()
    ]
    return f"klasses={klasses!r}|entry={chain['entry']!r}|impact={chain['impact']!r}"


def chain_novelty(conn: sqlite3.Connection, chain_id: int) -> dict:
    """Has this chain's PATTERN been recorded in the ledger before?

    The pattern key (see _chain_pattern_key) is compared against the key of
    every chain recorded EARLIER in this ledger — lower id (AUTOINCREMENT
    insert order), across ALL targets, not just this chain's target. Returns:

      {"pattern": the key string,
       "novel": True when no earlier chain shares it,
       "seen_in": ["chain #<id> '<name>' (target #<tid>)", ...] — earlier matches}

    The FIRST statement of a pattern stays novel: a later duplicate never
    retroactively un-novels the earlier chain.

    Honest boundary: this is LEDGER-LOCAL novelty — the pattern has never
    appeared in YOUR own recorded history. It is not world-novelty. The system
    cannot see hunts run outside this db, other teams' work, or public
    disclosures; "novel" here means "new to you".
    """
    chain = conn.execute("SELECT * FROM chains WHERE id=?", (chain_id,)).fetchone()
    if chain is None:
        raise ValueError(f"BLOCKED: chain #{chain_id} does not exist")
    key = _chain_pattern_key(conn, chain)
    seen_in = []
    for other in conn.execute(
        "SELECT * FROM chains WHERE id < ? ORDER BY id", (chain_id,)
    ).fetchall():
        if _chain_pattern_key(conn, other) == key:
            seen_in.append(
                f"chain #{other['id']} '{other['name']}' (target #{other['target_id']})"
            )
    return {"pattern": key, "novel": not seen_in, "seen_in": seen_in}


def chain_detail(conn: sqlite3.Connection, chain_id: int) -> str:
    """Markdown render of one chain: name, entry, impact, the ordered step
    lines (`step N: [F-<id>] <klass> <title> -> ` for findings; lead steps
    render as `[L-<id>] <title>` — leads carry no klass), the ledger-local
    novelty verdict, and created_at. Read-only."""
    chain = conn.execute("SELECT * FROM chains WHERE id=?", (chain_id,)).fetchone()
    if chain is None:
        raise ValueError(f"BLOCKED: chain #{chain_id} does not exist")
    novelty = chain_novelty(conn, chain_id)
    lines = [
        f"### Chain #{chain['id']}: {chain['name']}",
        f"- entry: {chain['entry'] or '(none recorded)'}",
        f"- impact: {chain['impact'] or '(none recorded)'}",
        "- steps:",
    ]
    steps = conn.execute(
        "SELECT * FROM chain_steps WHERE chain_id=? ORDER BY position", (chain_id,)
    ).fetchall()
    if not steps:
        lines.append("  (no steps linked)")
    for step in steps:
        if step["kind"] == "finding":
            ref = conn.execute(
                "SELECT klass, title FROM findings WHERE id=?", (step["ref_id"],)
            ).fetchone()
            if ref is not None:
                lines.append(
                    f"  step {step['position']}: [F-{step['ref_id']}] "
                    f"{ref['klass']} {ref['title']} -> "
                )
            else:
                lines.append(
                    f"  step {step['position']}: [F-{step['ref_id']}] (finding no longer exists) -> "
                )
        else:
            ref = conn.execute(
                "SELECT title FROM leads WHERE id=?", (step["ref_id"],)
            ).fetchone()
            title = ref["title"] if ref is not None else "(lead no longer exists)"
            lines.append(
                f"  step {step['position']}: [L-{step['ref_id']}] {title} -> "
            )
    if novelty["novel"]:
        lines.append(
            "- novelty: NOVEL — this pattern has never appeared in this ledger before"
        )
    else:
        lines.append(
            "- novelty: SEEN BEFORE — same pattern in " + "; ".join(novelty["seen_in"])
        )
    lines.append(
        "  (novelty is ledger-local: never seen in your own recorded history, "
        "not world-novelty)"
    )
    lines.append(f"- created: {chain['created_at']}")
    return redact("\n".join(lines))


# --- lessons ---

def add_lesson(conn: sqlite3.Connection, source_target: str, pattern: str, scope: str = "skill",
               notes: str = "", target_id: Optional[int] = None) -> int:
    if scope not in ("skill", "state_rule", "soul", "law_candidate"):
        raise ValueError("scope must be: skill / state_rule / soul / law_candidate")
    cur = conn.execute(
        "INSERT INTO lessons (source_target, pattern, scope, notes, target_id) VALUES (?, ?, ?, ?, ?)",
        (source_target, pattern, scope, notes, target_id),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_lessons(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM lessons ORDER BY id DESC").fetchall()


def reword_lesson(conn: sqlite3.Connection, lesson_id: int, pattern: str,
                  notes: Optional[str] = None) -> None:
    """Reword a lesson (L2.1): rewrite `pattern` (and optionally `--notes`).

    The archive gate is unchanged ON PURPOSE: lessons stay writable on archived
    targets — memory additions and corrections are not history rewrites, and a
    mangled (MSYS-mangled) pattern must be fixable after the fact. The new
    pattern (and notes, when given) pass the secrets gate; the old pattern
    rides in the `lesson_reworded` event so the reword is auditable. Not a
    general edit API — scope and target binding are NOT editable here."""
    row = _row(conn, "SELECT * FROM lessons WHERE id = ?", (lesson_id,),
               label=f"lesson #{lesson_id}")
    clean = (pattern or "").strip()
    if not clean:
        raise ValueError("BLOCKED: reword requires a non-empty pattern")
    assert_no_secrets(clean, "pattern")
    clean = redact(clean)
    if notes is not None:
        assert_no_secrets(notes, "notes")
        notes = redact(notes)
        conn.execute(
            "UPDATE lessons SET pattern=?, notes=? WHERE id=?",
            (clean, notes, lesson_id),
        )
    else:
        conn.execute("UPDATE lessons SET pattern=? WHERE id=?", (clean, lesson_id))
    log_event(conn, row["target_id"], "lesson_reworded",
              f"lesson #{lesson_id} reworded: {row['pattern']!r} -> {clean!r}")
    conn.commit()


# --- report ---

def export_report(conn: sqlite3.Connection, target_id: int) -> str:
    t = get_target(conn, target_id)
    findings = list_findings(conn, target_id)
    waves = list_waves(conn, target_id)
    lines = [
        f"# HUNT-OS Report: {t['name']}",
        f"- url: {t['url']}",
        f"- chain: {t['chain']} | age: {t['age_days']}d | tvl: ${t['tvl_usd']:,.0f}",
        f"- phase: {t['phase']} | ev_score: {t['ev_score']}",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("(none recorded)")
    for f in findings:
        lines.append(f"### F-{f['id']} [{f['severity'].upper()}] {f['title']}")
        lines.append(f"- class: {f['klass']} | ladder: {f['ladder_status']}")
        if f["evidence_ref"]:
            lines.append(f"- evidence: {f['evidence_ref']}")
        if f["poc_path"]:
            lines.append(f"- poc: {f['poc_path']}")
        if f["falsifier"]:
            lines.append(f"- falsifier: {f['falsifier']}")
        if f["overturned_by"]:
            lines.append(f"- OVERTURNED by: {f['overturned_by']}")
        if f["notes"]:
            lines.append(f"- notes: {f['notes']}")
        lines.append("")
    lines.append("## Waves")
    for w in waves:
        lines.append(f"- wave {w['number']}: lanes={w['lanes']} new_findings={w['findings_new']} verdict={w['ev_verdict']}")
    # Chains (capability stack): the Chainer's gadget graph rendered from the
    # ledger, each with its ledger-local novelty verdict. Findings-only chains
    # render fully (klass + title per step); lead steps render as L-<id> <title>
    # (leads carry no klass of their own).
    lines.append("## Chains")
    chain_rows = conn.execute(
        "SELECT id FROM chains WHERE target_id=? ORDER BY id", (target_id,)
    ).fetchall()
    if not chain_rows:
        lines.append("(none recorded)")
    for c in chain_rows:
        lines.append(chain_detail(conn, c["id"]))
        lines.append("")
    body = "\n".join(lines) + "\n"
    # Order matters: the sha256 digest is computed over the RAW body (what is
    # actually stored in the DB) BEFORE redaction. Redaction is a display-time
    # courtesy for the emitted report; the footer names the pre-redaction
    # digest so the report still verifies against the stored content.
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    body = redact(body)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return body + (f"<!-- hunt-report sha256:{digest} target:{t['id']} "
                   f"db:{get_meta(conn, 'db_id')[:12]} generated:{stamp} -->\n")


# The footer written by export_report: `<!-- hunt-report sha256:<64-hex>
# target:<id> db:<id12> generated:<utc> -->`. Everything BEFORE this comment
# line is the body the digest was computed over.
_REPORT_FOOTER_RE = re.compile(r"<!--\s*hunt-report\s+sha256:([0-9a-f]{64})[^>]*-->")


def verify_report_file(path: str) -> str:
    """Verify a report file against its hunt-report sha256 footer.

    Returns the verdict string; raises ValueError (BLOCKED:) on tampering.
    The digest is recomputed over the content BEFORE the footer comment line
    (the footer is appended as body + footer, so the body is everything up to
    the footer's `<!--`).
    """
    real_path = os.path.expanduser(path)
    try:
        with open(real_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        raise ValueError(f"BLOCKED: cannot read report file: {path}")
    except UnicodeDecodeError:
        # fail-closed with a named cause: a report that is not valid utf-8
        # cannot be fingerprint-verified (cp1252-mangled writes, A14).
        raise ValueError(
            f"BLOCKED: cannot decode report file as utf-8: {path} — "
            "reports must be written with encoding='utf-8' (hunt report does)"
        )
    m = _REPORT_FOOTER_RE.search(text)
    if m is None:
        raise ValueError(
            "BLOCKED: no hunt-report footer found — "
            "this file was not generated by hunt report"
        )
    body = text[: m.start()]
    actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual != m.group(1):
        raise ValueError(
            "BLOCKED: report has been tampered with — "
            "content hash does not match the footer"
        )
    # The footer must be the LAST thing in the file. Content appended after it
    # is outside the hashed region and would otherwise smuggle claims into a
    # "verified" report.
    if text[m.end():].strip():
        raise ValueError(
            "BLOCKED: report has been tampered with — "
            "content found after the hunt-report footer"
        )
    return "report matches its fingerprint"


# --- brief (the opening read: memory compounds only if you read it back) ---

def export_brief(conn: sqlite3.Connection, target_id: int) -> str:
    """Opening read for the next hunt round: everything the system remembers.

    Read-only by design (SELECTs + the contradiction engine, no writes). One
    markdown page: target state, lessons (target-bound first, then global),
    current contradictions, wave history, findings by ladder, surfaces &
    coverage (the Architect's map with its mechanically-computed blind spots),
    and the klass taxonomy — so round N+1 starts from what round N actually
    learned.
    """
    t = get_target(conn, target_id)
    lines = [
        f"# Brief: {t['name']}",
        f"- url: {t['url']}",
        f"- chain: {t['chain']} | phase: {t['phase']} | ev_score: {t['ev_score']}",
    ]
    if t["phase"] == "archived":
        lines.append(f"- archived: {t['archive_reason'] or '(no reason recorded)'}")

    # Lessons: target-bound first (newest first), then the global memory
    # (target_id IS NULL, newest first, max 10) — the hunt inherits the house.
    lines += ["", "## Lessons"]
    bound = conn.execute(
        "SELECT * FROM lessons WHERE target_id=? ORDER BY id DESC", (target_id,)
    ).fetchall()
    global_lessons = conn.execute(
        "SELECT * FROM lessons WHERE target_id IS NULL ORDER BY id DESC LIMIT 10"
    ).fetchall()
    lessons = list(bound) + list(global_lessons)
    if not lessons:
        lines.append("(none recorded — this hunt creates the first one)")
    for lesson in lessons:
        lines.append(f"- [{lesson['scope']}] {lesson['pattern']}")
        if lesson["notes"]:
            lines.append(f"  notes: {lesson['notes']}")

    # Contradictions: the same honesty engine `hunt status` displays (v0.4: it
    # includes the lead honesty flags — payload-less open leads, I15).
    lines += ["", "## Current contradictions"]
    flags = find_contradictions(conn, target_id)
    if not flags:
        lines.append("(clean)")
    for flag in flags:
        lines.append(flag)

    # Wave history: one line per wave, verdict and re-audit state included.
    lines += ["", "## Wave history"]
    waves = list_waves(conn, target_id)
    if not waves:
        lines.append("(no waves)")
    for w in waves:
        verdict = w["ev_verdict"] or "open"
        reaudit = "done" if w["reaudit_done"] else "pending"
        lines.append(
            f"wave {w['number']}: lanes={w['lanes']} findings_new={w['findings_new']} "
            f"verdict={verdict} reaudit={reaudit}"
        )

    # Findings by ladder: counts for every rung, then the non-overturned list.
    lines += ["", "## Findings by ladder"]
    findings = list_findings(conn, target_id)
    counts = {"theoretical": 0, "in-code": 0, "proven-live": 0, "overturned": 0}
    for f in findings:
        counts[f["ladder_status"]] = counts.get(f["ladder_status"], 0) + 1
    lines.append(
        f"theoretical={counts['theoretical']} in-code={counts['in-code']} "
        f"proven-live={counts['proven-live']} overturned={counts['overturned']}"
    )
    active = [f for f in findings if f["ladder_status"] != "overturned"]
    if not active:
        lines.append("(none)")
    for f in active:
        lines.append(f"F-{f['id']} [{f['ladder_status']}] ({f['klass']}/{f['action']}) {f['title']}")
        if f["falsifier"]:
            lines.append(f"  - falsifier: {f['falsifier']}")

    # Taxonomy: the klass allow-list as DATA, with operator growth annotated.
    lines += ["", "## Taxonomy"]
    taxa = conn.execute(
        "SELECT value, source FROM taxonomies WHERE kind='klass' ORDER BY rowid"
    ).fetchall()
    if not taxa:
        lines.append("(empty)")
    else:
        operator_added = sum(1 for r in taxa if r["source"] != "seed")
        annotation = f" ({operator_added} operator-added)" if operator_added else ""
        lines.append(", ".join(r["value"] for r in taxa) + annotation)

    # Leads (v0.4, I14): the observation ledger's tripwires. Shown here:
    #   - open + mutating: live work, each with its deterministic next mutation
    #   - parked: tripwire table (the retrigger condition)
    #   - killed WITH a retrigger: still a tripwire (the lead may wake)
    # Not shown: killed without a retrigger (a quiet death stays quiet) and
    # promoted (the lead already lives as a finding in the ladder above).
    lines += ["", "## Leads"]
    leads = list_leads(conn, target_id)
    if not leads:
        lines.append("(none)")
    shown_any = False
    for lead in leads:
        state = lead["state"]
        if state in ("open", "mutating"):
            nxt = next_mutation(conn, lead["id"])
            if nxt is not None:
                nxt_txt = f"next: {nxt['variable']}={nxt['value']!r}"
            else:
                nxt_txt = "next: none left — consider park (with a retrigger)"
            lines.append(
                f"L-{lead['id']} [{state}] ({lead['trigger_verdict']}/{lead['impact_verdict']}) "
                f"{lead['title']} — {nxt_txt}"
            )
            shown_any = True
        elif state == "parked":
            lines.append(
                f"L-{lead['id']} [parked] {lead['title']} — "
                f"tripwire: {lead['retrigger_condition'] or '(none recorded)'}"
            )
            shown_any = True
        elif state == "killed" and lead["retrigger_condition"]:
            lines.append(
                f"L-{lead['id']} [killed] {lead['title']} — "
                f"tripwire: {lead['retrigger_condition']}"
            )
            shown_any = True
    if leads and not shown_any:
        lines.append("(no live, parked, or tripped-wire leads)")

    # Surfaces & coverage (capability stack): the Architect's map as data, the
    # Blind Spot Scanner computed mechanically. The blind-spot lines are
    # brief-display ONLY — they deliberately do NOT ride into
    # find_contradictions: a blind spot is missing work, not a contradiction.
    lines += ["", "## Surfaces & coverage"]
    coverage = surface_coverage(conn, target_id)
    rows = coverage["rows"]
    if not rows:
        lines.append("(none recorded)")
    else:
        counts = {k: 0 for k in SURFACE_KINDS}
        for r in rows:
            counts[r["kind"]] = counts.get(r["kind"], 0) + 1
        covered = sum(1 for r in rows if r["has_lead"] or r["has_finding"])
        lines.append(
            "counts: " + ", ".join(f"{k}={counts[k]}" for k in SURFACE_KINDS)
            + f" | covered: {covered}/{len(rows)}"
        )
    for spot in coverage["blind_spots"]:
        lines.append(f"!! trust boundary '{spot['name']}' has no lead or finding")

    # Same display-time courtesy as export_report: rows that predate the gates
    # (or arrived via raw SQL) get conservatively redacted on the way out.
    body = redact("\n".join(lines) + "\n")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return body + f"<!-- hunt-brief target:{t['id']} generated:{stamp} -->\n"


# --- hunt next (L1.1): the one deterministic next command --------------------
# The operator shell's mouth: `hunt next` recommends exactly one copy-pasteable
# command from the ledger state. Law 6: it never hunts — it names one command,
# it does not add findings, pick lanes, or judge evidence. When the next act is
# judgment, the recommendation is a read (`hunt brief` / `hunt status`) and the
# WHY line names the human branch.

# poc_run events pin their sha256 (16-hex prefix, the promote-gate key) and,
# since the row-13 recommendation must name the executed file, the poc path
# (' path=<poc_path>', the LAST field — tails may contain anything).
_POC_RUN_SHA_RE = re.compile(r"^poc sha256:([0-9a-f]{16})")


def _poc_run_parts(detail: str) -> tuple:
    """(sha16, poc_path) recorded in a poc_run event detail.

    Returns (None, None) for an empty detail; the path is None for legacy
    events recorded before the path was pinned to the detail (the caller then
    falls back to the <file> placeholder — the db stays the final gate)."""
    if not detail:
        return None, None
    m = _POC_RUN_SHA_RE.match(detail)
    sha = m.group(1) if m else None
    path = None
    if " path=" in detail:
        path = detail.rsplit(" path=", 1)[1] or None
    return sha, path


def next_command(conn: sqlite3.Connection, target_id: int) -> tuple:
    """The deterministic next command for a target (spec L1.1, rows 1-19).

    PURE over the ledger: SELECTs only — it never writes, never executes the
    command it names, and never touches the filesystem (a deeper kernel gate,
    e.g. RoE or a changed PoC file, still fires at execution time; `next`
    reports ledger state, it does not pre-judge). Returns
    (next_command, why): one copy-pasteable command + one ledger-grounded
    sentence. Placeholders (<ev>, <path>, <file>, <type>, <body>, "<notes>",
    "<evidence>", "<name>", "<pattern>", "<reason>", "...") stay literals for
    the operator to fill — no scores, titles, or paths are invented.

    Total order, FIRST MATCH WINS. Rows 10-13 pick the LOWEST finding id among
    the findings matching the first applicable row. The hunting fork (row 9)
    never recommends `hunt wave open` (lanes are judgment) and an open wave
    makes NEXT a read (`hunt status`) with the close command in WHY. RoE is not
    a phase gate and never appears in the order.
    """
    t = get_target(conn, target_id)
    tid = t["id"]
    phase = t["phase"]

    # Row 19 — archived: the hunt is closed; next is a read that lists hunts.
    if phase == "archived":
        return (
            "hunt target list",
            f"target #{tid} is archived ({t['archive_reason'] or 'no reason recorded'}) — "
            "this hunt is closed; hunt target list shows every hunt, archived included",
        )

    # Rows 1-2 — scoring: no score, no leaving.
    if phase == "scoring":
        if t["ev_score"] <= 0:
            return (
                f"hunt score {tid} <ev>",
                f"target #{tid} is in scoring with ev_score={t['ev_score']:g} — "
                "it cannot leave scoring without a positive score",
            )
        return (
            f"hunt phase {tid} recon",
            f"target #{tid} is scored (ev={t['ev_score']:g}) — the pipeline's next phase is recon",
        )

    # Rows 3-4 — recon: the phase exit artifact.
    if phase == "recon":
        if not _has_artifact(conn, tid, "surface_map"):
            return (
                f"hunt artifact {tid} surface_map <path>",
                f"target #{tid} is in recon with no surface_map artifact — "
                "the phase cannot be left without its exit artifact",
            )
        return (
            f"hunt phase {tid} classify",
            "surface_map artifact present — the pipeline's next phase is classify",
        )

    # Rows 5-6 — classify: the phase exit artifact.
    if phase == "classify":
        if not _has_artifact(conn, tid, "attack_plan"):
            return (
                f"hunt artifact {tid} attack_plan <path>",
                f"target #{tid} is in classify with no attack_plan artifact — "
                "the phase cannot be left without its exit artifact",
            )
        return (
            f"hunt phase {tid} hunting",
            "attack_plan artifact present — the pipeline's next phase is hunting",
        )

    # Row 7 — hunting or verify: previous wave closed but not re-audited
    # (wave N+1 is locked until the re-audit is recorded).
    if phase in ("hunting", "verify"):
        last_wave = conn.execute(
            "SELECT * FROM waves WHERE target_id=? ORDER BY number DESC LIMIT 1", (tid,)
        ).fetchone()
        if last_wave is not None and last_wave["ev_verdict"] and not last_wave["reaudit_done"]:
            return (
                f'hunt wave reaudit --wave-id {last_wave["id"]} --summary "..."',
                f"wave {last_wave['number']} is closed but not re-audited — "
                f"wave {last_wave['number'] + 1} stays locked until the re-audit is recorded",
            )

    if phase == "hunting":
        # Row 9 — hunting fork: a wave is already open. Judgment, so next is a
        # READ, never a finding and never `hunt wave open`; the close command
        # goes in WHY.
        open_wave = conn.execute(
            "SELECT * FROM waves WHERE target_id=? AND ev_verdict='' ORDER BY number DESC LIMIT 1",
            (tid,),
        ).fetchone()
        if open_wave is not None:
            return (
                "hunt status",
                f"wave #{open_wave['id']} (number {open_wave['number']}) is open — record "
                "findings and leads through the CLI; close it when the wave is done: "
                f"hunt wave close --wave-id {open_wave['id']} --verdict continue|exhausted|pivot",
            )
        # Row 8 — no open wave (none, or the last is closed+reaudited): always
        # the opening read. No "briefed" session table — operators re-read, and
        # the ledger never pretends a read was a decision.
        return (
            f"hunt brief {tid}",
            f"no open wave — read the brief before wave work; when done reading: "
            f'hunt wave open {tid} "<lanes>" (or, when the hunt is complete: '
            f"hunt phase {tid} verify)",
        )

    if phase == "verify":
        # Rows 10-13 — the evidence ladder, lowest finding id per row.
        row10: list = []               # in-code without a verifier event
        row11: list = []               # in-code, verified, no adversary review
        row12: list = []               # next promotion lacks a matching poc_run
        row13: list = []               # promotion admissible with a matching poc_run -> (fid, poc_path)
        for f in conn.execute(
            "SELECT * FROM findings WHERE target_id=? AND ladder_status IN ('theoretical','in-code') "
            "ORDER BY id",
            (tid,),
        ).fetchall():
            fid = f["id"]
            if f["ladder_status"] == "in-code":
                verifier = conn.execute(
                    "SELECT 1 FROM events WHERE finding_id=? AND kind='verifier_pass' LIMIT 1",
                    (fid,),
                ).fetchone() is not None
                if not verifier:                       # row 10
                    row10.append(fid)
                    continue
                adversary = conn.execute(
                    "SELECT 1 FROM events WHERE finding_id=? AND kind='adversary_pass' LIMIT 1",
                    (fid,),
                ).fetchone() is not None
                if not adversary:                      # row 11
                    row11.append(fid)
                    continue
                # in-code -> proven-live: needs a poc_run whose sha DIFFERS from
                # the in-code step's (the old run cannot be reused as second proof).
                in_sha = (f["poc_sha256"] or "")[:16]
                runs = conn.execute(
                    "SELECT detail FROM events WHERE finding_id=? AND kind='poc_run' ORDER BY id",
                    (fid,),
                ).fetchall()
                has_differing = False
                match_path = None
                for ev in reversed(runs):              # latest differing run first
                    sha, path = _poc_run_parts(ev["detail"])
                    if sha is not None and sha != in_sha:
                        has_differing = True
                        if match_path is None:
                            match_path = path
                if has_differing:
                    row13.append((fid, match_path))    # row 13 (path may be None on legacy events)
                else:
                    row12.append(fid)                  # row 12: no differing executed PoC
            else:  # theoretical -> in-code: any executed PoC can back the promote
                runs = conn.execute(
                    "SELECT detail FROM events WHERE finding_id=? AND kind='poc_run' "
                    "ORDER BY id DESC LIMIT 1",
                    (fid,),
                ).fetchall()
                if runs:
                    row13.append((fid, _poc_run_parts(runs[0]["detail"])[1]))
                else:
                    row12.append(fid)                  # row 12: existence is not execution
        if row10:
            fid = row10[0]
            return (
                f"hunt verify {fid} <type> <body>",
                f"finding #{fid} is in-code without a verifier event — the proven-live gate "
                "needs one (fork_receipt, tx_hash, or http_transcript)",
            )
        if row11:
            fid = row11[0]
            return (
                f'hunt challenge {fid} "<notes>"',
                f"finding #{fid} is in-code and verified but un-reviewed — the adversary pass "
                "is required before it can reach proven-live",
            )
        if row12:
            fid = row12[0]
            return (
                f"hunt poc run --id {fid} --poc-path <file>",
                f"finding #{fid}'s next promotion has no matching executed PoC — "
                "existence is not execution: a PoC that never ran clean cannot back the climb",
            )
        if row13:
            fid, poc_path = row13[0]
            file_token = poc_path if poc_path else "<file>"
            return (
                f'hunt finding promote --id {fid} --evidence-ref "<evidence>" --poc-path {file_token}',
                f"finding #{fid}'s next ladder promotion is admissible with the executed PoC "
                f"({file_token}) — climb the ladder; the db remains the final gate",
            )
        # Row 14 — zero in-code findings and no row-13 candidate (rows 10-13
        # above cover every in-code finding, so none remain here): leave verify.
        return (
            f"hunt phase {tid} report",
            "no finding is waiting on the evidence ladder — leave verify "
            "(the kernel gate refuses while in-code findings remain)",
        )

    # Rows 15-16 — report.
    if phase == "report":
        if not _has_artifact(conn, tid, "disclosure_report"):
            return (
                f"hunt report {tid} --out REPORT.md",
                "the report phase has no disclosure_report artifact — write it with --out "
                "(the artifact stamp is the phase exit evidence)",
            )
        return (
            f"hunt phase {tid} retro",
            "disclosure_report recorded — the pipeline's next phase is retro",
        )

    # Rows 17-18 — retro: the archive gate is memory.
    if phase == "retro":
        lesson = conn.execute(
            "SELECT 1 FROM lessons WHERE target_id=? LIMIT 1", (tid,)
        ).fetchone()
        if lesson is None:
            return (
                f'hunt lesson add <name> "<pattern>" --target-id {tid}',
                f"target #{tid} has no lesson bound to it — archive requires one "
                "(memory compounds or it never happened)",
            )
        return (
            f'hunt target archive {tid} "<reason>"',
            f"a lesson is bound to target #{tid} — the hunt can be deliberately closed "
            "(completion)",
        )

    # Unreachable: the schema CHECK pins the phase value set, and every legal
    # phase is handled above. Fail loud rather than return a silent guess.
    raise ValueError(f"BLOCKED: unknown phase {phase!r} on target #{tid}")


# --- workspace lock (P5: the db is the project's single notebook) ---
# A `.huntos-project` file in the working directory pins the workspace to one
# database (its full db_id). Every CLI run re-checks the lock against whatever
# HUNT_DB points at; a mismatch blocks writes while a deliberate switch goes
# through a recorded rebind (bind_project logs a project_rebound event).

LOCK_FILENAME = ".huntos-project"


def db_fingerprint(conn: sqlite3.Connection) -> str:
    """Short display fingerprint (first 12 hex of db_id)."""
    return get_meta(conn, "db_id")[:12]


def project_lock_path(cwd: str) -> str:
    return os.path.join(cwd, LOCK_FILENAME)


def read_project_lock(cwd: str) -> Optional[dict]:
    """Return the parsed lock file, or None when the workspace is unbound."""
    path = project_lock_path(cwd)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.loads(f.read())


def bind_project(conn: sqlite3.Connection, cwd: str) -> str:
    """Bind the working directory to the current db (the deliberate switch).

    Writes {db_id, bound_at} to .huntos-project and records a project_rebound
    event in the db being bound to, so every switch is auditable.
    """
    db_id = get_meta(conn, "db_id")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(project_lock_path(cwd), "w", encoding="utf-8") as f:
        f.write(json.dumps({"db_id": db_id, "bound_at": stamp}) + "\n")
    log_event(conn, None, "project_rebound", f"bound to {db_id[:12]}")
    conn.commit()
    return db_id


def check_project_lock(conn: sqlite3.Connection, cwd: str) -> Optional[str]:
    """None when the workspace is unbound or matches the current db;
    otherwise a BLOCKED: message describing the mismatch."""
    try:
        lock = read_project_lock(cwd)
    except (json.JSONDecodeError, OSError):
        return (
            f"BLOCKED: {LOCK_FILENAME} in {cwd} is malformed — "
            "fix or delete it, or rebind: hunt project bind"
        )
    if lock is None:
        return None
    if not isinstance(lock, dict) or not isinstance(lock.get("db_id"), str):
        return (
            f"BLOCKED: {LOCK_FILENAME} in {cwd} is malformed — "
            "fix or delete it, or rebind: hunt project bind"
        )
    locked_id = lock["db_id"]
    current_id = get_meta(conn, "db_id")
    if locked_id == current_id:
        return None
    return (
        "BLOCKED: this project is bound to db "
        f"{locked_id[:12]} but HUNT_DB points to {current_id[:12]} — "
        "deliberate switch? rebind first: hunt project bind"
    )


# --- conductor domain (blueprint §5: session contract and persistence) ---
#
# Public kernel API for the conductor's SESSION / ATTEMPT / INCIDENT ledger.
# The law: nothing writes to these tables except through these functions —
# the orchestrator never needs raw SQL. Refusals speak the kernel's normal
# contract (ValueError 'BLOCKED: ...' -> the CLI's exit-2 handler).
#
# Status transitions are enforced HERE in Python (the graphs below); the
# CHECK constraints in the schema pin the value sets against raw writers and
# the tamper triggers block naive raw status flips. interrupted/uncertain are
# NOT research outcomes (blueprint §5): they retry (-> running), carry an
# error_class, and never count as lane/wave results.

CONDUCTOR_LANES = ("architect", "red_teamer", "fuzz_engineer", "chainer")
CONDUCTOR_EVENT_TYPES = (
    "lane_start", "tool_request", "tool_result", "assistant_output", "usage",
    "claim_gate", "completion", "error",
)
CONDUCTOR_EVENT_DETAIL_CAP = 2000
CONDUCTOR_EVENT_LIMIT_MAX = 500

# Per-attempt usage ceiling: one usage event above this is not a heartbeat,
# it is a poisoned/upstream lie — summed into the spend report it would
# corrupt every downstream number. Refuse at the source (10**9 tokens is
# far past any honest single attempt).
_CONDUCTOR_USAGE_CEILING = 10**9

# Failure vocabulary for interrupted/uncertain/cancelled attempts. Keeping
# auth/rate_limit out of 'research_blocked' is what makes blueprint §12.8
# checkable: provider failures stay distinguishable from research outcomes.
CONDUCTOR_ERROR_CLASSES = (
    "auth", "rate_limit", "crash", "protocol", "disk_full", "timeout", "cancelled",
)

# The legal session state machine (blueprint §5). completed/aborted are terminal.
CONDUCTOR_SESSION_TRANSITIONS = {
    "preflight": {"running"},
    "running": {"degraded", "paused", "completed", "recovery_required", "aborted"},
    "degraded": {"running", "paused", "recovery_required", "aborted"},
    "paused": {"running", "aborted"},
    "recovery_required": {"aborted"},
    "completed": set(),
    "aborted": set(),
}

# The legal attempt state machine (blueprint §5). interrupted/uncertain retry
# (-> running); completed/research_blocked/cancelled are terminal outcomes.
CONDUCTOR_ATTEMPT_TRANSITIONS = {
    "ready": {"running", "cancelled"},
    "running": {"completed", "research_blocked", "interrupted", "uncertain", "cancelled"},
    "completed": set(),
    "research_blocked": set(),
    "interrupted": {"running"},
    "uncertain": {"running"},
    "cancelled": set(),
}

# Terminal/failure attempt vocabulary is the protocol layer's law (state.py):
# TERMINAL_ATTEMPT_STATUSES / FAILURE_ATTEMPT_STATUSES via is_terminal_attempt
# / is_failure_attempt — imported inside set_conductor_attempt_status (see
# there for why the import is lazy).


def _conductor_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mint_conductor_id(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    """Mint the next 'X-<n>' id for a conductor table.

    The counter is GLOBAL (one sequence per table, shared by every session and
    every retry) and monotone: MAX(numeric suffix) + 1. A retry never recycles
    its parent's id — the whole point of parent_attempt_id is that A-numbers
    only ever grow, so an id always names exactly one attempt. SUBSTR is
    1-based and skips the '<prefix>-' head (2 chars + the dash), so 'A-9' -> 9
    and numeric ordering survives double digits ('A-10' > 'A-9').
    """
    n = conn.execute(
        f"SELECT COALESCE(MAX(CAST(SUBSTR(id, {len(prefix) + 2}) AS INTEGER)), 0) + 1 FROM {table}"
    ).fetchone()[0]
    return f"{prefix}-{n}"


def _conductor_row_or_block(conn: sqlite3.Connection, table: str, label: str, row_id: str):
    row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
    if row is None:
        raise ValueError(f"BLOCKED: conductor {label} '{row_id}' does not exist")
    return row


def _session_target_id(conn: sqlite3.Connection, session_id: str) -> Optional[int]:
    row = conn.execute(
        "SELECT target_id FROM conductor_session WHERE id=?", (session_id,)
    ).fetchone()
    return row["target_id"] if row is not None else None


def create_conductor_session(conn: sqlite3.Connection, target_id: int, workspace: str,
                             db_fingerprint: str, budget: Optional[int],
                             adapter_id: Optional[str], adapter_version: Optional[str],
                             model_profile_hash: Optional[str],
                             skills_lock_hash: Optional[str],
                             rounds: Optional[int] = None,
                             adapter_registry_name: Optional[str] = None) -> dict:
    """Open a conductor session (status 'preflight'). Returns the session row
    as a plain dict.

    Gates: the target must exist and not be archived (the archived lock — a
    closed hunt takes no new sessions), and the caller must name the ledger it
    is running against: db_fingerprint must match the OPEN db (blueprint §12.2,
    kernel-side half — a session recorded against a fingerprint other than the
    db it actually ran on would be a lie in the ledger). budget=None records
    'no budget declared'. rounds is the declared round count of the managed
    loop (None = not declared; resume needs it to know the work surface).
    """
    target = _require_active_target(conn, target_id)
    if not db_fingerprint or not str(db_fingerprint).strip():
        raise ValueError(
            "BLOCKED: session db_fingerprint is required — pass db.db_fingerprint(conn) "
            "(a session must name the ledger it runs against)"
        )
    current_fp = (get_meta(conn, "db_id") or "")[:12]
    if str(db_fingerprint).strip() != current_fp:
        raise ValueError(
            f"BLOCKED: session db_fingerprint '{db_fingerprint}' does not match the open "
            f"ledger ({current_fp}) — a session cannot run against the wrong db"
        )
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, int) or budget < 0):
        raise ValueError(f"BLOCKED: budget must be a non-negative integer or None; got {budget!r}")
    if rounds is not None and (isinstance(rounds, bool) or not isinstance(rounds, int) or rounds < 1):
        raise ValueError(f"BLOCKED: rounds must be a positive integer or None; got {rounds!r}")
    session_id = _mint_conductor_id(conn, "conductor_session", "S")
    conn.execute(
        "INSERT INTO conductor_session (id, target_id, workspace, db_fingerprint, status, "
        "budget, adapter_id, adapter_version, adapter_registry_name, model_profile_hash, "
        "skills_lock_hash, rounds, created_at) "
        "VALUES (?, ?, ?, ?, 'preflight', ?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, int(target_id), redact(workspace or ""), str(db_fingerprint).strip(),
         budget, adapter_id, adapter_version, adapter_registry_name, model_profile_hash,
         skills_lock_hash, rounds, _conductor_stamp()),
    )
    log_event(conn, target["id"], "conductor_session_created",
              f"{session_id} target=#{target_id} workspace={workspace} fingerprint={db_fingerprint}")
    conn.commit()
    return get_conductor_session(conn, session_id)


def set_conductor_session_status(conn: sqlite3.Connection, session_id: str,
                                 new_status: str) -> dict:
    """Move a session along the legal state machine (blueprint §5) and return
    the updated row. Same-value calls are no-ops. started_at is stamped on the
    FIRST 'running' entry only (it survives degraded/paused detours); ended_at
    is stamped on completed/aborted (the two terminal states)."""
    session = _conductor_row_or_block(conn, "conductor_session", "session", session_id)
    old = session["status"]
    if new_status not in CONDUCTOR_SESSION_TRANSITIONS:
        raise ValueError(
            f"BLOCKED: session status must be one of {sorted(CONDUCTOR_SESSION_TRANSITIONS)}; "
            f"got '{new_status}'"
        )
    if new_status == old:
        return dict(session)  # same-value no-op
    legal = CONDUCTOR_SESSION_TRANSITIONS[old]
    if new_status not in legal:
        raise ValueError(
            f"BLOCKED: illegal session transition {old} -> {new_status} "
            f"(legal from '{old}': {sorted(legal) if legal else 'none — terminal'})"
        )
    updates, args = ["status=?"], [new_status]
    if new_status == "running" and session["started_at"] is None:
        updates.append("started_at=?")
        args.append(_conductor_stamp())
    if new_status in ("completed", "aborted"):
        updates.append("ended_at=?")
        args.append(_conductor_stamp())
    args.append(session_id)
    conn.execute(f"UPDATE conductor_session SET {', '.join(updates)} WHERE id=?", tuple(args))
    log_event(conn, session["target_id"], "conductor_session_status",
              f"{session_id} {old} -> {new_status}")
    conn.commit()
    return get_conductor_session(conn, session_id)


def create_conductor_attempt(conn: sqlite3.Connection, session_id: str, lane: str,
                             round: int, parent_attempt_id: Optional[str] = None,
                             model_profile: Optional[str] = None,
                             prompt_hash: Optional[str] = None) -> dict:
    """Birth one lane attempt (status 'ready') and return its row as a dict.

    Gates: the session must be running or degraded (no attempts in preflight,
    paused, completed, ...), the lane is one of the four roles, round is an
    integer >= 1, and a parent_attempt_id (a retry) must exist AND belong to
    the same session — retries never jump sessions. The id is fresh even for
    retries: A-numbers only grow.
    """
    session = _conductor_row_or_block(conn, "conductor_session", "session", session_id)
    if session["status"] not in ("running", "degraded"):
        raise ValueError(
            f"BLOCKED: session {session_id} is '{session['status']}' — attempts are born "
            "only into a running or degraded session"
        )
    if lane not in CONDUCTOR_LANES:
        raise ValueError(f"BLOCKED: lane must be one of {list(CONDUCTOR_LANES)}; got '{lane}'")
    if isinstance(round, bool) or not isinstance(round, int) or round < 1:
        raise ValueError(f"BLOCKED: round must be an integer >= 1; got {round!r}")
    if parent_attempt_id is not None:
        parent = conn.execute(
            "SELECT session_id FROM conductor_attempt WHERE id=?", (parent_attempt_id,)
        ).fetchone()
        if parent is None:
            raise ValueError(f"BLOCKED: parent attempt '{parent_attempt_id}' does not exist")
        if parent["session_id"] != session_id:
            raise ValueError(
                f"BLOCKED: parent attempt '{parent_attempt_id}' belongs to session "
                f"{parent['session_id']} — a retry stays inside its own session"
            )
    attempt_id = _mint_conductor_id(conn, "conductor_attempt", "A")
    conn.execute(
        "INSERT INTO conductor_attempt (id, session_id, lane, round, parent_attempt_id, "
        "model_profile, prompt_hash, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', ?)",
        (attempt_id, session_id, lane, round, parent_attempt_id, model_profile, prompt_hash,
         _conductor_stamp()),
    )
    detail = f"{attempt_id} {session_id} lane={lane} round={round}"
    if parent_attempt_id:
        detail += f" retry of {parent_attempt_id}"
    log_event(conn, session["target_id"], "conductor_attempt_created", detail)
    conn.commit()
    return get_conductor_attempt(conn, attempt_id)


def set_conductor_attempt_prompt_hash(conn: sqlite3.Connection, attempt_id: str,
                                      prompt_hash: str) -> dict:
    """Pin the canonical capsule hash before an attempt is dispatched."""
    attempt = _conductor_row_or_block(conn, "conductor_attempt", "attempt", attempt_id)
    if attempt["status"] != "ready":
        raise ValueError("BLOCKED: capsule hash can only be pinned on a ready attempt")
    if not isinstance(prompt_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", prompt_hash):
        raise ValueError("BLOCKED: capsule hash must be a lowercase SHA-256 hex digest")
    conn.execute("UPDATE conductor_attempt SET prompt_hash=? WHERE id=?", (prompt_hash, attempt_id))
    conn.commit()
    return get_conductor_attempt(conn, attempt_id)


def set_conductor_attempt_status(conn: sqlite3.Connection, attempt_id: str,
                                 new_status: str, error_class: Optional[str] = None) -> dict:
    """Move an attempt along the legal state machine (blueprint §5) and return
    the updated row. Same-value calls are no-ops.

    error_class rules: the vocabulary is CONDUCTOR_ERROR_CLASSES, and an error
    class is only recordable on the failure outcomes (interrupted/uncertain/
    cancelled) — attaching one to a clean path (e.g. running->completed) is
    refused, so a completed attempt can never masquerade as a failed one.
    started_at is stamped on the FIRST 'running' entry (it survives retries);
    ended_at is stamped on terminal outcomes only — interrupted/uncertain are
    not results, so they leave it NULL.
    """
    # Terminal/failure vocabulary is the protocol layer's law (state.py) —
    # one definition, not an inline re-derivation. The import is lazy on
    # purpose: db is the kernel and must not pull the conductor package
    # (adapter/schemas/summary/orchestrator) at import time — that package's
    # __init__ imports this module back.
    from huntos.conductor.state import (
        FAILURE_ATTEMPT_STATUSES,
        is_failure_attempt,
        is_terminal_attempt,
    )
    attempt = _conductor_row_or_block(conn, "conductor_attempt", "attempt", attempt_id)
    old = attempt["status"]
    if new_status not in CONDUCTOR_ATTEMPT_TRANSITIONS:
        raise ValueError(
            f"BLOCKED: attempt status must be one of {sorted(CONDUCTOR_ATTEMPT_TRANSITIONS)}; "
            f"got '{new_status}'"
        )
    if error_class is not None:
        if error_class not in CONDUCTOR_ERROR_CLASSES:
            raise ValueError(
                f"BLOCKED: error_class must be one of {list(CONDUCTOR_ERROR_CLASSES)}; "
                f"got '{error_class}'"
            )
        if not is_failure_attempt(new_status):
            raise ValueError(
                f"BLOCKED: error_class is only recorded on "
                f"{list(FAILURE_ATTEMPT_STATUSES)} outcomes, not on '{new_status}' — "
                "a clean outcome cannot carry an error class"
            )
    if new_status == old:
        return dict(attempt)  # same-value no-op
    legal = CONDUCTOR_ATTEMPT_TRANSITIONS[old]
    if new_status not in legal:
        raise ValueError(
            f"BLOCKED: illegal attempt transition {old} -> {new_status} "
            f"(legal from '{old}': {sorted(legal) if legal else 'none — terminal'})"
        )
    updates, args = ["status=?"], [new_status]
    if error_class is not None:
        updates.append("error_class=?")
        args.append(error_class)
    if new_status == "running" and attempt["started_at"] is None:
        updates.append("started_at=?")
        args.append(_conductor_stamp())
    # Terminal outcomes stamp ended_at (state.py law: interrupted/uncertain
    # are pauses with an error_class, not results — they never stamp it).
    if is_terminal_attempt(new_status):
        updates.append("ended_at=?")
        args.append(_conductor_stamp())
    args.append(attempt_id)
    conn.execute(f"UPDATE conductor_attempt SET {', '.join(updates)} WHERE id=?", tuple(args))
    detail = f"{attempt_id} {old} -> {new_status}"
    if error_class is not None:
        detail += f" error_class={error_class}"
    log_event(conn, _session_target_id(conn, attempt["session_id"]),
              "conductor_attempt_status", detail)
    conn.commit()
    return get_conductor_attempt(conn, attempt_id)


def record_attempt_usage(conn: sqlite3.Connection, attempt_id: str, tokens: int) -> dict:
    """Add tokens to an attempt's cumulative usage counter and return the
    updated row. Additive by design — a usage event stream lands as a sum, so
    heartbeats cannot overwrite each other."""
    attempt = _conductor_row_or_block(conn, "conductor_attempt", "attempt", attempt_id)
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        raise ValueError(f"BLOCKED: usage tokens must be a non-negative integer; got {tokens!r}")
    if tokens > _CONDUCTOR_USAGE_CEILING:
        raise ValueError(
            f"BLOCKED: usage tokens exceed the per-attempt ceiling "
            f"({_CONDUCTOR_USAGE_CEILING}); got {tokens!r}"
        )
    conn.execute(
        "UPDATE conductor_attempt SET usage = COALESCE(usage, 0) + ? WHERE id=?",
        (tokens, attempt_id),
    )
    log_event(conn, _session_target_id(conn, attempt["session_id"]),
              "conductor_attempt_usage", f"{attempt_id} +{tokens} tokens")
    conn.commit()
    return get_conductor_attempt(conn, attempt_id)


def _cap_conductor_detail(detail: str) -> str:
    clean = redact(detail)
    if len(clean) <= CONDUCTOR_EVENT_DETAIL_CAP:
        return clean
    marker = "... [truncated]"
    return clean[:CONDUCTOR_EVENT_DETAIL_CAP - len(marker)] + marker


def record_conductor_event(conn: sqlite3.Connection, session_id: str,
                           attempt_id: str, event_type: str, detail: str,
                           operation_id: Optional[str] = None):
    """Append one typed, redacted operational event for an attempt."""
    if event_type not in CONDUCTOR_EVENT_TYPES:
        raise ValueError(
            f"BLOCKED: conductor event type must be one of {list(CONDUCTOR_EVENT_TYPES)}"
        )
    attempt = _conductor_row_or_block(
        conn, "conductor_attempt", "attempt", attempt_id
    )
    if attempt["session_id"] != session_id:
        raise ValueError(
            f"BLOCKED: attempt {attempt_id} belongs to session "
            f"{attempt['session_id']}, not {session_id}"
        )
    if not isinstance(detail, str):
        raise ValueError("BLOCKED: conductor event detail must be a string")
    if operation_id is not None and not isinstance(operation_id, str):
        raise ValueError("BLOCKED: conductor event operation_id must be a string or None")
    clean = _cap_conductor_detail(detail)
    sequence = int(conn.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM conductor_event WHERE attempt_id=?",
        (attempt_id,),
    ).fetchone()[0])
    try:
        cur = conn.execute(
            "INSERT INTO conductor_event "
            "(session_id, attempt_id, lane, sequence, event_type, detail, operation_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, attempt_id, attempt["lane"], sequence, event_type, clean,
             operation_id, _conductor_stamp()),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"BLOCKED: conductor event append failed: {exc}") from exc
    conn.commit()
    return conn.execute("SELECT * FROM conductor_event WHERE id=?", (cur.lastrowid,)).fetchone()


def list_conductor_events(conn: sqlite3.Connection, session_id: str,
                          attempt_id: Optional[str] = None,
                          limit: int = 100) -> list:
    """Return the last ``limit`` events in chronological order."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= CONDUCTOR_EVENT_LIMIT_MAX:
        raise ValueError(
            f"BLOCKED: conductor event limit must be an integer from 1 to "
            f"{CONDUCTOR_EVENT_LIMIT_MAX}"
        )
    _conductor_row_or_block(conn, "conductor_session", "session", session_id)
    args: list = [session_id]
    where = "session_id=?"
    if attempt_id is not None:
        attempt = _conductor_row_or_block(conn, "conductor_attempt", "attempt", attempt_id)
        if attempt["session_id"] != session_id:
            raise ValueError(
                f"BLOCKED: attempt {attempt_id} belongs to session "
                f"{attempt['session_id']}, not {session_id}"
            )
        where += " AND attempt_id=?"
        args.append(attempt_id)
    args.append(limit)
    return conn.execute(
        f"SELECT * FROM (SELECT * FROM conductor_event WHERE {where} "
        "ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
        tuple(args),
    ).fetchall()


def record_conductor_incident(conn: sqlite3.Connection, session_id: str, klass: str,
                              detail: Optional[str]) -> dict:
    """Record an incident against a session (mint 'I-<n>') and return its row.
    `klass` (not `class` — reserved word in Python; the COLUMN is named class)
    is the incident taxonomy; detail is free text gated by the secret gates."""
    session = _conductor_row_or_block(conn, "conductor_session", "session", session_id)
    if not klass or not str(klass).strip():
        raise ValueError("BLOCKED: incident class must be a non-empty string")
    if detail:
        assert_no_secrets(str(detail), "incident detail")
    incident_id = _mint_conductor_id(conn, "conductor_incident", "I")
    conn.execute(
        "INSERT INTO conductor_incident (id, session_id, class, detail, resolution, created_at) "
        "VALUES (?, ?, ?, ?, NULL, ?)",
        (incident_id, session_id, str(klass).strip(), redact(detail), _conductor_stamp()),
    )
    log_event(conn, session["target_id"], "conductor_incident_recorded",
              f"{incident_id} {session_id} class={str(klass).strip()}")
    conn.commit()
    return get_conductor_incident(conn, incident_id)


def resolve_conductor_incident(conn: sqlite3.Connection, incident_id: str, resolution: str) -> dict:
    """Close an incident: store the resolution and stamp resolved_at. An
    incident resolves ONCE — the audit trail is append-only, so re-resolving
    is refused."""
    incident = _conductor_row_or_block(conn, "conductor_incident", "incident", incident_id)
    if incident["resolved_at"] is not None:
        raise ValueError(
            f"BLOCKED: incident '{incident_id}' is already resolved "
            f"({incident['resolved_at']}) — resolutions are append-only"
        )
    if not resolution or not str(resolution).strip():
        raise ValueError(
            "BLOCKED: incident resolution must be a non-empty string — say how it was resolved"
        )
    assert_no_secrets(str(resolution), "incident resolution")
    stamp = _conductor_stamp()
    conn.execute(
        "UPDATE conductor_incident SET resolution=?, resolved_at=? WHERE id=?",
        (redact(str(resolution).strip()), stamp, incident_id),
    )
    log_event(conn, _session_target_id(conn, incident["session_id"]),
              "conductor_incident_resolved", f"{incident_id} resolved")
    conn.commit()
    return get_conductor_incident(conn, incident_id)


def get_conductor_session(conn: sqlite3.Connection, session_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM conductor_session WHERE id=?", (session_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def latest_conductor_session(conn: sqlite3.Connection,
                             target_id: Optional[int] = None) -> Optional[dict]:
    """The most recently minted session — globally, or for one target. Ordered
    by the NUMERIC id suffix (lexicographic order would put S-9 after S-10)."""
    sql = "SELECT * FROM conductor_session"
    args: tuple = ()
    if target_id is not None:
        sql += " WHERE target_id=?"
        args = (target_id,)
    sql += " ORDER BY CAST(SUBSTR(id, 3) AS INTEGER) DESC LIMIT 1"
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row is not None else None


def list_conductor_attempts(conn: sqlite3.Connection, session_id: str) -> list:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM conductor_attempt WHERE session_id=? "
            "ORDER BY CAST(SUBSTR(id, 3) AS INTEGER)",
            (session_id,),
        ).fetchall()
    ]


def list_conductor_incidents(conn: sqlite3.Connection, session_id: str) -> list:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM conductor_incident WHERE session_id=? "
            "ORDER BY CAST(SUBSTR(id, 3) AS INTEGER)",
            (session_id,),
        ).fetchall()
    ]


def get_conductor_attempt(conn: sqlite3.Connection, attempt_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM conductor_attempt WHERE id=?", (attempt_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def get_conductor_incident(conn: sqlite3.Connection, incident_id: str) -> Optional[dict]:
    """Read one incident (None when missing). Companion getter for the
    incident mutators' rows — the orchestrator-facing list lives in
    list_conductor_incidents."""
    row = conn.execute(
        "SELECT * FROM conductor_incident WHERE id=?", (incident_id,)
    ).fetchone()
    return dict(row) if row is not None else None


def _get_conductor_incident(conn: sqlite3.Connection, incident_id: str) -> dict:
    return _conductor_row_or_block(conn, "conductor_incident", "incident", incident_id)
