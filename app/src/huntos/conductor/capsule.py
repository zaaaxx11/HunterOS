"""Canonical, bounded lane capsules for managed conductor attempts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from huntos.core import db

BRIEF_CAP = 12_000
ROLE_FILES = {
    "architect": "architect.md",
    "red_teamer": "red-teamer.md",
    "fuzz_engineer": "fuzz-engineer.md",
    "chainer": "chainer.md",
}


def default_roles_root() -> Path:
    """Resolve the lane-role doctrine shipped inside the package
    (``huntos/_data/roles``) — no checkout and no cwd involved."""
    root = Path(__file__).resolve().parents[1] / "_data" / "roles"
    if not root.is_dir():
        raise ValueError("BLOCKED: HUNT-OS roles not found at _data/roles")
    return root


def skills_lock_hash(roles_root: Path | None = None) -> str:
    root = Path(roles_root) if roles_root is not None else default_roles_root()
    digest = hashlib.sha256()
    for lane in db.CONDUCTOR_LANES:
        path = root / ROLE_FILES[lane]
        try:
            content = path.read_bytes()
        except OSError as exc:
            raise ValueError(f"BLOCKED: role file unavailable for {lane}: {exc}") from exc
        digest.update(lane.encode("utf-8") + b"\0" + content + b"\0")
    return digest.hexdigest()


def build_lane_capsule(conn, session_id, attempt_id, lane, round_no,
                       model_profile, roles_root) -> tuple[dict, str]:
    """Build canonical lane input from the already-open ledger connection."""
    if lane not in db.CONDUCTOR_LANES:
        raise ValueError(f"BLOCKED: unknown conductor lane {lane!r}")
    session = db.get_conductor_session(conn, session_id)
    if session is None:
        raise ValueError(f"BLOCKED: conductor session '{session_id}' does not exist")
    attempt = db.get_conductor_attempt(conn, attempt_id)
    if attempt is None or attempt["session_id"] != session_id:
        raise ValueError(f"BLOCKED: attempt {attempt_id} does not belong to session {session_id}")
    if attempt["lane"] != lane or attempt["round"] != round_no:
        raise ValueError("BLOCKED: capsule identity does not match the recorded attempt")
    target_id = session["target_id"]
    if target_id is None:
        raise ValueError("BLOCKED: capsule session has no target")
    try:
        target = db.get_target(conn, int(target_id))
    except ValueError as exc:
        raise ValueError("BLOCKED: capsule target is missing") from exc
    source = db.get_target_source(conn, int(target_id))
    if source is None:
        raise ValueError("BLOCKED: capsule target source is missing")
    roe = db.get_roe(conn, int(target_id))
    if roe is None:
        raise ValueError("BLOCKED: capsule rules of engagement are missing")
    role_path = Path(roles_root) / ROLE_FILES[lane]
    try:
        role_text = role_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"BLOCKED: role text unavailable for {lane}: {exc}") from exc
    if not role_text.strip():
        raise ValueError(f"BLOCKED: role text for {lane} is empty")
    brief = db.export_brief(conn, int(target_id))
    if len(brief) > BRIEF_CAP:
        marker = "\n... [brief truncated]\n"
        brief = brief[:BRIEF_CAP - len(marker)] + marker
    capsule = {
        "protocol": "HUNT-ADAPTER/1",
        "identifiers": {
            "session_id": session_id,
            "attempt_id": attempt_id,
            "target_id": int(target_id),
            "lane": lane,
            "round": round_no,
        },
        "target": {
            "name": target["name"],
            "canonical": target["url"],
            "chain": target["chain"],
            "phase": target["phase"],
        },
        "source": {
            "kind": source["kind"],
            "canonical": source["canonical"],
            "display": source["display"],
            "workspace": source["workspace"],
            "revision": source["revision"],
        },
        "workspace": source["workspace"],
        "rules_of_engagement": {
            "hosts": roe["hosts"],
            "actions": roe["actions"],
            "authorization_note": source["authorization_note"],
        },
        "role": {"lane": lane, "text": role_text},
        "brief": brief,
        "contract": {
            "tool": "Request local CLI actions only with ToolRequest; await each ToolResult.",
            "output": "Return operational output only; never expose chain-of-thought or raw secrets.",
            "serial": True,
        },
        "model_profile": model_profile,
    }
    canonical = json.dumps(capsule, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return capsule, hashlib.sha256(canonical.encode("utf-8")).hexdigest()
