# HUNT-OS

A command-line hunt manager for authorized security work. HUNT-OS keeps every
fact of a hunt (targets, findings, PoC runs, verifications, reports) in a local
SQLite ledger that is only writable through the `hunt` CLI, so state survives
interrupted sessions and reports are always generated from recorded facts.

Python 3.10 or newer. No runtime dependencies. Runs on Windows, Linux, and
macOS.

## Install the CLI

The release bootstrap installer puts the `hunt` CLI and its Python package on
your machine. It does **not** install skills into an agent harness; that is a
separate `hunt install` step described below.

> If your prompt shows `C:\Users\you>` without a `PS` prefix, you are in
> `cmd.exe` — stop. Neither installer pipe works here (`'irm' is not
> recognized` proves it). Type `powershell.exe`, press Enter (prompt becomes
> `PS C:\...>`), then use the PowerShell block below. For Git-Bash, launch
> `Git Bash` (or `"C:\Program Files\Git\bin\bash.exe"`) and use the POSIX
> block. Do not paste either pipe into `cmd.exe`.

POSIX shells (including Git Bash):

```sh
curl -fsSL https://github.com/zaaaxx11/Hunter/releases/latest/download/install.sh | bash
```

PowerShell (5.1+ / pwsh) — single line:

```powershell
irm https://github.com/zaaaxx11/Hunter/releases/latest/download/install.ps1 | iex
```

Only on old Windows PowerShell 5.1 where the line above fails with
`The underlying connection was closed`, run this TLS pre-step once first
(GitHub requires TLS 1.2; the in-script fix cannot help the initial fetch):

```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
```

Preflight: `$PSVersionTable.PSVersion`, `py -3 --version` (>= 3.10;
the Microsoft Store stub is rejected), and `Get-Command curl` (in PowerShell
`curl` is an `Invoke-WebRequest` alias — `curl -fsSL ... | bash` only works in
POSIX shells/Git-Bash/WSL, never in PowerShell; `cmd.exe` is unsupported).

If `irm` reports `release SHA256SUMS could not be downloaded`, the release is
missing or unreachable (fail closed). `SHA256SUMS does not list...` means a
bad manifest. Both cases print the editable-checkout fallback.

These commands are remote-script pipes. They execute the bytes fetched from
GitHub with your user privileges. The scripts verify the downloaded wheel's
SHA-256 after they start, but that does not authenticate the script itself. If
that trust model is not acceptable, download and review the installer, pin a
release, and run the reviewed file locally instead of piping it to a shell.

For a reproducible release, pin the package version before running the wrapper
(both `0.3.0` and `v0.3.0` resolve to the `v0.3.0` release tag):

```sh
HUNTOS_VERSION=0.3.0 bash install.sh
# HUNTOS_VERSION=v0.3.0 also works; HUNTOS_VERSION=latest (or unset) uses latest/download
```

```powershell
$env:HUNTOS_VERSION = '0.3.0'; irm https://github.com/zaaaxx11/Hunter/releases/download/v0.3.0/install.ps1 | iex
```

| Shell | Type this only | Do not type |
|---|---|---|
| Windows PowerShell 5.1+ / pwsh | `irm ... \| iex` (with TLS pre-step above) | `curl -fsSL ... \| bash` — `curl` is an `Invoke-WebRequest` alias, `bash` is absent (causes `ParameterBindingException`) |
| Git-Bash / WSL / Linux / macOS | `curl -fsSL ... \| bash` | `irm ... \| iex` |
| `cmd.exe` | unsupported — use PowerShell or Git Bash | either pipe |

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
different root; set `HUNTOS_USE_PIPX=1` only to opt into pipx's own layout. Add
the venv's `bin` (POSIX) or `Scripts` (PowerShell) directory to `PATH` as the
installer instructs, then verify from any directory:

```sh
hunt --help
python -m huntos --help
hunt harness list
```

`.HunterOS` is the application environment: it contains the Python environment
and installed package files, which upgrades may replace. `.huntos` is the
persistent HUNT-OS state directory: by default it contains `hunt.db`, the
adapter registry, and GitHub workspaces. `HUNT_DB` can select another ledger;
`.huntos-project` in a working directory can bind that directory to one ledger.
Do not use `.HunterOS` as the ledger location.

If the release is unavailable, the wrapper prints an editable-checkout fallback;
it does not silently clone or execute an unpinned source tree. For source-based
development, install explicitly from a checkout:

```sh
python -m pip install --editable ./app --no-deps
```

## Use

```sh
hunt                      # guided setup: enter a target source and start
hunt shell                # interactive console; type commands without the prefix
hunt status               # the full picture of the current hunt
hunt next                 # the one recommended next command
hunt doctor               # workspace preflight
```

Typical loop: prepare an authorized target, run a bounded round, record what
you find, and let the CLI enforce what may be claimed. Day-one tour:
[QUICKSTART.md](QUICKSTART.md). Full reference: [app/WALKTHROUGH.md](app/WALKTHROUGH.md).

## Integrating your agent harness

- Skill-only mode (any harness): after installing the CLI, copy the packaged
  skills, roles, bridge, and hook pack into the harness with the separate
  `hunt install` skills installer. It does not install Python or the `hunt`
  command, and it does not configure a product-specific hook schema.

  ```sh
  hunt install --adapter claude-code
  hunt install --adapter zcode
  hunt install --adapter generic --dir /path/to/harness/skills
  ```

- Managed mode: requires your own adapter executable implementing
  `HUNT-ADAPTER/1` ([spec](docs/HUNT-ADAPTER-1.md)). The bundled
  `examples/adapters/reference_jsonl.py` demonstrates the protocol; it is a
  deterministic simulation, not a real agent.

## Contents

| Path | Contents |
|---|---|
| `app/` | the CLI and ledger source (stdlib-only Python) |
| `tests/smoke/` | tracked public smoke/contract tests |
| `app/src/huntos/_data/idea/` | `IDEA.md` doctrine, `HUNT-BRIDGE.md`, and the skill corpus loaded into harnesses |
| `app/src/huntos/_data/roles/` | the seven lane-role doctrine files |
| `app/src/huntos/_data/bin/`, `app/src/huntos/_data/hooks/` | claim gate and the hook wrappers |
| `install.sh`, `install.ps1` | release installers (wheel download + sha256 verification) |
| `QUICKSTART.md`, `app/WALKTHROUGH.md` | operator guides |
| `docs/HUNT-ADAPTER-1.md` | adapter protocol for managed mode |
| `templates/`, `checks/` | report/finding templates and pre-report checklist |
| `.github/workflows/` | CI: tests on Linux and Windows, install smoke; release on `v*` tags |

## Notes

- Only use this against systems you are authorized to test.
- Refusals print `BLOCKED:` and exit 2; gates are enforced by code, not config.
- Built-in mock runs are labelled SIMULATED and are for demos and tests only.
