# Layer1 Batch Scan Results — 2026-08-14

## Summary
- 201 blockchain projects scanned from Layer1.xlsx
- Methodology: Quick fingerprint + admin path check + credential grep in homepage
- 5 exploit findings, 4 admin panels found, 192 clean

## Exploit Findings (CRITICAL)
| Project | Finding | Credentials |
|---------|---------|-------------|
| Naoris | Admin bypass + Firebase takeover + Stored XSS | pw: <redacted>, fb: contact@naorisconsulting.com / <redacted> |
| U2U | debug API file write + GC kill + mempool leak | debug_writeMemProfile, txpool_content |
| Theta | RPC admin methods + NoSQL dump | theta.BackupChain, $exists bypass |
| Helios | Docker RCE uid=0 + WASM RCE | Docker escape + Bridge sig NOOP |
| Qtum | NextAuth draft leak + AI stack unauth | CMS draft, unauthenticated AI endpoints |

## Admin Panel Found (PENDING DEEP AUDIT)
| Project | Admin Path | CMS | Deep Audit Result |
|---------|-----------|-----|-------------------|
| Filecoin | /admin | TinaCMS | Protected (OAuth), no bypass |
| Flare | /admin/login | Payload CMS | Data leak (11 collections), no RCE |
| Turingbitchain | /admin | SPA | No admin, all paths SPA |
| Dymension | /admin | Firebase Storage | Airdrop leak (5K addresses, 2.4M tokens) |

## Key Patterns Discovered
- Payload CMS: x-powered-by header, /api/access schema leak, /api/users/login
- TinaCMS: Vite SPA at /admin, clientId in JS bundle
- Firebase Storage: Public bucket listing via /o?maxResults
- React SPA: All paths return 200, need Content-Type check