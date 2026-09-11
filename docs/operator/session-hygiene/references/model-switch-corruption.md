# Model-Switch Output Corruption Pattern

## Recognition

After repeated model switches (3+ provider changes via xkiro/hcnsec within a single session):

**Symptoms:**
- Output becomes **looped, hyper-verbose, non-executing** — 30+ paragraphs of meta-narration with zero tool calls
- Text devolves into repeated fragments: "whichever whichever whichever...", "Rp Rp Rp...", Catalan/Spanish injection, or unchecked recursion
- Model re-states its `[Note: model was just switched...]` identity mid-response
- Produces **raw code dumps** (10K-50K chars of entry.js, grep output, etc.) instead of synthesized analysis
- In worst case: **Catalan language injection** or random byte dumps appear mid-response
- User frustration signals: "cokkk, output mu coba lihat, kenapa itu?" / "coba lihat output lo, aneh" = corruption, not agent incompetence

## Root Cause

When the xkiro/router switches the backend model provider, the new model inherits garbled context tokens from the old model's prefill state. The turn count keeps incrementing but the context window's internal state becomes maligned — tokens that should be instruction tokens are treated as output continuation, breaking the assistant's generation loop.

## Fix / Recovery

1. **DO NOT** defend or diagnose mid-stream. You already produced garbage — the user sees it.
2. Immediately acknowledge the corruption and state the root cause in ONE sentence.
3. Do a hard reset into clean execution mode: stop all narration, re-identify with the user's preferred tone, and deliver a 2-line summary of status.
4. Produce actual tool calls next — execution over explanation.

## Prevention

- User requirement: **stay on 1 model during audits — no auto-switch** (from Tare audit session)
- If a model switch is suggested by gateway/router, ASK the user before proceeding
- After a switch does occur, be aware that the first few turns may be corrupted — verify output coherence early