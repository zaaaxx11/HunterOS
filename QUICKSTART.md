# HunterOS Plugins Quick Start

## Install as skills/tools plugin

```bash
git clone https://github.com/zaaaxx11/hunteros-plugins.git ~/.hunteros-plugins
```

## Use with your agent harness

**Claude Code:**
```
/plugin marketplace add zaaaxx11/hunteros-plugins
/plugin install hunt-os@hunter-os
```

**Hermes Agent:**
```bash
ln -s ~/.hunteros-plugins/skills ~/.hermes/profiles/default/skills/hunter
```

**OpenCode/Codex:**
```bash
cp -r ~/.hunteros-plugins/skills ~/your-project/ai_skills/
```

## Load a skill

Tell your agent:
```
load the hunter-harness-core skill
load the hunter-loop skill
```

Each skill is self-contained markdown. Load only what the lane needs.

## Full harness (optional)

```bash
pip install git+https://github.com/zaaaxx11/HunterOsHarness.git
hunter loop /path/to/target --time 6h --goals rce-min:1,findings-min:500 --yes
```
