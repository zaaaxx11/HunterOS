# Skills Landing A — Categories 01 (recon), 02 (web2), 06 (osint)

Source: `hunteros_temp/the operator_Skills_Master` zips 01/02/06, extracted to the
system temp dir (`/tmp/the operator-land`), normalized and landed into
`soul/skills/{recon,web2,osint}` on branch `land-a`. Nothing committed.

**Totals: 35 skills landed, 0 skipped, 102 secret redactions (see
`recon-web2-osint-hygiene.md`).**

## soul/skills/recon — category 01 (4 skills)

| Skill | Notes |
|---|---|
| predator-recon | Biggest skill: SKILL.md + unified CLI script (`predator-recon`, bash, text — kept), 5 phase scripts, payloads, config.yaml.example/templates, 17+ reference docs incl. case studies (mergify, t3tris, paxos, salesforce). Frontmatter already canonical. |
| web2-spa-recon | SKILL.md + 32 case references (Colb, Nuxaris, BC Swap, Alltoscan, Bityuan, VersatizeCoin, AIOZ…). Helius RPC key redacted 12x across SKILL.md + references. |
| web2-admin-takeover | SKILL.md + 3 references (bcswap, versatizecoin) + web2-hunt.sh script; banner de-branded. |
| cloudflare-waf-graphql-recon | Single SKILL.md, no changes needed. |

## soul/skills/web2 — category 02 (23 skills)

adversarial-bug-bounty-hunting, adversarial-exploit-chains,
adversarial-persona-operations, bug-bounty-agent, business-logic-invariant-hunt,
disk-space-session-safety, epixnet-ui-redteam, frontend-security-audit,
github-secret-hunt, human-intelligence-osint, js-secret-scanner,
mcp-security-audit, nextauth-authz-probe, nextauth5-detection,
nextjs-authn-authz-probing, saas-supply-chain-exploitation,
spa-live-backend-discovery, wallet-auth-bypass-audit, web-blocked-page-recovery,
web2-admin-cdc, web2-admin-hunt, web2-api-security-patterns,
web2-attack-surface-audit.

- Heavy reference payloads (adversarial-bug-bounty-hunting ~69 refs,
  bug-bounty-agent ~44 refs, web2-attack-surface-audit ~29 refs). All landed as
  text assets alongside their SKILL.md.
- Naoris/Naox Firebase takeover credentials (2 passwords + Firebase API key,
  ~38 occurrences) redacted in this category — the single largest secret cluster.
- adversarial-persona-operations: persona-branded skill; "the operator" replaced with
  "the operator" throughout SKILL.md + 3 references. Katalog name mismatch:
  zip folder is `adversarial-exploit-chains`, Katalog says
  `adversarial-exploit-chainers`; landed under the folder's functional name.
  Katalog's `nextauth-email-enum` does not exist in the zip (23 folders listed
  above are what shipped); its content appears folded into
  `nextauth-authz-probe` / `business-logic-invariant-hunt` references.
- Katalog mentions "web/blocked-page-recovery"; see conversion note below.

## soul/skills/osint — category 06 (8 skills)

cloud-instance-hardening, github-secret-hunt, headless-shell-access,
hermes-config-management, infrastructure-osint, session-hygiene, vps-audit,
vps-cleanup.

- github-secret-hunt is byte-identical in categories 02 and 06; landed in both
  destinations per the landing map (intentional duplication).
- hermes-config-management: the zip ships a full LIVE `config.yaml` dump
  (`references/config_fixed.yaml`) plus incident notes with 10+ real provider
  API keys — 22 redactions here, the densest hygiene pass. Note: KATALOG
  lists hermes-config-management under category 08, but it shipped inside the
  06 zip, so it landed in osint per the zip's contents.
- headless-shell-access and session-hygiene are operator-workflow/hygiene
  skills (Hermes-agent flavored) rather than hunting skills; they were usable
  skills with real content, so they were landed rather than skipped.

## Format conversions

- `web-blocked-page-recovery` was double-wrapped in the zip: outer folder held
  only `DESCRIPTION.md` + inner `blocked-page-recovery/` folder. Flattened to
  `web-blocked-page-recovery/SKILL.md` + `scripts/recover_page.py`;
  redundant outer `DESCRIPTION.md` dropped (its one-liner already exists in the
  SKILL.md frontmatter).
- All 35 SKILL.md files already carried `---` frontmatter with `name` +
  `description`; no frontmatter synthesis was needed.
- No binaries, images, or executables found anywhere in the three zips;
  nothing dropped for being binary. Largest asset < 100 KB.
- All landed names are functional (`predator-recon`, `nextauth-authz-probe`, …);
  no the operator branding in any landed file or folder name.

## Surprises

1. `hermes-config-management` shipped a live config dump with ~10 working
   provider API keys as "reference material" — worst secret exposure in the set.
2. `github-secret-hunt` (both copies) embedded a verbatim user-provided GitHub
   PAT in the InjectiveLabs case study header.
3. The Naoris case files reused the *actual* harvested target credentials
   (admin password, Firebase account password, Firebase web API key) in
   copy-paste PoC curl commands — all redacted, methodology kept.
3. The operator's own Helius RPC key was pasted into 9+ case files as a URL
   parameter — redacted everywhere including 4-char truncated remnants.
4. Duplicate skill: `github-secret-hunt` exists identically in both zips 02 and 06.
5. KATALOG drift: `adversarial-exploit-chainers` vs zip's
   `adversarial-exploit-chains`; `nextauth-email-enum` missing from the zip;
   `hermes-config-management` filed under 08 in KATALOG but shipped in 06.

## Verification

- `find soul/skills -name SKILL.md` → 35 files, all with frontmatter `name:`/`description`.
- `grep -ri the operator soul/skills` → 0 hits.
- Secret-pattern grep (ghp_/gho_/github_pat_, AKIA×16, eyJ.x.eyJ JWTs, sk-*,
  AIza, BEGIN PRIVATE KEY, password/token/api_key with >=12-char values,
  user:pass@host, session cookies) over `soul/skills` → only intentional
  `<REDACTED-*>` placeholders and scanner-fingerprint strings documented in the
  hygiene log.
