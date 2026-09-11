"""HUNT-OS core dataclasses - shared structures (engine-agnostic, tenant-agnostic)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- Evidence ladder (Doctrine #2) ---
LADDER = ["theoretical", "in-code", "proven-live", "overturned"]
LADDER_RANK = {"theoretical": 0, "in-code": 1, "proven-live": 2}

# Artifact types accepted as verifier evidence (Doctrine #2: no PoC = no proof)
ARTIFACT_TYPES = ["fork_receipt", "tx_hash", "http_transcript"]

# Rules-of-engagement action scale (escalation order)
ROE_ACTIONS = ["recon", "read", "auth-test", "mutate"]

# FRAMEWORK.md L2 artifact contract: what each phase must produce to be left
PHASE_ARTIFACTS = {
    "recon": "surface_map",
    "classify": "attack_plan",
    "report": "disclosure_report",
}

# Taxonomy (klass): OWASP SC Top 10:2025 + DASP + SWC, ordered by priority.
# 'Unknown' is the quarantine class: always valid, reviewed at retro.
# New classes grow via retro (hunt klass add) — see taxonomies table in db.py.
KLASS = ["Access", "Oracle", "Reentrancy", "Sig", "Arithmetic",
         "ExternalCall", "Logic", "Upgradeable", "Web2", "Unknown"]

# Severity order (business priority: Access > Oracle > Reentrancy > Sig > Logic > UUPS)
SEVERITY = ["critical", "high", "medium", "low", "info"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY)}

# Pipeline phases (L2) - order is enforced
PHASES = ["scoring", "recon", "classify", "hunting", "verify", "report", "retro", "archived"]
PHASE_RANK = {p: i for i, p in enumerate(PHASES)}


@dataclass
class Target:
    name: str
    url: str
    chain: str = "evm"
    age_days: int = 0
    tvl_usd: float = 0.0
    phase: str = "scoring"
    ev_score: float = 0.0
    archive_reason: str = ""
    notes: str = ""


@dataclass
class Finding:
    title: str
    target_id: int
    klass: str
    severity: str = "info"
    ladder_status: str = "theoretical"
    evidence_ref: str = ""
    poc_path: str = ""
    overturned_by: str = ""
    notes: str = ""


@dataclass
class Wave:
    target_id: int
    number: int
    lanes: str = ""          # comma-separated lane families
    findings_new: int = 0
    reaudit_done: int = 0    # 0/1: was previous wave re-audited first
    ev_verdict: str = ""     # continue / exhausted / pivot
    notes: str = ""


@dataclass
class Lesson:
    source_target: str
    pattern: str             # the reusable pattern
    scope: str = "skill"     # skill / state_rule / soul / law_candidate
    notes: str = ""
