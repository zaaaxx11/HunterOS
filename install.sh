#!/usr/bin/env bash
# HUNT-OS release installer (POSIX shells: bash, dash, zsh, Git-Bash).
# IF PROMPT SHOWS C:\...> WITHOUT PS PREFIX: you are in cmd.exe - stop.
# Type powershell.exe for install.ps1 (irm|iex), or launch Git Bash for this file.
#
#   curl -fsSL https://github.com/zaaaxx11/Hunter/releases/latest/download/install.sh | bash
#   wget -qO- https://github.com/zaaaxx11/Hunter/releases/latest/download/install.sh | bash
#
# POSIX shells only - do not paste the curl|bash line into PowerShell (there
# `curl` is an Invoke-WebRequest alias and `bash` is absent) or cmd.exe
# (unsupported). Windows PowerShell uses install.ps1 with irm|iex instead.
# The release manifest names the canonical wheel (for example,
# huntos-0.3.0-py3-none-any.whl). The legacy unversioned alias is never
# passed to pip. HUNTOS_BASE_URL may point at a direct artifact directory for local
# mirrors/tests; without it, HUNTOS_VERSION selects a GitHub release tag.
set -eu
# Native Windows Python needs MSYS to translate POSIX paths. Downloads use
# stdout redirection, so no path-conversion exception is needed for curl/wget.
# Clear caller overrides that would otherwise break Git-Bash venv creation.
unset MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL

err() { printf 'install.sh: %s\n' "$1" >&2; }

# Keep Python and pip configuration from the caller out of every child process.
# This also makes a wheel-only install independent of indexes and user config.
clean_run() {
  (
    unset PYTHONPATH PYTHONHOME PIP_CONFIG_FILE PIP_INDEX_URL PIP_EXTRA_INDEX_URL
    exec "$@"
  )
}

REPO="${HUNTOS_REPO:-zaaaxx11/Hunter}"
VERSION="${HUNTOS_VERSION:-}"
# Normalize to the `v*` tag form used by release.yml: both `0.3.0` and
# `v0.3.0` resolve to `v0.3.0` (matching install.ps1). `latest`/empty keeps
# the `/latest/download` path.
case "$VERSION" in
  ''|latest) TAG='' ;;
  v*) TAG="$VERSION" ;;
  *) TAG="v$VERSION" ;;
esac
BASE_OVERRIDE="${HUNTOS_BASE_URL:-}"
if [ -n "$BASE_OVERRIDE" ]; then
  # An override is already the directory containing release artifacts.
  BASE="${BASE_OVERRIDE%/}"
elif [ -n "$TAG" ]; then
  BASE="https://github.com/${REPO}/releases/download/${TAG}"
else
  BASE="https://github.com/${REPO}/releases/latest/download"
fi

if [ -z "${HUNTOS_HOME:-}" ] && [ -z "${HOME:-}" ]; then
  err 'HUNTOS_HOME or HOME must be set.'
  exit 1
fi
HUNTOS_HOME="${HUNTOS_HOME:-${HOME}/.HunterOS}"
# Keep all paths used for activation and the swap absolute, including a local
# relative HUNTOS_HOME override.
case "$HUNTOS_HOME" in
  /*) ;;
  *) HUNTOS_HOME="$(pwd -P)/$HUNTOS_HOME" ;;
esac
VENV="${HUNTOS_HOME}/venv"

TMP=""
STAGING_DIR="${HUNTOS_HOME}/.staging"
STAGING_CREATED=0
STAGE_ROOT=""
STAGED_VENV=""
BACKUP=""
OLD_MOVED=0
NEW_ACTIVATED=0

cleanup() {
  status=$?
  trap - EXIT

  # Nothing in the existing installation is touched until the staged venv has
  # passed all checks. If activation or the final relocation check fails,
  # remove the new tree and put the old tree back where it was.
  if [ "$status" -ne 0 ]; then
    if [ "$NEW_ACTIVATED" -eq 1 ]; then
      rm -rf "$VENV" || :
    fi
    if [ "$OLD_MOVED" -eq 1 ] && { [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; }; then
      if ! mv "$BACKUP" "$VENV"; then
        err "could not restore the previous venv at ${VENV}"
        status=1
      fi
    fi
  fi

  # Only remove directories and files created by this invocation. In
  # particular, .huntos state and the pre-existing venv are not swept broadly.
  if [ -n "$STAGE_ROOT" ]; then
    rm -rf "$STAGE_ROOT" || :
  fi
  if [ "$STAGING_CREATED" -eq 1 ] && [ -d "$STAGING_DIR" ]; then
    rmdir "$STAGING_DIR" 2>/dev/null || :
  fi
  if [ -n "$TMP" ]; then
    rm -rf "$TMP" || :
  fi
  exit "$status"
}
trap cleanup EXIT

fallback_hint() {
  err "release artifacts are not downloadable (repo not public yet, or no release tagged)."
  err "fallback - install editable from a checkout instead:"
  printf >&2 '  git clone https://%s.git hunteros\n' "github.com/${REPO}"
  printf >&2 '  cd hunteros\n'
  printf >&2 '  %s -m pip install --editable ./app --no-deps\n' "${PY:-python}"
  printf >&2 '  hunt --help\n'
}

# --- 1. locate a usable Python >= 3.10 (python3 then python; reject stubs) ---
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 \
    && clean_run "$cand" -c 'import sys' >/dev/null 2>&1 \
    && clean_run "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PY="$(command -v "$cand")"
    # command -v should be absolute for a PATH executable. Resolve unusual
    # shells that return only a command name before using it for diagnostics.
    case "$PY" in
      /*) ;;
      *) PY="$(clean_run "$cand" -c 'import os,sys; print(os.path.abspath(sys.executable))')" ;;
    esac
    case "$PY" in
      /*) break ;;
      *) PY="" ;;
    esac
  fi
done
if [ -z "$PY" ]; then
  err "no absolute Python >= 3.10 found (the Windows Microsoft Store 'python' stub is rejected)."
  err "install Python 3.10+ from https://www.python.org/downloads/ and re-run."
  exit 1
fi

# --- 2. download the manifest, resolve its canonical wheel, then download it --
TMP="$(mktemp -d "${TMPDIR:-/tmp}/huntos-install.XXXXXX")"

fetch() {
  # fetch URL OUTFILE -> curl preferred, wget fallback; both fail on 404.
  if command -v curl >/dev/null 2>&1; then
    # Redirect in the POSIX shell instead of passing a POSIX path to a native
    # Windows curl, which may reject it when MSYS_NO_PATHCONV is set.
    curl -fsSL "$1" >"$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O - "$1" >"$2"
  else
    err "neither curl nor wget is available to download the release."
    return 1
  fi
}

if ! fetch "${BASE}/SHA256SUMS" "${TMP}/SHA256SUMS"; then
  fallback_hint
  exit 1
fi

# Select only a canonical wheel name with a distribution, version, and wheel
# tag portion. This deliberately excludes an unversioned wheel alias.
WHEEL_NAME="$(awk '
  {
    name=$2
    sub(/^\*/, "", name)
    sub(/\r$/, "", name)
    if (name ~ /^huntos-[^-\/[:space:]]+-[^\/[:space:]]+\.whl$/) {
      print name
      exit
    }
  }
' "${TMP}/SHA256SUMS")"
if [ -z "$WHEEL_NAME" ]; then
  err 'SHA256SUMS does not list a canonical huntos-<version>-<tags>.whl - refusing to install.'
  exit 1
fi

EXPECTED="$(awk -v name="$WHEEL_NAME" \
  '{ h=$1; n=$2; sub(/^\*/, "", n); sub(/\r$/, "", n); sub(/\r$/, "", h); if (n == name) { print h; exit } }' \
  "${TMP}/SHA256SUMS")"
case "$EXPECTED" in
  ''|*[!0-9A-Fa-f]*)
    err "SHA256SUMS has no valid sha256 entry for ${WHEEL_NAME} - refusing to install."
    exit 1
    ;;
esac
if [ "${#EXPECTED}" -ne 64 ]; then
  err "SHA256SUMS has no valid sha256 entry for ${WHEEL_NAME} - refusing to install."
  exit 1
fi
EXPECTED="$(printf '%s' "$EXPECTED" | tr '[:upper:]' '[:lower:]')"

WHEEL_PATH="${TMP}/${WHEEL_NAME}"
if ! fetch "${BASE}/${WHEEL_NAME}" "$WHEEL_PATH"; then
  fallback_hint
  exit 1
fi

# --- 3. verify the wheel against SHA256SUMS (fail closed) --------------------
if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL="$(sha256sum "$WHEEL_PATH" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  ACTUAL="$(shasum -a 256 "$WHEEL_PATH" | awk '{print $1}')"
else
  ACTUAL="$(clean_run "$PY" -c '
import hashlib
import sys
with open(sys.argv[1], "rb") as stream:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
print(digest.hexdigest())
' "$WHEEL_PATH")"
fi
if [ "$ACTUAL" != "$EXPECTED" ]; then
  err "sha256 mismatch for ${WHEEL_NAME} - aborting (fail closed)."
  err "  expected: $EXPECTED"
  err "  actual:   $ACTUAL"
  exit 1
fi
printf 'install.sh: sha256 verified for %s (%s...)\n' "$WHEEL_NAME" "$(printf '%s' "$ACTUAL" | cut -c1-16)"

# --- 4. build and validate a fresh staged venv -------------------------------
if [ ! -d "$STAGING_DIR" ]; then
  mkdir -p "$STAGING_DIR"
  STAGING_CREATED=1
fi
STAGE_ROOT="$(mktemp -d "${STAGING_DIR}/install.XXXXXX")"
STAGED_VENV="${STAGE_ROOT}/venv"
clean_run "$PY" -m venv "$STAGED_VENV"

if [ -f "${STAGED_VENV}/bin/python" ]; then
  STAGE_BINDIR=bin
  STAGE_PY_NAME=python
elif [ -f "${STAGED_VENV}/Scripts/python.exe" ]; then
  STAGE_BINDIR=Scripts
  STAGE_PY_NAME=python.exe
elif [ -f "${STAGED_VENV}/Scripts/python" ]; then
  STAGE_BINDIR=Scripts
  STAGE_PY_NAME=python
else
  err "python -m venv did not create an absolute venv interpreter."
  exit 1
fi
STAGE_PY="${STAGED_VENV}/${STAGE_BINDIR}/${STAGE_PY_NAME}"
clean_run "$STAGE_PY" -m pip install --isolated --no-index --no-deps "$WHEEL_PATH" >/dev/null

validate_install() {
  CHECK_ROOT="$1"
  CHECK_PY="$2"
  CHECK_BINDIR="$3"
  CHECK_HUNT=""

  case "$CHECK_PY" in
    /*) ;;
    *) err "venv Python is not absolute: ${CHECK_PY}"; return 1 ;;
  esac
  if [ -f "${CHECK_ROOT}/${CHECK_BINDIR}/hunt" ]; then
    CHECK_HUNT="${CHECK_ROOT}/${CHECK_BINDIR}/hunt"
  elif [ -f "${CHECK_ROOT}/${CHECK_BINDIR}/hunt.exe" ]; then
    CHECK_HUNT="${CHECK_ROOT}/${CHECK_BINDIR}/hunt.exe"
  else
    err "installed hunt executable was not found in ${CHECK_ROOT}/${CHECK_BINDIR}."
    return 1
  fi
  case "$CHECK_HUNT" in
    /*) ;;
    *) err "hunt executable is not absolute: ${CHECK_HUNT}"; return 1 ;;
  esac

  # Run from a foreign temporary cwd so a source checkout cannot satisfy the
  # module/package-data checks accidentally.
  (
    cd "$TMP"
    clean_run "$CHECK_PY" -c '
import pathlib
import sys
import huntos

root = pathlib.Path(huntos.__file__).resolve().parent
prefix = pathlib.Path(sys.prefix).resolve()
if not pathlib.Path(sys.executable).is_absolute():
    raise SystemExit("python executable is not absolute")
if not root.is_relative_to(prefix):
    raise SystemExit("huntos was imported outside the staged venv")
required = (
    root / "_data" / "idea" / "skills" / "INDEX.md",
    root / "_data" / "roles",
    root / "_data" / "hooks",
    root / "_data" / "bin",
)
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit("missing package data: " + ", ".join(missing))
' >/dev/null
    clean_run "$CHECK_PY" -m huntos --help >/dev/null
    clean_run "$CHECK_HUNT" --help >/dev/null
    # Hermes is deliberately a no-op and does not open or create .huntos state.
    clean_run "$CHECK_HUNT" install --adapter hermes >/dev/null
  )
}

validate_install "$STAGED_VENV" "$STAGE_PY" "$STAGE_BINDIR"

# --- 5. atomically activate, repair moved venv entry points, and re-check ----
# A venv contains entry-point shebangs with its creation path. Reinstalling
# the already-verified local wheel after the directory rename rewrites those
# entry points to the activated absolute path without contacting an index.
BACKUP="${STAGE_ROOT}/previous-venv"
if [ -e "$VENV" ] || [ -L "$VENV" ]; then
  mv "$VENV" "$BACKUP"
  OLD_MOVED=1
fi
mv "$STAGED_VENV" "$VENV"
NEW_ACTIVATED=1

ACTIVE_PY="${VENV}/${STAGE_BINDIR}/${STAGE_PY_NAME}"
clean_run "$ACTIVE_PY" -m pip install --isolated --no-index --no-deps --force-reinstall "$WHEEL_PATH" >/dev/null
validate_install "$VENV" "$ACTIVE_PY" "$STAGE_BINDIR"
ACTIVE_HUNT="$CHECK_HUNT"

printf 'install.sh: installed into %s\n' "$VENV"
printf 'install.sh: add it to PATH with:\n'
printf '  export PATH="%s/%s:$PATH"\n' "$VENV" "$STAGE_BINDIR"
printf 'then: hunt --help\n'
exit 0
