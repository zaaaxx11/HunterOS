"""Fail-closed target intake and isolated public GitHub preparation."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit, urlunsplit


_MAX_SOURCE_LENGTH = 4096
_GITHUB_PART = r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,98}[A-Za-z0-9])?"
_GITHUB_RE = re.compile(rf"^(?P<owner>{_GITHUB_PART})/(?P<repo>{_GITHUB_PART})(?:\.git)?$")
_SECRET_VALUE_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:password|passwd)\s*[=:]\s*\S+|"
    r"\b(?:token|secret|api[_-]?key)\s*[=:]\s*\S{12,}"
)
_SECRET_QUERY_KEYS = frozenset(
    {
        "access_token", "api_key", "apikey", "auth", "authorization",
        "client_secret", "key", "password", "passwd", "secret", "sig",
        "signature", "token",
    }
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_UNC_RE = re.compile(r"^(?:\\\\|//)[^\\/]+[\\/][^\\/]+")


@dataclass(frozen=True)
class TargetSource:
    kind: str
    canonical: str
    display: str
    workspace: str = ""
    revision: str = ""


def _blocked(message: str) -> ValueError:
    return ValueError(f"BLOCKED: {message}")


def _validate_raw(raw: str) -> str:
    if not isinstance(raw, str):
        raise _blocked("target source must be text")
    if not raw.strip():
        raise _blocked("target source must not be empty")
    if len(raw) > _MAX_SOURCE_LENGTH:
        raise _blocked(f"target source exceeds {_MAX_SOURCE_LENGTH} characters")
    if any(unicodedata.category(ch) == "Cc" for ch in raw):
        raise _blocked("target source contains a control character")
    value = raw.strip()
    if _SECRET_VALUE_RE.search(value) or _SECRET_ASSIGNMENT_RE.search(value):
        raise _blocked("target source contains what looks like a raw secret")
    return value


def _existing_directory(value: str, cwd: Path | None) -> Path | None:
    """Resolve an existing local directory without changing process cwd."""
    expanded = os.path.expanduser(value)
    # Windows/UNC spellings must not accidentally become odd relative POSIX
    # paths when intake is exercised on another operating system.
    if os.name != "nt" and (_WINDOWS_DRIVE_RE.match(expanded) or _UNC_RE.match(expanded)):
        return None
    candidate = Path(expanded)
    if not candidate.is_absolute():
        candidate = (Path.cwd() if cwd is None else Path(cwd)) / candidate
    try:
        if candidate.is_dir():
            return candidate.resolve()
    except (OSError, RuntimeError):
        return None
    return None


def _github_parts(value: str) -> tuple[str, str] | None:
    candidate = value
    if candidate.startswith("git@github.com:"):
        candidate = candidate[len("git@github.com:"):]
    elif candidate.startswith("github:"):
        candidate = candidate[len("github:"):]
    elif candidate.startswith("github.com/"):
        candidate = candidate[len("github.com/"):]
    else:
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            return None
        if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != "github.com":
            return None
        if parsed.username is not None or parsed.password is not None or parsed.port not in (None, 443):
            raise _blocked("GitHub source must not contain credentials or a non-default port")
        if parsed.query or parsed.fragment:
            raise _blocked("GitHub source must not contain a query or fragment")
        candidate = parsed.path.lstrip("/")
    match = _GITHUB_RE.fullmatch(candidate)
    if match is None:
        # A GitHub-looking input is never allowed to fall through as a generic
        # URL, where extra path components would change its meaning.
        if "github.com" in value.lower() or value.lower().startswith("github:"):
            raise _blocked("GitHub source must be exactly owner/repository")
        return None
    return match.group("owner"), match.group("repo").removesuffix(".git")


def _format_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _generic_url(value: str) -> TargetSource | None:
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise _blocked(f"invalid URL: {exc}") from None
    if not parsed.scheme:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise _blocked(f"unsupported target source scheme {parsed.scheme!r}")
    if parsed.username is not None or parsed.password is not None:
        raise _blocked("URL credentials are not allowed")
    host = parsed.hostname
    if not host:
        raise _blocked("URL requires a host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise _blocked(f"invalid URL port: {exc}") from None
    try:
        normalized_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise _blocked("URL host is invalid") from None
    if any(not label or len(label) > 63 for label in normalized_host.split(".") if ":" not in normalized_host):
        raise _blocked("URL host is invalid")
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SECRET_QUERY_KEYS:
            raise _blocked(f"URL query key {key!r} may carry credentials")
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = _format_host(normalized_host)
    if port is not None and not default_port:
        netloc += f":{port}"
    path = parsed.path or "/"
    canonical = urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))
    return TargetSource("url", canonical, canonical)


def _looks_path_like(value: str) -> bool:
    return bool(
        value.startswith((".", "~", "/", "\\"))
        or _WINDOWS_DRIVE_RE.match(value)
        or _UNC_RE.match(value)
        or "\\" in value
        or ("/" in value and not value.startswith(("http://", "https://")))
    )


def classify_target_source(raw: str, *, cwd: Path | None = None) -> TargetSource:
    """Classify a folder, exact public GitHub repository, or HTTP(S) URL."""
    value = _validate_raw(raw)
    folder = _existing_directory(value, cwd)
    if folder is not None:
        resolved = str(folder)
        return TargetSource("folder", resolved, resolved, workspace=resolved)

    github = _github_parts(value)
    if github is not None:
        owner, repo = github
        canonical = f"https://github.com/{owner}/{repo}"
        return TargetSource("github", canonical, canonical)

    url = _generic_url(value)
    if url is not None:
        return url
    if _looks_path_like(value):
        raise _blocked("local folder does not exist or is not a directory")
    raise _blocked("target source must be an existing folder, GitHub repository, or HTTP(S) URL")


def default_target_name(source: TargetSource) -> str:
    """Return a short, safe target name derived from canonical source data."""
    if source.kind == "folder":
        base = Path(source.canonical).name
    elif source.kind == "github":
        base = source.canonical.rstrip("/").rsplit("/", 1)[-1]
    elif source.kind == "url":
        parsed = urlsplit(source.canonical)
        base = (parsed.hostname or "target").split(".")[0]
    else:
        base = "target"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-._").lower()
    return (slug or "target")[:64]


def _run_git(runner, argv: list[str], env: dict[str, str], timeout: int):
    try:
        result = runner(
            argv,
            shell=False,
            env=env,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise _blocked(f"git preparation failed: {exc}") from None
    if getattr(result, "returncode", 1) != 0:
        stderr = str(getattr(result, "stderr", "") or "").strip().replace("\x00", "")
        if len(stderr) > 1000:
            stderr = stderr[-1000:]
        suffix = f": {stderr}" if stderr else ""
        raise _blocked(f"git command failed (exit {result.returncode}){suffix}")
    return str(getattr(result, "stdout", "") or "").strip()


def prepare_github_source(
    source: TargetSource,
    workspace_root: Path,
    *,
    runner=subprocess.run,
    timeout=120,
) -> TargetSource:
    """Prepare a shallow isolated checkout without deleting existing data."""
    if source.kind != "github":
        raise _blocked("GitHub preparation requires a github target source")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise _blocked("GitHub preparation timeout must be positive")
    # Re-classification pins callers to the exact canonical shape.
    checked = classify_target_source(source.canonical)
    if checked.kind != "github" or checked.canonical != source.canonical:
        raise _blocked("GitHub source canonical value is invalid")

    root = Path(workspace_root).expanduser().resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _blocked(f"cannot create workspace root {root}: {exc}") from None
    if not root.is_dir():
        raise _blocked(f"workspace root is not a directory: {root}")

    slug = default_target_name(source)
    digest = hashlib.sha256(source.canonical.encode("utf-8")).hexdigest()[:12]
    destination = root / f"{slug}-{digest}"
    hooks = root / ".disabled-git-hooks"
    try:
        hooks.mkdir(exist_ok=True)
    except OSError as exc:
        raise _blocked(f"cannot isolate Git hooks: {exc}") from None

    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_LFS_SKIP_SMUDGE": "1",
        }
    )
    common = ["git", "-c", f"core.hooksPath={hooks}"]

    if destination.exists():
        if not destination.is_dir():
            raise _blocked(f"GitHub workspace already exists and is not a directory: {destination}")
        origin = _run_git(
            runner,
            [*common, "-C", str(destination), "remote", "get-url", "origin"],
            env,
            timeout,
        )
        try:
            origin_source = classify_target_source(origin)
        except ValueError:
            raise _blocked("existing GitHub workspace has an invalid origin") from None
        if origin_source.kind != "github" or origin_source.canonical != source.canonical:
            raise _blocked("existing GitHub workspace origin does not match the requested source")
    else:
        _run_git(
            runner,
            [*common, "clone", "--depth", "1", "--no-tags", "--no-recurse-submodules",
             "--no-checkout", source.canonical, str(destination)],
            env,
            timeout,
        )
        _run_git(
            runner,
            [*common, "-C", str(destination), "checkout", "--detach", "HEAD", "--"],
            env,
            timeout,
        )

    revision_output = _run_git(
        runner,
        [*common, "-C", str(destination), "rev-parse", "--verify", "HEAD"],
        env,
        timeout,
    )
    revision = revision_output.splitlines()[0] if revision_output else ""
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
        raise _blocked("GitHub workspace HEAD did not resolve to a commit")
    if source.revision and source.revision.lower() != revision.lower():
        raise _blocked("existing GitHub workspace HEAD does not match the recorded revision")
    return replace(source, workspace=str(destination.resolve()), revision=revision.lower())
