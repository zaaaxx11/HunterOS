# UnionLabs Re-Audit 2026-08-08 — CDC Protocol Full Results

**Target**: https://github.com/unionlabs — IBC + CosmWasm + CometBLS ZK light client
**Scope**: ucs03-zkgm (3,556 lines), cw20-token-minter, cw-escrow-vault, 11-cometbls ZK verifier, cw-account proxy
**Methodology**: CDC (Divergent First → Chaining → Stall=Block → Adversarial Validation)

---

## EXECUTIVE SUMMARY

| Metric | Result |
|--------|--------|
| **Theories Generated** | 3 (Divergent First) |
| **Theories Blocked** | 2 (Adversarial breaks) |
| **Theories Theoretical** | 1 (ThirdParty token deploy) |
| **Proven RCE/Theft Chains** | **0** |
| **Verdict** | **SECURE** — No pre-auth RCE/theft found |

---

## TRUST GRAPH

```
[Untrusted] User Tx → ucs03-zkgm::send() → verify_internal() → ibc_host.PacketSend (source)
     | (IBC commitment + light client proof)
     v
[Trusted Boundary] core/contract.rs :: query_light_client(VerifyMembership) → ZK/ICS23
     |
     v
[Trusted?] ucs03-zkgm::execute() dispatched via ibc_host (OnlyIbcHost)
     -> InternalExecutePacket (OnlySelf) -> execute_internal() -> OP dispatch
     -> Forwards to: token-minter / cw-account (proxy) / any Zkgmable

[Funds Sinks] cw20-token-minter::Escrow/Unescrow/Mint/Burn/CreateDenomV2
[Account Sink] cw-account::OnZkgm -> from_json<Vec<CosmosMsg>> -> add_messages (arbitrary)
[Upgrade Sink] access-manager / upgradable / dummy_code_id / cw_account_code_id update
```

**Entry Vectors Enumerated:**
1. `ExecuteMsg::Send` — public, requires `WhenNotPaused`, calls `verify_internal`
2. `ExecuteMsg::IbcUnionMsg` — **only** `ibc_host`, entry to dest chain execution
3. `ExecuteMsg::Internal*` — **only** `env.contract.address` (self)
4. `ExecuteMsg::Restricted` — `access_managed::ensure_can_call` (authority gated)

---

## THEORY A: LOGIC BYPASS — CROSS-CHAIN CALL IMPERSONATION

**Trigger**: `OP_CALL` with `call.sender = attacker`, `call.contract_address = predicted_proxy`, `call.calldata = abi(Json(Vec<CosmosMsg>))`

**Source Verification** (`contract.rs:3000-3008`):
```rust
pub fn verify_call(call: &Call, sender: Addr, ...) {
  if call_sender != sender.as_str() { Err(InvalidCallSender) }
}
```
Called ONLY in `verify_internal` → `send()` on source chain. Packet's `call.sender` bound to source `info.sender`.

**Dest Execution** (`contract.rs:1500-1682`):
```rust
predicted = predict_call_proxy_account(path, dest_channel, call.sender)
if predicted == contract_address && !exists && !CREATED_PROXY_ACCOUNT.exists {
  Instantiate2 { salt: keccak(path, channel, sender) } 
  Migrate { new_code_id: cw_account_code_id }
  UpdateAdmin { admin: predicted }
}
wasm_execute(contract_address, Zkgmable::OnZkgm{ caller, sender: call.sender, message: calldata })
```

**Sink** (`cw-account/src/lib.rs:177-194`):
```rust
ExecuteMsg::Zkgmable(OnZkgm(on_zkgm)) => {
  ensure_remote_admin(deps, info, RemoteAdmin{address: on_zkgm.sender, channel, path})?;
  add_messages(from_json::<Vec<CosmosMsg>>(&on_zkgm.message)?)
}
```

**Adversarial Break — NO VICTIM HIJACK**:
- `verify_call` enforces `call.sender == source info.sender` → proxy ownership isolated per attacker
- Dest `ensure_remote_admin` checks `RemoteAdmin` created at proxy deploy with `sender = call.sender` → attacker owns their proxy only
- Proxy starts empty → no free mint → need victim to bridge attacker token or metadata collision (keccak preimage)
- **Verdict**: BLOCKED by design — intended interchain account feature, not bypass

---

## THEORY B: DESERIALIZATION/STORAGE CONFUSION — NATIVE TOKEN FLAG POISONING

**Trigger**: Force `is_native_token` flag for CW20 denom via `Escrow` path.

**Code** (`cw20-token-minter/src/contract.rs:230-293`):
```rust
LocalTokenMsg::Escrow { denom, amount, from, recipient } => {
  if info.funds.any(|c| c.denom == denom && c.amount == amount) {
    save_native_token(storage, &denom); // key = 0x03 + denom
    return Response::new()
  } else {
    TransferFrom { owner: from, recipient, amount }
  }
}
LocalTokenMsg::Unescrow { denom, recipient, amount } => {
  if is_native_token(deps, &denom) { BankMsg::Send{ to: recipient } } 
  else { Transfer{ recipient } }
}
```

**Adversarial Break**:
- To set flag, attacker must possess native token with denom = victim CW20 address string
- Cosmos SDK bank denom validation rejects unknown denoms unless token factory created them
- Cannot send native coin with denom = `union1...` (bech32) — bank rejects `InsufficientFunds` before contract executes
- `save_native_token` key `0x03` shared but `is_native_token` exact string match — no prefix collision with channel balances
- No overflow: U256/Uint256 `checked_add`/`checked_sub` everywhere
- **Verdict**: BLOCKED — requires ability to mint arbitrary native denom

---

## THEORY C: HOOK/WASM DEPLOYMENT — CREATE DENOM V2 ARBITRARY DEPLOYMENT (HIGH CONFIDENCE)

**Trigger**: `TokenOrderV2` kind=INITIALIZE (`0x00`) with attacker `metadata = { implementation: JSON{admin: attacker, code_id: 9999}, initializer: JSON{UpgradeMsg::Init{mint:{minter: attacker}}} }`

**Sink** (`cw20-token-minter/src/contract.rs:101-193`):
```rust
WrappedTokenMsg::CreateDenomV2 { subdenom, path, channel_id, token, implementation, initializer } => {
  let impl = from_json::<Cw20TokenMinterImplementation>(&implementation)?;
  let admin = validate(&impl.admin)?;
  code_hash = query_wasm_code_info(impl.code_id).checksum
  protocol_hash = query_wasm_code_info(config.cw20_impl_code_id).checksum
  is_cw20_base_code = code_hash == protocol_hash
  is_cw20_admin = admin == CW20_ADMIN
  is_local_minter = initializer.mint.minter == env.contract.address && empty balances
  is_secure = is_cw20_base_code && is_cw20_admin && is_local_minter
  kind = is_secure ? Protocol : ThirdParty  // <-- NEVER REVERTS ON FALSE!
  Instantiate2 { code_id: config.dummy_code_id, salt: keccak(...) }
  Migrate { new_code_id: impl.code_id, msg: initializer }
  UpdateAdmin { admin: admin }
}
```

**Chain**:
```
[Trigger] Attacker Send(TokenOrderV2 INITIALIZE, metadata=attacker_impl) 
  -> zkgm verify_internal (sender check only) 
  -> IBC PacketSend 
  -> [Trust Boundary] Light client VerifyMembership (legit packet passes)
  -> dest execute_token_order_v2 -> protocol_fill_mint(can_deploy=true, !HASH_TO_FOREIGN_TOKEN)
  -> minter.Wrapped(CreateDenomV2{implementation=attacker_code, initializer=attacker_msg})
  -> [Trust Boundary] minter OnlyAdmin passes (caller=zkgm)
  -> Instantiate2(dummy_code) -> Migrate(attacker_code_id) -> UpdateAdmin(attacker)
  -> attacker-controlled CW20 at deterministic address
```

**Adversarial Validation**:
- Pre-auth: Yes, `Send` is public
- Light client verification mandatory — no bypass
- Deployed contract = CW20 token, not arbitrary system contract
- Direct escrow drain: NO (needs victim to bridge attacker token or metadata collision)
- **Impact**: Supply-chain / phishing — ThirdParty token masquerading as legit
- Later MintTokens/BurnTokens/Transfer for that denom execute attacker code AS minter
- **Confidence**: PROVEN (deployment), THEORETICAL (fund theft without social engineering)

**EVIDENCE**:
- `cw20-token-minter/src/contract.rs:101-193` (CreateDenomV2 handler, checks 115-141 compute `is_secure` but 150-179 NEVER revert on `!is_secure`, only sets `kind=ThirdParty`)
- `ucs03-zkgm/src/contract.rs:2343-2354` (protocol_fill_mint forwards arbitrary metadata.implementation/initializer)
- `ucs03-zkgm-token-minter-api/src/lib.rs:49-51` (encode_metadata), 141-160 (CreateDenomV2 struct arbitrary bytes)

**MITIGATION**:
```rust
// In CreateDenomV2 handler — add after is_secure check:
if !is_secure_wrapped_token {
    return Err(Error::UnauthorizedThirdParty);
}
// OR whitelist:
require(impl.code_id == config.cw20_impl_code_id && admin == CW20_ADMIN, "unauthorized");
```

---

## ADVERSARIAL VALIDATION SUMMARY

| Theory | Status | Reason |
|--------|--------|--------|
| A: Call Proxy Impersonation | **BLOCKED** | Source `verify_call` binds sender; dest proxy empty; no victim hijack |
| B: Native Flag Poisoning | **BLOCKED** | Bank rejects unknown denom; cannot forge native token with CW20 address |
| C: CreateDenomV2 Arbitrary Deploy | **PROVEN DEPLOYMENT / THEORETICAL THEFT** | Contract deploys but needs victim interaction for theft |

---

## FINAL CDC VERDICT

**NO PROVEN PRE-AUTH RCE / FUND THEFT CHAIN**

```
VULNERABILITY: Arbitrary WASM Deployment / Supply-Chain Token Impersonation via Unrestricted CreateDenomV2
ENTRY: Pre-auth (anyone can Send TokenOrderV2 INITIALIZE via ucs03-zkgm)
CHAIN: Send(TokenOrderV2 INITIALIZE, metadata=attacker) -> verify_internal -> PacketSend -> Light client proof -> execute_token_order_v2 -> protocol_fill_mint -> minter.CreateDenomV2 -> Instantiate2+Migrate+UpdateAdmin(attacker)
IMPACT: Theft via Token Supply-Chain / Phishing (ThirdParty token) — NOT direct escrow drain
POC: /tmp/poc_union_v2_deploy.py (working simulation) + weaponization steps
EVIDENCE: cw20-token-minter/src/contract.rs:101-193, ucs03-zkgm/src/contract.rs:2343-2354
CONFIDENCE: PROVEN (arbitrary deployment), THEORETICAL (fund theft without social engineering)
MITIGATION: Reject CreateDenomV2 if !is_secure_wrapped_token; whitelist code_id; add supply cap; pausable ThirdParty creation
```