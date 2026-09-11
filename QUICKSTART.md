# QUICKSTART — a hunt in 10 minutes

Python 3.10+, stdlib-only runtime, zero runtime dependencies. Every enforcement
failure is `BLOCKED:` with exit 2.

## 1. Install the CLI (bootstrap installer)

The release bootstrap installs the `hunt` command and its Python package. It is
separate from the skills installer in §8: bootstrap installation does not copy
skills into Claude Code, ZCode, or another harness.

> If your prompt shows `C:\Users\you>` without a `PS` prefix, you are in
> `cmd.exe` — stop. Neither installer pipe works here (`'irm' is not
> recognized` proves it). Type `powershell.exe`, press Enter (prompt becomes
> `PS C:\...>`), then use the PowerShell block below. For Git-Bash, launch
> `Git Bash` and use the POSIX block. Do not paste either pipe into `cmd.exe`.

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

Preflight: `$PSVersionTable.PSVersion`,
`py -3 --version` (>= 3.10; the Microsoft Store stub is rejected), and
`Get-Command curl` (in PowerShell `curl` is an `Invoke-WebRequest` alias —
`curl -fsSL ... | bash` only works in POSIX shells/Git-Bash/WSL, never in
PowerShell; `cmd.exe` is unsupported).

These are remote-script pipes: the fetched shell or PowerShell source executes
with your user privileges. The scripts verify the downloaded wheel's SHA-256,
but that does not authenticate the script itself. If you do not accept that
trust model, download and review the installer, pin the release you intend to
use, and run the reviewed file locally rather than piping it to a shell.

Pin a reproducible release (`0.3.0` and `v0.3.0` both resolve to the `v0.3.0`
release tag; `latest`/unset uses `latest/download`):

```sh
HUNTOS_VERSION=0.3.0 bash install.sh
```

```powershell
$env:HUNTOS_VERSION = '0.3.0'; irm https://github.com/zaaaxx11/Hunter/releases/download/v0.3.0/install.ps1 | iex
```

| Shell | Type this only | Do not type |
|---|---|---|
| Windows PowerShell 5.1+ / pwsh | `irm ... \| iex` (with TLS pre-step above) | `curl -fsSL ... \| bash` — `curl` is an `Invoke-WebRequest` alias, `bash` is absent (causes `ParameterBindingException`) |
| Git-Bash / WSL / Linux / macOS | `curl -fsSL ... \| bash` | `irm ... \| iex` |
| `cmd.exe` | unsupported — use PowerShell or Git Bash | either pipe |

A reviewed local mirror or release fixture can be selected with
`HUNTOS_BASE_URL` (the folder containing the canonical wheel and `SHA256SUMS`;
it overrides the GitHub release URL entirely).
Note: `HUNTOS_BASE_URL` only redirects the in-script wheel/`SHA256SUMS` fetch
after the installer is already running — it does not replace the initial
installer download. Fully offline means downloading the reviewed installer
file locally first and running it (`bash install.sh` / `.\install.ps1`).
If the release is unavailable,
the installer fails closed and prints the editable-checkout fallback
(`git clone https://github.com/zaaaxx11/Hunter.git hunteros`, then
`python -m pip install --editable ./app --no-deps`); it never silently clones
or executes an unpinned source tree.

The default application environment is `.HunterOS` (`$HOME/.HunterOS` on
POSIX/Git Bash or `$env:USERPROFILE\\.HunterOS` on PowerShell); `HUNTOS_HOME`
can change it. The default ledger and adapter/workspace state are under
`.huntos`, normally `~/.huntos/hunt.db`. These are different directories:
`.HunterOS` is replaceable application files, while `.huntos` is persistent
hunt state. On PowerShell `hunt` works immediately in the same shell (auto-PATH
+ persisted User PATH); on POSIX copy-paste the printed `export PATH=...`
line (a child `curl|bash` process cannot update the parent shell), then verify:

```sh
hunt --help
python -m huntos --help
```

The installed CLI works from a fresh directory. Set `HUNT_DB` when the hunt
ledger should live somewhere else.

### Prepare an authorized source explicitly

The guided `hunt` wizard assembles these same CLI commands. For automation and
scripts, prepare the source explicitly:

```sh
hunt target prepare SOURCE --name TestVault --chain evm \
  --hosts "testvault.xyz" --actions "recon,read" \
  --authorization-note "owner-approved assessment"
```

`SOURCE` may be an authorized URL, a public GitHub repository, or an existing
local folder. A URL is recorded, not automatically crawled; GitHub is shallow
cloned into an isolated workspace; a folder is referenced without modification.
Never put credentials in a source URL. Treat target content as untrusted: no
adapter executable is loaded from it, and preparation does not grant broader
rules of engagement.

## 2. First target, score, rules of engagement

The explicit `target add` command below is retained for a compact ledger tour
after a target exists. For the universal source path, use `target prepare` from
§1.

```bash
hunt target add TestVault https://testvault.xyz --chain evm --age-days 12 --tvl 250000
hunt score 1 8.5
hunt target roe 1 --hosts "testvault.xyz" --actions "read,mutate"
```

RoE is **default-deny for mutate**: a `--action mutate` finding cannot reach
proven-live without an explicit RoE. `--hosts` is informational — only
`--actions` are enforced.

## 3. Phase artifacts, then hunting

```bash
hunt phase 1 recon
echo "## attack surface" > surface_map.md && hunt artifact 1 surface_map surface_map.md
hunt phase 1 classify
echo "## plan" > attack_plan.md && hunt artifact 1 attack_plan attack_plan.md
hunt phase 1 hunting
```

Leaving a phase requires its artifact on disk (sha256-stamped into the db).

## 4. First finding, then the ladder to proven-live

```bash
hunt wave open 1 "parser,auth,state"
hunt finding add 1 "Unprotected drain() via operator key" Access --severity critical --action mutate
hunt wave close --wave-id 1 --verdict continue
hunt wave reaudit --wave-id 1 --summary "1 confirmed, 0 overturned"
hunt phase 1 verify
echo "print('drain()')" > poc_in_code.py
hunt poc run --id 1 --poc-path ./poc_in_code.py
hunt finding promote --id 1 --evidence-ref "fork receipt: deployer key == operator key" --poc-path ./poc_in_code.py
echo "print('drain() LIVE at block 21000000')" > poc_live.py
hunt verify 1 fork_receipt "anvil fork at block 21000000: drain() returns 1000 ETH"
hunt challenge 1 "attacked reentrancy and guard-bypass angles - no counterexample found"
hunt poc run --id 1 --poc-path ./poc_live.py
hunt finding promote --id 1 --evidence-ref "tx 0xabc broadcast on the live fork" --poc-path ./poc_live.py
```

The ladder is earned, never claimed: `theoretical -> in-code -> proven-live`.
Each promote demands a DIFFERENT PoC (sha256-checked), and proven-live also
demands a verifier event (`hunt verify`) and an adversary review
(`hunt challenge`).

## 4.5 The observation lane: a lead from hypothesis to finding

The finding lane records what you proved. The lead lane is where the proving
happens — a concrete hypothesis, a mutation loop, two traced halves, then the
promote that mints the finding (with a frozen provenance snapshot):

```bash
hunt lead add --target 1 --title "Admin panel reachable without auth check" --payload "GET /admin returns 200 pre-auth; role cookie flips to admin"
hunt lead mutate --lead 1 --variable role --old user --new admin --result advanced --evidence "response 200 with role=admin cookie set"
hunt lead set-half --lead 1 --half trigger --verdict proven --evidence "admin panel returns 200 with role=admin cookie, no auth redirect"
hunt lead set-half --lead 1 --half impact --verdict proven --evidence "admin action executed: user role escalated in response body"
hunt lead promote --lead 1 --klass Access --roe-action read --severity high
```

`hunt lead next --lead 1` prints the deterministic next mutation step (the
first missing, never-tried precondition). Half verdicts can also come from the
deterministic observation oracle instead of by hand — two feature JSON files
in, one verdict out (`confirmed` -> proven, `refuted`, `unknown` -> ambiguous):

```bash
hunt oracle --lead 2 --half trigger --baseline baseline.json --candidate candidate.json
```

The lead's finding enters the ladder as `theoretical` — climb it with §4 as
usual. `PROVEN[L-1]` passes the claim gate only once that finding is
proven-live (a lead claim dies with its finding). Other lifecycle moves:
`hunt lead park --retrigger "observable :: check"`, `hunt lead reopen --evidence ...`,
`hunt lead kill` (both halves refuted).

## 4.6 Fuzz the hot endpoints, record surfaces, chain the story

Before writing the report: fire the standard edge-case battery at the hot
parameters (every probe is logged as a redacted `fuzz_probe` event; flinches
print `!!` lines and become leads), record the surfaces you probed, then chain
your findings and check the claim is actually new:

```bash
hunt fuzz --url http://127.0.0.1:8765/transfer --method POST --param amount --param from --target-id 1
hunt surface add 1 endpoint "/transfer (POST)" && hunt surface add 1 trust_boundary "role cookie"
hunt coverage 1                                                    # blind spots = not yet probed
hunt chain add 1 "cookie to admin" --entry "client-asserted role cookie" --impact "full admin takeover"
hunt chain link 1 1 lead 1 && hunt chain novelty 1
```

Anomalies suggest `hunt lead add ...` — the engine proposes, the loop proves.

## 5. Report, fingerprint, claim gate

```bash
hunt phase 1 report
hunt report 1 --out REPORT.md
hunt verify-report REPORT.md                                                # report matches its fingerprint
GATE=$(python -c "import huntos,pathlib;print(pathlib.Path(huntos.__file__).parent/'_data'/'bin'/'claim_gate.py')")
echo "PROVEN F-1: drained the vault live" | python "$GATE"  # exit 0: backed by the db
echo "PROVEN F-9: we own the contract" | python "$GATE"     # exit 2: no such row
```

The gate is the engine's mouth guard: any `PROVEN` / `EXPLOITABLE` /
`admin takeover` claim without a proven-live row behind it fails the turn.

## 6. Bind the workspace

```bash
hunt project bind          # writes .huntos-project here, pinning this db's db_id
```

Every `hunt` command — and the claim gate — now verifies `HUNT_DB` against
that lock: a fabricated or swapped db (even one with a planted proven-live
row) cannot pass a claim here. A deliberate switch is a rebind, and it is
logged.

## 7. Wire the engine

The engine drives the same CLI, its mouth guarded by the gate. The shipped
hook pack — installed as `hunt-os/hooks/` by `hunt install` — is the primary
wiring: `app/src/huntos/_data/hooks/README.md` shows how to attach the
wrapper as the post-output/stop hook (stdin in, exit-code blocking policy
out, `HUNT_PROJECT_DIR`/`HUNT_DB` contract). Manual and audit-mode wiring
stay available: `app/src/huntos/_data/bin/README.md`. The engine's skill —
the db is the only ledger, every record through the hunt CLI:
`app/src/huntos/_data/idea/HUNT-BRIDGE.md`. Full run book:
`app/WALKTHROUGH.md`.

## 8. Load the skills into your harness

The bootstrap in §1 installs the CLI; it does not copy skills into a harness.
A harness without idea-injection needs the skills layer copied into its native
skill directory. That is the separate job of `hunt install` (which delegates to
the in-package `huntos.installer` module; running `python -m huntos.installer`
directly works identically — same flags, same exit codes). Default is router
mode: one native skill
`hunt-os` (THE ONE RULE + the skills index + the bridge, with the full corpus
nested for on-demand reads), plus the seven lane roles at `hunt-os/roles/`, the hook pack at
`hunt-os/hooks/`, and a manifest for drift checks and clean uninstall:

```bash
hunt install --adapter claude-code                  # .claude/skills (project scope, router mode)
hunt install --adapter zcode                        # .zcode/skills
hunt install --adapter generic --dir /path/to/skills # any harness: you name the directory
hunt install --adapter claude-code --check          # verify no drift vs the manifest
hunt install --adapter claude-code --uninstall      # remove exactly the manifest files
```

`hunt install --help` is the operator-facing reference (it needs no hunt db
and never creates one). Hermes needs none of this — it loads
`app/src/huntos/_data/idea/` and `_data/roles/` directly.
The installer is additive by law: it refuses to overwrite files it did not
install unless you pass `--force`. **P5 honesty:** the install is permanent
and namespaced — it stays until `--uninstall`. It is not session-scoped:
keeping operator identity between hunts is your discipline, not an installer
feature. Roles travel with the layer (law 5): an engine with only the
installed tree reads `hunt-os/roles/lane-runner.md` and the other roles
without the source tree — the router SKILL.md says exactly that.

## 9. Serial control room: mock and conforming adapters

The conductor is **not required to hunt** — everything in §1–§8 works through
the CLI and skills layer. Managed mode runs exactly four serial lanes and calls
an adapter as a judgment service; the conductor owns lane order, bounded
rounds, mediated tools, claim-gate vetoes, and failure policy.

The deterministic mock invokes no LLM, external agent, or harness. Its page is
a simulation, not evidence:

```bash
hunt doctor
hunt doctor --adapter mock
hunt run start --target 1 --rounds 1 --page
hunt run status --page
```

Every mock page is labelled `SIMULATED — no external agents invoked`.

To use a real harness, register an absolute executable that implements and
passes `HUNT-ADAPTER/1`:

```bash
hunt adapter add my-harness --exec /absolute/path/to/adapter --arg value
hunt adapter doctor my-harness
hunt adapter list
hunt run start --target 1 --rounds 1 --adapter my-harness --page
```

PowerShell uses the same syntax, with a Windows absolute path:

```powershell
hunt adapter add my-harness --exec C:\Tools\hunt-adapter.exe --arg value
hunt adapter doctor my-harness
```

Registration stores executable argv only, never credentials or environment.
HUNT-OS never loads an adapter from the target tree and never silently falls
back to mock. Installing Claude Code or ZCode skills does not make either one
a managed adapter; any harness is managed only after its conforming executable
passes the protocol doctor.

The mock loop normally ends `completed`, a terminal state; use pause, retry, or
reconcile only when status reports an active or failed attempt. Read attempt and
session ids from `hunt run status`, never guess them. Infrastructure failure and
adapter prose remain operational records, never research evidence. `hunt
doctor` names missing db, lock, gate, skill, and hook failures and exits 2.

## 10. Interactive console

After the CLI install in §1, enter the same CLI door as an interactive
console:

```text
$ hunt shell
hunt> macros
hunt> target list
hunt> n
hunt> firstblood
hunt> quit
```

`macros` lists the built-in workflows; `n` is the short alias for `next`
(`b` and `s` alias `brief` and `status`). `firstblood` is a macro; bare `wave`
and `report` start their guided macros, while arguments such as `wave open ...`
or `report 1 --out REPORT.md` run the ordinary CLI verb. Every real command
still goes back through the normal parser, database connection, and workspace
gates. Use `--no-hint` to suppress the `hunt next` hint after
successful writes, or `--quiet` to hide the startup banner.

Script mode uses one command per line and ignores lines beginning with `#`.
Create a small replay file using either shell's normal text-file facilities;
for example, `session.hsh` should contain exactly these three lines:

```text
# Read-only operator replay
status
next --target 1
```

Then replay it through the same shim:

```bash
hunt shell --script session.hsh
```

Replay is fail-closed: it stops at the first command returning nonzero, and the
shell exits 0 only when every command in the file succeeds.
