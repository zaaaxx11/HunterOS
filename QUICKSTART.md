# HunterOS Plugins Quick Start

## Native Claude Code Install (Recommended)

```bash
git clone https://github.com/zaaaxx11/hunteros-plugins.git ~/.hunteros-plugins

# Install skills — copy to user-level Claude Code directory
mkdir -p ~/.claude/skills ~/.claude/agents
cp -r ~/.hunteros-plugins/.claude/skills/* ~/.claude/skills/
cp -r ~/.hunteros-plugins/.claude/agents/* ~/.claude/agents/
```

Restart Claude Code and the skills are available.

## Load a skill

Tell Claude Code:
```
load hunt-recon-predator-recon
load hunt-web2-web2-attack-surface-audit
load hunt-web3-black-swan-engine
```

Or load the router first:
```
load hunt-os
```
to see the full 51-skill index and pick your target category.

## Agent Lanes

7 pre-built agents available via the Agent tool:

| Agent | Role |
|-------|------|
| `hunt-architect` | Attack-surface mapping |
| `hunt-red-teamer` | Auth/authz testing, injection |
| `hunt-fuzz-engineer` | Edge cases, constraints |
| `hunt-chainer` | Exploit chain construction |
| `hunt-verifier` | Evidence checking |
| `hunt-adversary` | Adversarial review |
| `hunt-lane-runner` | Lane dispatcher |

## Plugin Install (Legacy)

```
/plugin marketplace add zaaaxx11/hunteros-plugins
/plugin install hunt-os@hunter-os
```

## Hermes Agent

```bash
ln -s ~/.hunteros-plugins/skills ~/.hermes/profiles/default/skills/hunter
```

## OpenCode/Codex

```bash
cp -r ~/.hunteros-plugins/skills ~/your-project/ai_skills/
```