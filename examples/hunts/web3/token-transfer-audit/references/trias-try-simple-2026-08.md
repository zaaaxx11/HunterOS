# TRYSimple.sol (Trias) — Token Transfer Case Study 2026-08

Source: `trias-lab/erc20/TRYSimple.sol` (sol 0.4.24, TRY token, SafeMath with safeSub/safeAdd only). Full audit: `/root/FUZZ_ENGINEER_TRIAS_REPORT.md`, live harness `/root/fuzz_harness.py`.

## SafeMath is correct but incomplete

- `safeSub(a,b): require(b<=a); c=a-b; return c` — prevents underflow (`safeSub(0,1)` reverts). Correct.
- `safeAdd(a,b): c=a+b; require(c>=a)` — wrap check prevents overflow (`safeAdd(max,1)` reverts). Correct.
- All `balances`/`allowance` updates via SafeMath; no raw `+/-` outside it — PASS.
- Missing `safeMul` — not used in current code, latent if fee logic added.
- Sol 0.4.24 outdated (2018); 0.8.x has built-in checks. No pause/blacklist; no external calls → no reentrancy in this contract.

## transfer() — zero-amount allowed (HIGH inconsistency)

```solidity
function transfer(address _to, uint256 _value) public returns (bool) {
    require(_to != 0x0);
    require(balances[msg.sender] >= _value);
    balances[msg.sender] = safeSub(balances[msg.sender], _value);
    balances[_to] = safeAdd(balances[_to], _value);
}
```

- `_value=0` → `require(balance>=0)` always true → executes, emits `Transfer` with 0 (log spam / indexer DoS). `transferFrom` has `require(_value>0)` — inconsistency. Fix: `require(_value>0)` in both.
- `_value=max` → reverts via balance check (PASS).
- `_to=self` → sub then add same slot, net zero but event emitted (volume-spoof).

## transferFrom() — missing _from zero check (MEDIUM)

```solidity
require(_to != 0x0);
require(_value > 0);
require(balances[_from] >= _value && allowance[_from][msg.sender] >= _value);
```

- No `require(_from != 0x0)`. Not directly exploitable (`balances[0x0]==0` → `_value>0` fails) but inconsistent; flag if mint-to-zero ever existed.

## approve() — classic race (HIGH)

```solidity
function approve(address _spender, uint256 _value) public returns (bool) {
    allowance[msg.sender][_spender] = _value;
}
```

- Direct assignment without `allowance==0` guard. Alice `approve(Bob,100)` → `approve(Bob,50)` can be front-run: Bob `transferFrom` 100 before 50 tx → total 150.
- No `increaseApproval/decreaseApproval`, no `require(_value==0 || allowance==0)`. Proven pattern; high-impact if spender malicious + mempool visibility.
- Also `approve(0x0, ...)` allowed (no zero check) — state pollution; `approve(max)` unlimited drain if spender key compromised.
- Mapping `public allowance` + `function allowance()` shadowing (auto-getter shadowed) — confusing but safe.

## Constructor

- `balances[msg.sender] = _initialAmount` without `*10**decimals` — deployer must add 18 zeros manually (footgun). No `require(_initialAmount>0)`.

## Detection grep

```bash
grep -n "approve" TRYSimple.sol
grep -n "require.*_value" TRYSimple.sol
grep -n "safeSub\|safeAdd" TRYSimple.sol
grep -n "0x0" TRYSimple.sol
```

## Fix checklist

- Add `require(_value>0)` to `transfer()` or document zero-transfer intent.
- Mitigate approve race: `require(_value==0 || allowance[msg.sender][_spender]==0)` or add `increaseAllowance/decreaseAllowance`.
- Add `require(_from != address(0) && _spender != address(0))`.
- Upgrade to sol 0.8.x; remove manual SafeMath.
