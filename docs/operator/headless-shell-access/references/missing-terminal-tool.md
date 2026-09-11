# Missing Terminal Tool in Headless Container

## The Symptom

The system prompt / tool registry declares a `terminal` tool (with `backend: singularity`) but the actual tool set only contains:

```
computer_use, process, session_search, skill_manage, skill_view, skills_list, text_to_speech, todo, vision_analyze
```

No `terminal` tool. This means the agent cannot execute shell commands, even though the system prompt suggests a `singularity` backend is available.

## Why This Happens

The `terminal` tool is a first-class Hermes tool that requires the `terminal` toolset to be enabled. In headless/Singularity container environments, the toolset may be missing from the tool registry for several reasons:

1. **Toolset disabled** — `terminal` toolset not in the platform's toolset config
2. **Backend not configured** — Singularity requires `singularity` binary on PATH; if missing, the tool is disabled automatically
3. **Permission issues** — Container may lack the necessary cgroup/device permissions for Singularity
4. **Platform provisioning** — The environment may have been provisioned without the terminal toolset

## Also: `execute_code` Requires Singularity Too

The `execute_code` tool (Python sandbox) ALSO fails in the same environment with:

```
RuntimeError: Neither 'apptainer' nor 'singularity' was found in PATH.
```

This is NOT a Python error — it's the same container backend dependency. So when `terminal` is missing, `execute_code` is almost certainly also broken. Both tools share the same singularity backend requirement.

## Also: `delegate_task` Inherits the Limitation

A delegated subagent inherits the same tool set. If you delegate a task that needs shell execution or Python code, the subagent will hit the same singularity error.

## How to Detect Early

After loading any skill, immediately verify critical tools are present:

```
# Check available tools by attempting a no-op
process(action='list')  # If this works but session_id is always required, terminal is missing
```

Or simply check your tool set at the start of any session — if `terminal` isn't in your available tools and the task requires shell execution, switch to `headless-shell-access` immediately rather than wasting turns on `computer_use` workarounds.

## Diagnostic Order (for this specific issue)

1. `process(action='list')` → empty or no sessions → need `terminal` tool
2. `computer_use(action='capture', app='screen')` → 0x0 → no display
3. No `terminal` tool in tool set → confirmed headless blocker
4. **Stop. Report. Suggest alternatives.**

## Common Fix Commands

```bash
# Enable terminal toolset in Hermes config
hermes config set tools.terminal.enabled true

# Install Singularity if missing
apt-get install -y singularity-container
# or for RPM:
yum install -y singularity-ce

# Check current toolset
hermes tools list
hermes config check
```

## Related

- See `repro-headless-blocker.md` for the original ZIP extraction reproduction case
- See `headless-shell-access/SKILL.md` for the full diagnostic checklist