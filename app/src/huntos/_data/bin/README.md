# bridge — the claim gate

## What this is

`claim_gate.py` is a harness-agnostic hook that guards the engine's mouth.
An engine that hunts with HUNT-OS may *suspect* anything, but its output may
not *claim* more than the database can back. The gate reads the engine's
output text, scans it for the strong-claim markers `PROVEN` and
`EXPLOITABLE` (exact, case-sensitive) plus the phrase `admin takeover`
(case-insensitive), and checks every claim against the hunt db. Every claim
must name its object: either an explicit bind — the marker immediately
followed by a bracketed id (`PROVEN[F-3]` / `EXPLOITABLE[F-3]` for findings,
`PROVEN[L-2]` for leads), which is the authoritative binding for that
occurrence — or, for bare markers, the nearest id nearby (`F-<n>` or `#<n>`
for findings, `L-<n>` for leads; same line or within 80 characters of the
marker). A finding-bound claim passes only if that finding's ladder status is
`proven-live`; a lead-bound claim passes only if the lead is `promoted` AND
the finding it minted is still `proven-live` (a lead claim dies with its
finding). An unbound claim is a veto, always: proof of some other finding
somewhere in the db backs a claim that names nothing — the db decides which
claims are proven, in the same enforcement style as the hunt CLI. The gate
never writes: the db is opened read-only, and a missing or unreadable db is
fail-closed (claims cannot be verified, so they cannot pass).

## The hook contract

- **Input:** the engine's output text — piped to stdin, or a file path given
  as `argv[1]`. Empty input (nothing piped, no argument) passes: there is
  nothing to check.
- **Exit 0** = pass. Prints one line to stdout: `claim gate: no unbacked claims`.
- **Exit 2** = veto. Prints one `BLOCKED: ...` line to stderr naming the claim
  and what the database actually says. A hook-capable harness turns a non-zero
  exit into a failed turn; the engine must then earn the claim through the hunt
  CLI (`hunt finding promote`, `hunt verify`, `hunt challenge`) instead of
  asserting it.
- **Fail-closed:** if the db cannot be reached or read, claims cannot be
  verified — so they cannot pass. No markers in the text means the db is never
  touched.
- **Environment:** `HUNT_DB` selects the database, exactly like the CLI
  (default `~/.huntos/hunt.db`).

## Wiring it into a harness

The bootstrap installers (`install.sh`/`install.ps1`) install the Python CLI;
they do not install or wire this gate. The separate `hunt install` skills
installer copies the shipped hook pack into every installed layer as the fixed,
manifest-tracked layout `hunt-os/hooks/claim_gate_wrapper.sh`,
`claim_gate_wrapper.py`, and `claim_gate.py` (a byte-copy of this gate at
skills-install time). Both wrappers resolve the gate relative to their own
directory — never a git checkout or a remote URL — forward stdin, preserve
stdout/stderr and exit status, honor `HUNT_DB`, and evaluate the project lock in
`HUNT_PROJECT_DIR` when the harness does not preserve cwd. The Python wrapper
uses its current interpreter and is the native Windows path. **Wiring guide:
`app/src/huntos/_data/hooks/README.md`.** The generic POSIX post-output recipe:

```sh
<engine output> | HUNT_DB=/path/to/hunt.db \
    sh /path/to/skills/hunt-os/hooks/claim_gate_wrapper.sh
```

PowerShell/native Windows uses the installed Python wrapper:

```powershell
$env:HUNT_DB = "C:\Hunt\hunt.db"
Get-Content -Raw .\engine_output.txt |
  python C:\Skills\hunt-os\hooks\claim_gate_wrapper.py
if ($LASTEXITCODE -ne 0) { throw "claim gate veto" }
```

Beyond the shipped pack, three generic patterns cover harnesses that cannot
run the wrapper directly. None require special support from this repo — any
harness that can run a command around message generation works. Paths and
field names below are placeholders; adapt them to your tool.

### (a) Post-output / stop hook

The harness runs a command when the assistant finishes composing a message and
pipes that message to the command's stdin. A non-zero exit blocks the message
or ends the turn — attach your blocking policy to the exit code.

### (b) Pre-display filter

The harness writes the composed message to a file before rendering it and runs
the gate with the file path as the argument. Same verdicts; the message is
shown only when the gate exits 0.

### (c) Manual / audit mode

No hooks needed. After a session, run the packaged gate over the transcript:

    python /path/to/huntos/_data/bin/claim_gate.py session_transcript.txt

Same scanning and verdicts as the wired modes; the exit code is the signal
(0 = transcript made no unbacked claims, 2 = at least one — see stderr).

### Example pseudo-config (illustrative only — prefer the shipped hook pack above)

The JSON below is the OLD illustrative blob, kept only to show the shape of a
post-output hook. It is not a verified settings schema for any specific
harness — do not paste it into real settings. Use the shipped
`hunt-os/hooks/` wrapper via `app/src/huntos/_data/hooks/README.md` instead.

```json
{
  "hooks": {
    "on_assistant_message": {
      "command": "python /path/to/huntos/_data/bin/claim_gate.py",
      "input": "stdin",              // or "tempfile": path passed as argv[1]
      "on_nonzero_exit": "block_message_and_report_stderr"
    }
  }
}
```

**The project lock:** when the working directory contains a `.huntos-project`
lock file (written by `hunt project bind`), the gate also verifies the opened
db against it before evaluating any claim. A `HUNT_DB` pointed at a fabricated
database — even one with a planted proven-live row — cannot pass in a bound
workspace: the db cannot prove it is the ledger the directory is bound to, so
the turn is vetoed (`BLOCKED:` on stderr, exit 2). Unbound workspaces behave
exactly as before.

## Pair it with the skill

The gate is the enforcement half of the bridge. The other half is the skill
`huntos/_data/idea/HUNT-BRIDGE.md`, which teaches the engine to *use* the hunt CLI —
record findings, walk the evidence ladder, log verifier events — instead of
narrating results. The skill gives the engine an honest path; the gate makes
the dishonest path mechanically fail. Ship them together.

## Notes

- The gate only guards output text. It does not judge whether a PoC is real
  (that is P2 territory); it enforces that whatever is claimed is already
  backed by `proven-live` rows in the one state that cannot lie — the db.
- The db URI is normalized to forward slashes, so Windows `HUNT_DB` values
  like `C:\Users\you\.huntos\hunt.db` work as-is.
