# HUNT-OS Report: PracticeVault
- url: http://127.0.0.1:8765
- chain: evm | age: 0d | tvl: $0
- phase: archived | ev_score: 7.0

## Findings

### F-1 [CRITICAL] Admin panel takeover via client-asserted role cookie (forgeable in one header)
- class: Access | ladder: proven-live
- evidence: poc2_admin_secret_extraction.py vs live 127.0.0.1:8765: 403/200 differential from one header swap + protected asset extracted + repeat request stable
- poc: ../examples/practice_target/poc/poc2_admin_secret_extraction.py
- notes: GET /admin with Cookie: role=admin returns 200 + SECRET panel; role=ADMIN gets 403 (exact match, trivially known); no session or signature involved - lane: Red-Teamer

### F-2 [CRITICAL] Unauthenticated /transfer mutates shared balances; no sufficient-balance check allows unbounded overdraw
- class: Access | ladder: proven-live
- evidence: poc2_transfer_overdraw.py vs live 127.0.0.1:8765: single unauth request transferred 1000000000 from vault, vault balance driven negative (-1999000112) - no sufficient-balance check
- poc: ../examples/practice_target/poc/poc2_transfer_overdraw.py
- notes: bare POST from=vault&to=bob&amount=999999999 accepted with zero credentials; vault went to -999000099 - lane: Fuzz-Engineer

### F-3 [HIGH] C:/Program Files/Git/api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client
- class: Web2 | ladder: overturned
- OVERTURNED by: lane-runner: title corrupted by Git-Bash POSIX path conversion (leading-slash arg became C:/Program Files/Git/api/users); re-recorded as F-6
- notes: storage-to-output leak of credential material; md5 digests are dictionary-crackable - lane: Architect

### F-4 [HIGH] Failed /transfer destroys funds: debit executes before credit, crash on unknown destination leaves balance debited
- class: Logic | ladder: proven-live
- evidence: poc2_failed_transfer_drain_loop.py vs live 127.0.0.1:8765: 5 failed transfers burned 5000000 vault units (repeatable destruction loop)
- poc: ../examples/practice_target/poc/poc2_failed_transfer_drain_loop.py
- notes: invariant 'failed transfer leaves balances unchanged' violated; vault lost 100 units on a transfer that errored out; unknown source is harmless (KeyError before mutation) - lane: Red-Teamer

### F-5 [CRITICAL] Chain: /api/users recon -> forged admin cookie -> unauthenticated transfer = unauth to admin+theft in one script
- class: Access | ladder: proven-live
- evidence: poc2_chain_full_breach.py vs live 127.0.0.1:8765: full breach in one script - 3/3 credentials cracked, admin secret extracted, vault driven negative by 100000000 unauth transfer
- poc: ../examples/practice_target/poc/poc2_chain_full_breach.py
- notes: gadget handoff: leak yields account names, forged cookie yields admin panel (SECRET: internal transfer keys), transfer yields balance mutation; every step attacker-initiated, zero credentials - lane: Chainer

### F-6 [HIGH] /api/users dumps usernames and unsalted md5 password hashes to any unauthenticated client
- class: Web2 | ladder: proven-live
- evidence: poc2_users_hash_crack.py vs live 127.0.0.1:8765: 3/3 leaked md5 digests recovered via 5-word dictionary - hashes are working credentials, not decoys
- poc: ../examples/practice_target/poc/poc2_users_hash_crack.py
- notes: storage-to-output leak of credential material; md5 digests are dictionary-crackable - lane: Architect (re-record after shell mangling)

### F-7 [HIGH] Negative-amount transfer to unknown destination mints credits: source credited with no offsetting debit (repeatable ledger inflation)
- class: Arithmetic | ladder: proven-live
- evidence: poc2_ledger_control.py vs live 127.0.0.1:8765: minted 1,000,000,000 units onto alice via crashed negative transfers, then set vault from -2104000112 to exactly 500000 - arbitrary ledger write
- poc: ../examples/practice_target/poc/poc2_ledger_control.py
- notes: blind-spot round: naive self-transfer mint hypothesis DIED on probe (debit and credit cancel, no-op); real flaw is the combination - amount=-X flips the debit into a credit, then the unknown-destination KeyError crashes before any debit lands; alice gained 100 units from a request that returned no response

## Waves
- wave 1: lanes=architect-trustgraph,redteam-invariant,fuzz-boundary,chain-handoff new_findings=6 verdict=continue
- wave 2: lanes=blindspot-sign-edges,blindspot-idor,blindspot-concurrency,blindspot-methods new_findings=1 verdict=exhausted
<!-- hunt-report sha256:ca9970eb8979fe2c4bd84a93dee3ec1d5a5b190f1135772a67c15c5d84a6f8c7 target:1 db:888b9c57e901 generated:2026-09-05T18:40:16Z -->
