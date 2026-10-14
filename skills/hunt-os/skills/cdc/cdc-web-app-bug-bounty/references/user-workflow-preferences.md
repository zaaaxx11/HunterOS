# User Pace & Workflow Preferences — <REDACTED-OPERATOR-ALIAS>

## Speed Preferences
- **"lama bener"** = frustrated with slow pace, wants immediate action
- **"gas aja"** = just do it, don't explain what you're about to do
- **"satu per satu"** = sequential agent execution, not parallel
- **"jelasin santai"** = casual Indonesian, aku/kamu, no formal language

## Workflow Pattern
1. Spawn agents ONE AT A TIME when user requests sequential
2. Monitor live transcript, detect if agent is stuck >2min → re-do manually
3. Report results immediately, don't wait for all agents to finish
4. Use casual Indonesian for explanations, technical terse for findings

## Agent Failure Recovery
- If agent output is corrupted/gibberish → re-do manually with same goal
- Don't retry the same failed approach → switch to direct terminal execution
- Detect stuck agents early via transcript monitoring

## Communication Style
- Don't explain what you're going to do — just do it
- Report findings as they come, not in a batch at the end
- Use emojis for status (✅ ❌ 🔥 💀)
- Technical output: file:line references, not prose
- "lanjut" / "lanjut aja" = keep going, don't stop to summarize, just execute next step
- User gets frustrated by pauses for explanations — prefer continuous execution