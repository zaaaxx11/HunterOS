# Target Worth Matrix (FT vs SaaS) (cut from rate-limited-chain-recon SKILL.md 2026-09-07)

Cut verbatim from `soul/skills/web3/rate-limited-chain-recon/SKILL.md` during the S2b-2 content pass. The Sonic-FT / Gimo / Naoris case refs live in `examples/hunts/web3/rate-limited-chain-recon/references/`.

---

## Target Worth Matrix (FT vs SaaS)

From 2026-08-09 pivot debate (FT/Sonic not worth 6h vs Everlyn SaaS worth 6h):
| Criterion for pre-auth RCE | FT (token) | Everlyn (SaaS) |
|---|---|---|
| Input crosses admin boundary without auth | ❌ LayerZero OnlyPeer/OnlyEndpoint solid | ✅ `x-middleware-subrequest` bypass |
| Deserialization / delegatecall / eval | ❌ no delegatecall | ✅ `pickle.load(cache)` |
| Complex private state with holder mesh | Thin wrapper (2 contracts) | ✅ 247 epochs, vault mesh, Safe chain |
| Supply chain (engineer runs your payload) | ❌ | ✅ ANTRP chair.py |
| **Verdict** | Max **DoS 14k bricked** (`keepers=false`) | **READ→WRITE chain + RCE root** worth 6h |

Use this to answer **"sampai mana?" / "sebenarnya kurang apa sih?"** — give honest coverage % (98% supply, 32 scan chunks done) and pivot recommendation, not false progress.
