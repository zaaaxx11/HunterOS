# Installed claim-gate hook pack

The bootstrap installers (`install.sh`/`install.ps1`) install the Python CLI; they
do not wire a harness. The separate `hunt install` skills installer copies this
fixed, manifest-tracked hook pack into a harness skills directory:

```text
<skills-dir>/hunt-os/hooks/claim_gate_wrapper.sh
<skills-dir>/hunt-os/hooks/claim_gate_wrapper.py
<skills-dir>/hunt-os/hooks/claim_gate.py
```

The gate is a byte-copy of the packaged `huntos/_data/bin/claim_gate.py` at
skills-install time. Both wrappers resolve only that adjacent copy; they do not
look in a git checkout or fetch code remotely. `hunt install --check` verifies
every hash and `--uninstall` removes only unchanged manifest-owned files.
Operator-modified files are retained.

## Contract

- Engine output arrives on stdin and is forwarded unchanged to the gate.
- Gate stdout and stderr pass through unchanged.
- Exit `0` passes. Exit `2` vetoes and prints `BLOCKED:` on stderr. Other gate exit codes are preserved exactly.
- `HUNT_DB` selects the read-only ledger (default `~/.huntos/hunt.db`). Claims with a missing, unreadable, or foreign db fail closed.
- `HUNT_PROJECT_DIR`, when set, must be a readable directory. The gate runs there so `.huntos-project` is checked even when the harness starts elsewhere.
- A missing or unreadable adjacent gate, unusable project directory, or launcher failure exits 2.
- Neither wrapper reads an adapter or gate from a target tree.

The POSIX wrapper supports `HUNT_PYTHON` for environments where `python` is not on `PATH`. The Python wrapper deliberately uses its running interpreter (`sys.executable`), which is the safe native Windows path.

## POSIX

Pipe the final assistant output to the shell wrapper and make nonzero mean “block the message / fail the turn”:

```sh
HUNT_DB=/absolute/path/hunt.db \
HUNT_PROJECT_DIR=/absolute/path/project \
sh /absolute/path/skills/hunt-os/hooks/claim_gate_wrapper.sh < engine_output.txt
```

Or use the cross-platform wrapper:

```sh
HUNT_DB=/absolute/path/hunt.db \
python /absolute/path/skills/hunt-os/hooks/claim_gate_wrapper.py < engine_output.txt
```

## PowerShell and native Windows

PowerShell pipeline:

```powershell
$env:HUNT_DB = "C:\Hunt\hunt.db"
$env:HUNT_PROJECT_DIR = "C:\Hunt\project"
Get-Content -Raw .\engine_output.txt |
  python C:\Skills\hunt-os\hooks\claim_gate_wrapper.py
if ($LASTEXITCODE -ne 0) { throw "claim gate vetoed the output" }
```

Native process integration should execute this argv without a shell:

```text
["C:\Path\To\python.exe", "C:\Skills\hunt-os\hooks\claim_gate_wrapper.py"]
```

Write the complete candidate message to the process stdin, inherit or relay stdout/stderr, and block on any nonzero exit. Do not use shell quoting or an unverified harness-specific config schema.

## Harness integration

Use the wrapper as a post-output/stop hook, pre-display filter, or manual audit command. Claude Code and ZCode skill installation alone does **not** prove a managed or hook integration. This repository intentionally does not invent either product’s current hook configuration schema. Wire the generic stdin/exit-code contract using that harness’s verified documentation.

Manual smoke test:

```sh
printf '%s\n' 'PROVEN[F-1]' | HUNT_DB=/path/to/hunt.db \
  python /path/to/skills/hunt-os/hooks/claim_gate_wrapper.py
```

This exits 0 only if finding F-1 is `proven-live` in the selected, project-bound ledger. Empty input passes because there is no claim to check.
