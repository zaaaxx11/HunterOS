# HUNT-OS

A command-line hunt manager for authorized security work. HUNT-OS keeps every fact of a hunt (targets, findings, PoC runs, verifications, reports) in a local SQLite ledger that is only writable through the `hunt` CLI, so state survives interrupted sessions and reports are always generated from recorded facts.

**Quick facts:**
- Python 3.10+ | No runtime dependencies | Windows, Linux, macOS
- Local SQLite ledger with CLI-only writes
- See [QUICKSTART.md](QUICKSTART.md) for your first hunt

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
  - [Quick Start](#quick-start)
  - [Platform-Specific Instructions](#platform-specific-instructions)
  - [Troubleshooting](#troubleshooting)
  - [Advanced Options](#advanced-options)
- [First Steps](#first-steps)
- [Project Structure](#project-structure)
- [Agent Integration](#agent-integration)
- [Safety & Authorization](#safety--authorization)

---

## Requirements

- **Python 3.10 or newer** (verify: `python --version` or `py -3 --version`)
- **Supported OS:** Windows, Linux, macOS
- **No external dependencies** (stdlib only)

---

## Installation

The release bootstrap installer puts the `hunt` CLI and Python package on your machine in a user-level virtual environment. This does **not** configure agent harness integrations; that is a separate `hunt install` step.

### Quick Start

Choose your platform and copy the command:

| Platform | Command |
|----------|---------|
| **Linux / macOS / Git Bash / WSL** | `curl -fsSL https://github.com/zaaaxx11/Hunter/releases/latest/download/install.sh \| bash` |
| **PowerShell 5.1+ / pwsh** | `irm https://github.com/zaaaxx11/Hunter/releases/latest/download/install.ps1 \| iex` |
| **cmd.exe** | Not supported — use PowerShell or Git Bash |

After installation completes, verify:

```sh
hunt --help
hunt harness list
```

After the first install, update HUNT-OS directly from the verified release
wheel without running `curl` or `irm` again:

```sh
hunt update
hunt update --check
```

`--check` downloads and verifies the release without changing the installed
package. `HUNTOS_BASE_URL`, `HUNTOS_REPO`, and `HUNTOS_VERSION` can be set for
an internal mirror or a pinned release.

On PowerShell `hunt` works immediately in the same shell (the installer
prepends the venv `Scripts` dir to process `$env:Path` and persists it to
User PATH for future shells). On POSIX copy-paste the printed
`export PATH=...` line first (`curl|bash` runs in a child process and cannot
update the parent shell).

### Platform-Specific Instructions

<details>
<summary><strong>Linux, macOS, Git Bash, WSL</strong> (expand for details)</summary>

```sh
curl -fsSL https://github.com/zaaaxx11/Hunter/releases/latest/download/install.sh | bash
```

The script downloads the wheel, verifies the SHA-256, installs into `.HunterOS/venv`, and prints PATH instructions.

</details>

<details>
<summary><strong>PowerShell 5.1+ / pwsh</strong> (expand for details)</summary>

**Standard install (most systems):**
```powershell
irm https://github.com/zaaaxx11/Hunter/releases/latest/download/install.ps1 | iex
```

**Older PowerShell 5.1 with TLS errors** (one-time pre-step):
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
# Then run the standard install above
```

GitHub requires TLS 1.2; this pre-step allows the initial download to proceed.

</details>

<details>
<summary><strong>cmd.exe</strong> (not supported)</summary>

`cmd.exe` does not support shell pipes. Use PowerShell or Git Bash instead:
- **PowerShell:** `powershell.exe` then the PowerShell install command
- **Git Bash:** Launch Git Bash and use the POSIX install command

</details>

### Troubleshooting

<details>
<summary>Common errors and solutions</summary>

**PowerShell: `'irm' is not recognized`**
- You are in `cmd.exe`, not PowerShell. Type `powershell.exe`, press Enter, then retry.

**Error: `The underlying connection was closed` (PowerShell 5.1 only)**
- GitHub requires TLS 1.2. Run the TLS pre-step once, then retry the install.

**Error: `release SHA256SUMS could not be downloaded`**
- The release is missing or unreachable. The script prints an editable-checkout fallback.

**Error: `SHA256SUMS does not list...`**
- The manifest is corrupted. Verify your network connection and retry.

**Hunt commands not found after install**
- On PowerShell the installer applies PATH automatically (`hunt` works in the
  same shell immediately and User PATH is persisted for new shells). If a
  shell was already open before the install, restart it or run
  `$env:Path = "C:\Users\you\.HunterOS\venv\Scripts;" + $env:Path`.
- On POSIX `curl|bash` runs in a child process and cannot update the parent
  shell: copy-paste the printed `export PATH=...` line.
- Verify: `echo $PATH` (POSIX) or `$env:PATH` (PowerShell)

</details>

### Advanced Options

**Pin a specific release version:**

```sh
HUNTOS_VERSION=0.3.0 bash install.sh
```

```powershell
$env:HUNTOS_VERSION = '0.3.0'; irm https://github.com/zaaaxx11/Hunter/releases/download/v0.3.0/install.ps1 | iex
```

Both `0.3.0` and `v0.3.0` resolve to the same tag; omit to use `latest`.

**Use a local mirror:**

For a reviewed local mirror or release fixture, set `HUNTOS_BASE_URL` to the
folder containing the canonical wheel and `SHA256SUMS` (it overrides the
GitHub release URL entirely, e.g. `HUNTOS_BASE_URL=https://mirror.example.com/huntos bash install.sh`).
Note: `HUNTOS_BASE_URL` only redirects the in-script wheel/`SHA256SUMS` fetch
after the installer is already running — it does not replace the initial
installer download. Fully offline means downloading the reviewed installer
file locally first and running it (`bash install.sh` / `.\install.ps1`).
The installer refuses
missing, malformed, or mismatched checksums and never performs an implicit pip
upgrade. The local override is primarily for controlled mirrors and testing;
keep HTTPS and a trusted artifact source for normal use.

By default the bootstrap creates a user-level virtual environment under
`.HunterOS`: `$HOME/.HunterOS/venv` on POSIX/Git Bash and
`$env:USERPROFILE\.HunterOS\venv` on PowerShell. Set `HUNTOS_HOME` to choose a
different root; set `HUNTOS_USE_PIPX=1` only to opt into pipx's own layout. On
PowerShell the installer applies PATH automatically: `hunt` works in the same
shell immediately (the Scripts dir is prepended to process `$env:Path` and
persisted idempotently to User PATH, so new shells find it too; a restart is
only needed for shells already open before the install). On POSIX `curl|bash`
runs in a child process and cannot export to the parent shell, so copy-paste
the printed `export PATH=...` line, then verify from any directory:

```sh
hunt --help
python -m huntos --help
hunt harness list
```

**Custom installation directory:**

```sh
HUNTOS_HOME=/custom/path bash install.sh
```

**Source-based development:**

```sh
python -m pip install --editable ./app --no-deps
```

**State directories (do not confuse these):**
- `.HunterOS` — application environment (Python venv, package files; replaced on upgrade)
- `.huntos` — persistent state (hunt.db, adapter registry, workspaces; survives upgrades)
- Set `HUNT_DB` to use a different ledger path
- Create `.huntos-project` in a working directory to bind that directory to one ledger

---

## First Steps

Start the guided setup:

```sh
hunt                      # guided setup: enter a target source and start
hunt shell                # interactive console; type commands without the prefix
hunt status               # the full picture of the current hunt
hunt next                 # the one recommended next command
hunt doctor               # workspace preflight
```

**Typical workflow:** Prepare an authorized target → run a bounded round → record findings → let the CLI enforce claims.

**Full guides:**
- **Day-one tour:** [QUICKSTART.md](QUICKSTART.md)
- **Full reference:** [app/WALKTHROUGH.md](app/WALKTHROUGH.md)

---

## Project Structure

| Path | Contents |
|------|----------|
| `app/` | CLI and ledger (Python stdlib only) |
| `tests/smoke/` | Public smoke and contract tests |
| `app/src/huntos/_data/idea/` | `IDEA.md` doctrine, `HUNT-BRIDGE.md`, skill corpus |
| `app/src/huntos/_data/roles/` | Seven lane-role doctrine files |
| `app/src/huntos/_data/bin/`, `app/src/huntos/_data/hooks/` | Claim gate and hook wrappers |
| `install.sh`, `install.ps1` | Release installers |
| `QUICKSTART.md`, `app/WALKTHROUGH.md` | Operator guides |
| `docs/HUNT-ADAPTER-1.md` | Adapter protocol specification |
| `templates/`, `checks/` | Report templates and pre-report checklist |
| `.github/workflows/` | CI: tests on Linux/Windows, release on `v*` tags |
| `examples/practice_target/` | Educational vulnerable web app for practice hunts |
| `pr/` | Known issues and deferred work (see [pr/OPEN-PROBLEMS.md](pr/OPEN-PROBLEMS.md)) |

---

## Agent Integration

Two integration modes:

### Skill-Only Mode (Any Harness)

Install skills, roles, bridge, and hooks into your harness without installing Python:

```sh
hunt install --adapter claude-code
hunt install --adapter zcode
hunt install --adapter generic --dir /path/to/harness/skills
```

### Managed Mode (Custom Adapter Required)

Requires your own adapter executable implementing the `HUNT-ADAPTER/1` protocol ([spec](docs/HUNT-ADAPTER-1.md)). The bundled reference implementation (`examples/adapters/reference_jsonl.py`) demonstrates the protocol with deterministic simulation, not real agents.

---

## Safety & Authorization

- ⚠️ **Only use this against systems you are authorized to test.**
- Refusals print `BLOCKED:` and exit code 2; gates are enforced by code, not config.
- Built-in mock runs are labeled `SIMULATED` for demos and tests only.

**Security model:** Remote-script installations (`curl | bash`, `irm | iex`) execute downloaded bytes with your privileges. Scripts verify the wheel's SHA-256 *after* they run, but do not authenticate the script itself. If that trust model is unacceptable:
1. Download and review the installer locally
2. Pin a release version
3. Run the reviewed file instead of piping it to a shell

---

**Need help?** Open an issue, or run `hunt doctor` to check your workspace preflight.
