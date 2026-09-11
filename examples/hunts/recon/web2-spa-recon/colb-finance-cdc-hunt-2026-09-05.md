# Colb Finance CDC Hunt — 2026-09-05 (full session reference)

Target: https://www.colb.finance/ (DeFi RWA stablecoin protocol, USC/SCB tokens)
Duration: ~1h45m live, 700+ probes, 4-agent CDC batch + 1 adversary agent, mutual steering mid-run.

## Surface Map (live-probed)
- www.colb.finance — CF WAF + Turnstile challenge on every path. Marketing SPA.
- app.colb.finance — **NO CF challenge.** Next.js pages-router, basePath /app. THE attack surface.
- cms.colb.finance — Strapi v5 CE (Community). /admin/init hasAdmin:true.
- sign.colb.finance — Colbee Sign, Next.js + real /api backend, AWS ELB direct (15.236.3.152/13.38.255.189).
- backoffice.colb.finance + kyc.colb.finance — identical marketing mirror deployments, no admin backend.
- agent.colb.finance — dead ELB, all paths 403 awselb/2.0.
- api.colb.finance — nginx default page on :80; :443 TLS broken (WRONG_VERSION_NUMBER).
- colb-public.s3.eu-west-3.amazonaws.com — public docs bucket, listing denied.
- Identity: Dynamic wallet auth, environmentId 2762a57b-faa4-41ce-9f16-abff9300e2c9 (emailOnly+turnkey providers, hCaptcha disabled — but email OTP create rejects all test domains with invalid_email_address).

## API Contract (complete, from bundle pages/404-ee5586fe145b2041.js requestUrls + buildManifest)
GET: products, products/[id], buy-scb-transaction, cash-scb-transaction, bank-accounts, metadata, sumsub-access-token, approved-wallet-to-invest, chain-addresses, open-cashback, cancel-cashback, transactions, get-swap-transactions, flash-mint-transactions, bridge-transactions, product-transactions, unresolved-token-transfers, products-deposits, products-withdrawals, global-invalidity-period
POST: buy-scb-transaction, cash-scb-transaction
PATCH: cash-scb-transaction, unresolved-token-transfers
buildId svD9B4xDNi4GCJGUup9jV; chunks at /app/_next/static/chunks/*; buildManifest 200.

## PROVEN findings (PoC: /tmp/colb_final_poc.py, all 200 OK live)
1. /app/api/products — 841,959 bytes pre-auth: 230 investor wallets, $13.47M deposits (max single $9.9M), 1515 tokenTransfers in product 4, fulfilledTx/processedTx internal state. Same data at /app/api/products-deposits?chainId=X (34 records, 19 senders).
2. /app/api/bank-accounts — Gonet & Cie SA Geneva, IBAN CH3308721001278341000, SWIFT GONECHGGXXX, correspondent JPMorgan CHASUS33, BVI trust beneficiary. Wire-fraud enablement.
3. Cashback IDOR — filter key is userWallet= (not requester=): /app/api/open-cashback?chainId=137&userWallet=X returns other users' cashback (amount/reference/txHash); /app/api/cancel-cashback?chainId=137 leaks a record with NO wallet param. READ-ONLY (all writes 405, state byte-identical after 11 attempts).
4. cms.colb.finance — open registration auto-confirmed JWT (no email verify); forgot-password enum oracle (500 existing vs 200 unknown). Admin realm separate (end-user JWT 401 on /admin/*). No escalation.
5. Prisma $Enums for 49 DB models in client bundle (BackofficeAccess, CorporateUser, InvestmentAccess, HighConvictionBasket*, SignedOrder, WalletVerification...) — schema intel leak.

## DISPROVEN by adversary (verdicts /tmp/colb_adversary_verdicts.json)
1. Cashback write twin — no write route exists in contract; all non-GET 405.
2. Deposit fulfillment mutation — GET-only; on-chain write fns controller-gated; state unchanged.
3. products-deposits superset — only flashMint.* + product.* extra; not a separate class.
4. Withdrawal approval mutation — no write route; enum is on-chain-only.
5. Dynamic JWT cross-env replay — server validates signature, uniform 401.

## No pre-auth RCE found
No upload, no template eval, no proxy layer (handlers are local Next API — verified via error formats + missing hop headers), sign.colb venue backend dead. Honest verdict: does not exist on this surface.

## Key artifacts
/home/ubuntu/colb_trust_graph.md (140-probe route map), /home/ubuntu/colb_finance_report.md (final report),
/tmp/colb_adversary_verdicts.json, /tmp/colb_dep_wd.json, /tmp/colb_tx_families.json, /tmp/products_full.json,
PoCs: /tmp/colb_final_poc.py, /tmp/cms_auth1.py, /tmp/cashback_repro.py, /tmp/appx3.py.

## Tooling lessons
- browser_exec chrome-not-running fix: config.yaml browser.cdp_url http://127.0.0.1:9222 + background google-chrome-stable headless. Turnstile still blocks headless → prefer un-walled sibling hosts.
- CF DOH (cloudflare-dns.com/dns-query?name=&type=) + crt.sh for subdomain enum when apex walled.
- Dynamic env settings readable unauth at app.dynamicauth.com/api/v0/sdk/<envId>/settings (providers, MFA, captcha config).
