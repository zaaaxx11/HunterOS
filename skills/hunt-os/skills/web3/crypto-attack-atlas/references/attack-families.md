# Attack families A1-A18 (synced atlas)

Each family: what breaks, how to spot it, what to run, how to close it.
Incident counts come from the 904-incident dataset (keyword-classified).

## A1 — Reentrancy  (`klass Reentrancy`)

State is updated after an external call, so the callee re-enters before accounting settles.

- incidents: **60** | USD parsed: **$92,473,138** (lower bound)
- SWC: SWC-107, SWC-113
- HUNT-OS skills: token-transfer-audit, evm-contract-audit, black-swan-engine

**Variants**

- classic single-function
- cross-function
- read-only (LP/oracle state seen mid-write)
- callback token (ERC777/677/721 onERC721Received)

**Signals**

- external call before the sstore that settles the balance
- no nonReentrant on a value-moving entry point
- a view function another protocol reads while state is half-written

**Detect / run**

```sh
slither . --detect reentrancy-eth,reentrancy-no-eth,reentrancy-benign,reentrancy-events
```
```sh
grep -rn 'call{value\|\.call(\|transferFrom\|safeTransferFrom' src/ | head -50
```
```sh
forge test --match-test invariant -vvv  (balance-conservation invariant)
```
- trace the exploit tx: >1 hop back into the same contract in one tx

**Mitigate**

- checks-effects-interactions on every value path
- nonReentrant on all entry points touching accounting
- read oracle values from TWAP/cached state, never mid-transaction LP spot

**Real cases**

- 2023-07-30 Curve — $41,000,000 (PoC)
- 2024-09-03 Penpiexyz_io — $27,348,259 (PoC)
- 2022-11-10 DFXFinance — $4,000,000 (PoC)
- 2023-02-10 dForce — $3,650,000 (PoC)

## A2 — Price oracle manipulation  (`klass Oracle`)

The protocol trusts a price it can be made to move inside one transaction.

- incidents: **163** | USD parsed: **$94,967,103** (lower bound)
- SWC: SWC-116
- HUNT-OS skills: defi-protocol-analysis, lending-protocol-fork-audit, evm-contract-audit

**Variants**

- spot reserves
- Uniswap v3 slot0
- token balance as price
- stale feed / missing sequencer check
- thin-pool TWAP

**Signals**

- getReserves()/slot0()/balanceOf() used directly for valuation
- no heartbeat or staleness check on the feed
- no deviation bound between blocks
- LP token accepted as collateral

**Detect / run**

```sh
grep -rn 'getReserves\|slot0\|latestRoundData\|latestAnswer' src/
```
```sh
forge test --fork-url $RPC  (push price in one block, assert borrow capacity)
```
- check feed: answeredInRound, updatedAt age, decimals
```sh
slither . --detect arbitrary-send-erc20,unchecked-transfer
```

**Mitigate**

- Chainlink/Pyth with staleness + sequencer-uptime checks
- TWAP >= 30min and a per-block deviation cap
- circuit breaker on abnormal price delta
- no LP spot price as collateral value

**Real cases**

- 2024-09-03 Penpiexyz_io — $27,348,259 (PoC)
- 2024-06-10 UwULend — $19,300,000 (PoC)
- 2023-05-29 Jimbo — $8,000,000 (PoC)
- 2024-03-05 Woofi — $8,000,000 (PoC)

## A3 — Flash-loan capital amplifier  (`klass Logic`)

Not a bug by itself: it removes the capital bound from every other family.

- incidents: **63** | USD parsed: **$21,868,156** (lower bound)
- SWC: —
- HUNT-OS skills: defi-protocol-analysis, cross-contract-chain-builder

**Variants**

- Aave/Balancer flash loan
- flash swap
- same-block borrow+repay

**Signals**

- any assumption that an attacker cannot hold a large balance for one block
- no per-block / per-tx rate limit on borrow or mint

**Detect / run**

```sh
forge test --fork-url $RPC with deal() sizing attacker capital to pool TVL
```
- audit question: 'if the attacker has 100M for one block, what breaks?'

**Mitigate**

- design against unbounded transient capital
- per-block caps, cooldowns, TWAP-based limits

**Real cases**

- 2024-11-19 PolterFinance — $7,000,000 (PoC)
- 2026-10-24 X100Senate — $4,749,726 (PoC)
- 2022-12-11 Lodestar — $4,000,000 (PoC)
- 2023-04-28 0vix — $2,000,000 (PoC)

## A4 — Access control / authorization  (`klass Access`)

A value-bearing function has no effective guard, or the guard is bypassable.

- incidents: **41** | USD parsed: **$14,201,650** (lower bound)
- SWC: SWC-100
- HUNT-OS skills: evm-contract-audit, black-swan-engine

**Variants**

- missing modifier on setter/init/mint
- tx.origin auth
- unprotected initialize (proxy takeover)
- role grant without two-step
- public function that should be internal

**Signals**

- external/public function with no modifier and a state write
- initialize() callable twice or on the implementation
- owner transfer in one step
- tx.origin in require

**Detect / run**

```sh
slither . --detect unprotected-upgrade,suicidal,arbitrary-send-eth,tx-origin
```
```sh
aderyn .  (centralization + access rules)
```
```sh
grep -rn 'function .*external\|function .*public' src/ then filter for modifiers
```
```sh
grep -rn 'initialize\|_disableInitializers\|tx.origin' src/
```

**Mitigate**

- Ownable2Step + explicit RBAC
- timelock + multisig for sensitive params
- initializer modifier and _disableInitializers() on implementations
- never tx.origin for auth

**Real cases**

- 2026-10-24 X100Senate — $4,749,726 (PoC)
- 2026-06-17 Aztec V1 — $2,200,000 (PoC)
- 2026-06-14 Aztec Connect — $2,190,000 (PoC)
- 2022-09-28 MEVBOT — $1,469,700 (PoC)

## A5 — Business logic & accounting  (`klass Logic`)

Code does what it says, but the accounting model is wrong or incomplete.

- incidents: **238** | USD parsed: **$421,999,015** (lower bound)
- SWC: SWC-110
- HUNT-OS skills: business-logic-invariant-hunt, black-swan-engine, defi-protocol-analysis

**Variants**

- wrong update order
- unit/decimals mix
- double counting
- struct/array deletion leaves stale state
- return vs break
- payable.transfer() for distribution

**Signals**

- no invariant test anywhere in the repo
- internal balances that are never reconciled with token.balanceOf
- silent failure paths (no revert on failure)

**Detect / run**

- write invariants first: sum(balances) == balanceOf(this); totalDebt <= totalAssets
```sh
echidna test/invariants.sol --contract Invariants
```
```sh
medusa fuzz --config medusa.json
```
```sh
halmos --function check_  (prove the property, not just sample it)
```

**Mitigate**

- invariants in CI
- double-entry accounting
- single source of truth per value

**Real cases**

- 2023-03-13 EulerFinance — $200,000,000 (PoC)
- 2025-02-23 HegicOptions — $104,000,000 (PoC)
- 2024-01-01 OrbitChain — $81,000,000 (PoC)
- 2021-05-16 bEarn — $11,000,000 (PoC)

## A6 — Share / ERC4626 accounting  (`klass Logic`)

The asset<->share conversion can be shifted, usually by donation or first-deposit inflation.

- incidents: **40** | USD parsed: **$29,702,896** (lower bound)
- SWC: SWC-101
- HUNT-OS skills: defi-protocol-analysis, lending-protocol-fork-audit, token-transfer-audit

**Variants**

- first-deposit inflation
- donation to totalAssets
- rounding in favour of the user
- preview* inconsistent with the action

**Signals**

- totalAssets() reads balanceOf
- no virtual shares / decimals offset
- redeem rounding direction favours the caller
- no minimum seed deposit

**Detect / run**

```sh
grep -rn 'totalAssets\|convertToShares\|previewRedeem\|_decimalsOffset' src/
```
```sh
forge test: deposit 1 wei, donate 1e18, deposit again as victim, assert loss
```
- invariant: share price must not decrease without a loss event

**Mitigate**

- OZ ERC4626 with _decimalsOffset / virtual shares
- accounting variable for totalAssets, not balanceOf
- rounding always against the user

**Real cases**

- 2021-05-16 bEarn — $11,000,000 (PoC)
- 2023-04-15 HundredFinance — $7,000,000 (PoC)
- 2023-02-24 EFVault — $5,100,000 (PoC)
- 2023-11-10 Raft_fi — $3,200,000 (PoC)

## A7 — Precision, rounding & arithmetic  (`klass Arithmetic`)

Integer math loses or misplaces value that an attacker can harvest in a loop.

- incidents: **23** | USD parsed: **$86,572,843** (lower bound)
- SWC: SWC-101
- HUNT-OS skills: evm-contract-audit, token-transfer-audit

**Variants**

- divide before multiply
- downcast truncation
- round-to-zero dust
- mulDiv without 512-bit intermediate
- unchecked block in accounting

**Signals**

- '/' appearing before '*' in a value formula
- uint256 -> uint128 casts
- magnitudes with different decimals in one expression

**Detect / run**

```sh
slither . --detect divide-before-multiply,incorrect-exp,tautology
```
```sh
forge test --fuzz-runs 10000 with boundary values (0, 1, max)
```
```sh
grep -rn 'uint128(\|uint96(\|uint64(\|unchecked {' src/
```

**Mitigate**

- mulDiv (Solady/PRBMath)
- explicit decimals normalisation
- no unchecked in accounting paths

**Real cases**

- 2023-11-22 KyberSwap — $48,000,000 (PoC)
- 2024-05-14 Sonne Finance — $20,000,000 (PoC)
- 2023-04-15 HundredFinance — $7,000,000 (PoC)
- 2024-01-02 RadiantCapital — $4,500,000 (PoC)

## A8 — Signature, permit & replay  (`klass Sig`)

A signature is trusted more than it should be: no nonce, no domain binding, or a zero-recover.

- incidents: **21** | USD parsed: **$16,241,130** (lower bound)
- SWC: SWC-117
- HUNT-OS skills: evm-contract-audit, wallet-auth-bypass-audit

**Variants**

- ecrecover returns address(0)
- nonce not consumed
- domain separator missing chainId/verifyingContract
- permit without deadline
- malleable s value
- ERC-1271 unchecked
- stale unlimited approval

**Signals**

- ecrecover used directly without a zero/s-value check
- digest built from abi.encodePacked with >1 dynamic arg
- no nonce mapping read before the action

**Detect / run**

```sh
slither . --detect incorrect-erc20-interface,abi-encode-packed
```
```sh
grep -rn 'ecrecover\|ECDSA\|permit\|nonce\|DOMAIN_SEPARATOR' src/
```
- verify digest binds chainId + address(this) + nonce + deadline

**Mitigate**

- EIP-712 with nonce + deadline, OZ ECDSA.recover
- increaseAllowance over unlimited approve; periodic revoke

**Real cases**

- 2026-10-26 SafeApprovalSquat — $7,450,000 (PoC)
- 2026-05-07 TrustedVolumes — $5,870,000 (PoC)
- 2026-04-23 GiddyVaultV3 — $1,300,000 (PoC)
- 2026-10-27 FenceTranchePool — $1,013,000 (PoC)

## A9 — Initialization, proxy & upgrade  (`klass Upgradeable`)

The proxy's storage or implementation pointer can be taken over.

- incidents: **17** | USD parsed: **$21,858,576** (lower bound)
- SWC: SWC-112
- HUNT-OS skills: evm-contract-audit, erc4337-bundler-audit

**Variants**

- implementation not _disableInitializers()
- storage layout shift
- delegatecall to untrusted target
- reinitializer reused
- selfdestruct in library

**Signals**

- upgradeTo without timelock
- no storage gap in upgradeable base
- initialize without initializer modifier
- addition of a parent variable

**Detect / run**

```sh
slither . --print storage-layout  (diff across versions)
```
```sh
diffyscan  (source vs verified bytecode drift)
```
```sh
aderyn .  (proxy/initializer rules)
```
```sh
grep -rn 'delegatecall\|upgradeTo\|_disableInitializers\|initializer' src/
```

**Mitigate**

- storage gaps, onlyProxy/notDelegated guards
- timelocked upgrades with multisig
- reinitializer(version)

**Real cases**

- 2026-09-15 RsETHSafeModule — $7,800,000 (PoC)
- 2026-05-07 TrustedVolumes — $5,870,000 (PoC)
- 2023-02-24 EFVault — $5,100,000 (PoC)
- 2024-04-30 PikeFinance — $1,400,000 (PoC)

## A10 — Bridge & cross-chain verification  (`klass Logic`)

The destination chain accepts a message it should not have accepted.

- incidents: **25** | USD parsed: **$27,431,049** (lower bound)
- SWC: SWC-133
- HUNT-OS skills: cross-contract-chain-builder, l2-rollup-audit, on-chain-exploit-workflow

**Variants**

- proof not bound to chainId/contract
- installable root
- public relayer without role
- replay across chains
- single trusted validator
- transient-state leftover

**Signals**

- message hash not persisted before use
- no replay guard
- root/validator settable by an unprivileged address
- trust assumption undocumented

**Detect / run**

```sh
grep -rn 'verify\|prove\|root\|relay\|l2LogsRoot\|finalize' src/
```
```sh
forge test --fork: replay the same proof twice; replay on a second fork chainId
```
- map the trust boundary: who can install a root? who can relay?

**Mitigate**

- domain separation per chain+contract, persisted message ids
- threshold multisig / light client, per-epoch rate limits
- two independent verification paths

**Real cases**

- 2026-05-17 VerusBridge — $11,580,000 (PoC)
- 2024-11-19 PolterFinance — $7,000,000 (PoC)
- 2024-01-30 MIMSpell — $6,500,000 (PoC)
- 2026-10-28 ZkLinkNova — $783,000 (PoC)

## A11 — Token integration quirks  (`klass ExternalCall`)

An integration assumes a standard ERC-20 that the token does not implement.

- incidents: **19** | USD parsed: **$1,456,121** (lower bound)
- SWC: SWC-104
- HUNT-OS skills: token-transfer-audit, evm-contract-audit

**Variants**

- fee-on-transfer
- rebasing
- returns false
- no return value
- ERC777 hook
- weird ERC4626 limits
- permit2

**Signals**

- accounting uses the requested amount instead of the measured delta
- transfer() return value unchecked
- token whitelist absent

**Detect / run**

```sh
slither . --detect unchecked-transfer,unchecked-lowlevel,low-level-calls
```
```sh
grep -rn 'transfer(\|transferFrom(' src/  (must be safeTransfer + measured)
```
- unit test with a fee-on-transfer mock token

**Mitigate**

- measure balanceBefore/After on every transfer-in
- whitelist tokens with tested behaviour
- never account from the requested amount

**Real cases**

- 2026-03-23 BCE — $800,000 (PoC)
- 2026-04-28 RWAVault — $398,655 (PoC)
- 2026-10-02 GoldPesa — $115,000 (PoC)
- 2026-06-16 DIP — $111,098 (PoC)

## A12 — Liquidation, economics & MEV  (`klass Logic`)

Economic parameters or execution ordering let value leak without any code bug.

- incidents: **61** | USD parsed: **$39,714,526** (lower bound)
- SWC: SWC-114
- HUNT-OS skills: defi-protocol-analysis, lending-protocol-fork-audit

**Variants**

- LTV/bonus mis-set
- oracle-lagged liquidation
- uncapped emissions
- sandwich
- bad-debt socialization

**Signals**

- liquidation threshold above what a -30% move survives
- reward emission without cap
- no minOut on user swaps
- public mempool execution

**Detect / run**

- stress simulation: price -50%, liquidity -90%, 100% utilization
```sh
grep -rn 'liquidationThreshold\|bonus\|emission\|rewardRate' src/
```
- eigenphi / bundle analysis for sandwich exposure

**Mitigate**

- dynamic thresholds, oracle heartbeats
- emission caps
- private mempool or minOut for users

**Real cases**

- 2024-09-03 Penpiexyz_io — $27,348,259 (PoC)
- 2026-10-24 X100Senate — $4,749,726 (PoC)
- 2023-11-07 MEVbot — $2,000,000 (PoC)
- 2023-02-17 Dexible — $1,500,000 (PoC)

## A13 — Slippage & deadline  (`klass Logic`)

User-supplied parameters are trusted defaults, so execution is free to be bad.

- incidents: **15** | USD parsed: **$883,675** (lower bound)
- SWC: SWC-114
- HUNT-OS skills: defi-protocol-analysis, evm-contract-audit

**Variants**

- minOut = 0
- infinite deadline
- attacker-chosen swap path
- arbitrary calldata accepted

**Signals**

- minOut/minShares optional or defaulted to 0
- deadline in the far future
- selector/path not validated against a whitelist

**Detect / run**

```sh
grep -rn 'minOut\|minAmountOut\|minShares\|deadline\|swapExact' src/
```
- unit test: call the entry with minOut=0 and assert it reverts

**Mitigate**

- mandatory minOut computed on-chain, short deadline, router whitelist

**Real cases**

- 2025-03-18 DCFToken — $442,000 (PoC)
- 2023-11-06 TheStandard_io — $290,000 (PoC)
- 2026-10-19 Argent — $59,800 (PoC)
- 2023-08-02 CurveBurner — $36,000 (PoC)

## A14 — Governance  (`klass Access`)

The treasury can be moved through a 'valid' decision.

- incidents: **11** | USD parsed: **$5,036,626** (lower bound)
- SWC: —
- HUNT-OS skills: evm-contract-audit, cross-contract-chain-builder

**Variants**

- flash-loan voting
- proposal executes treasury transfer
- low quorum
- no/short timelock
- double execution

**Signals**

- snapshot taken on a borrowable balance
- proposal payload unrestricted
- quorum below realistic turnout
- timelock < 24h

**Detect / run**

```sh
grep -rn 'propose\|quorum\|timelock\|execute\|snapshot' src/
```
```sh
forge test: simulate a proposal that calls transfer() out of the treasury
```
- verify executed-proposal ids are persisted

**Mitigate**

- escrowed/locked voting weight, absolute quorum, >=48h timelock
- treasury spend caps per proposal, dual governance for upgrades

**Real cases**

- 2026-10-24 X100Senate — $4,749,726 (PoC)
- 2026-09-12 YamFinance — $121,000 (PoC)
- 2026-08-05 StrongBlock — $72,000 (PoC)
- 2026-10-03 MALT — $72,000 (PoC)

## A15 — Key compromise & operational compromise  (`klass Access`)

No contract bug: a key, signer, or engineer endpoint was compromised and value moved.

- incidents: **4** | USD parsed: **$1,500,152,295** (lower bound)
- SWC: —
- HUNT-OS skills: on-chain-forensics, sovereign-ops-protocol

**Variants**

- hot-wallet private key leak
- multisig signer phishing
- devops laptop compromise
- insider
- EIP-7702 delegation abuse

**Signals**

- signer set changed
- tx from a receive-only wallet
- mass approvals
- sweep to a fresh address
- new EIP-7702 delegation on a treasury EOA

**Detect / run**

- monitor signer sets and delegation designators off-chain
- diff the signer list against the recorded baseline each round
- alert on approvals to unseen spenders from treasury addresses

**Mitigate**

- HSM/MPC, proposer/approver separation, allowlist policy engine
- hardware keys + FIDO, rotation
- real-time on-chain monitoring + freeze playbook

**Real cases**

- 2025-02-21 Bybit — $1,500,000,000 (PoC)
- 2026-10-18 AlpsCon — $152,295 (PoC)
- 2021-03-05 Paid Network — n/a (PoC)
- 2022-06-24 Harmony's Horizon Bridge — n/a (PoC)

## A16 — Supply chain & infrastructure  (`klass Web2`)

The frontend/dependency layer is compromised, so users sign or send to the attacker.

- incidents: **1** | USD parsed: **$447,000** (lower bound)
- SWC: —
- HUNT-OS skills: js-secret-scanner, frontend-security-audit, saas-supply-chain-exploitation

**Variants**

- compromised third-party script
- DNS/CDN takeover
- malicious npm dependency
- browser extension

**Signals**

- unpinned third-party script in the dapp HTML
- no SRI/CSP
- dependency without lockfile pin

**Detect / run**

```sh
curl -s $APP | grep -o 'src="[^"]*"'  (list external scripts, check integrity)
```
- check CSP/SRI headers
- audit lockfile diffs for new transitive packages

**Mitigate**

- SRI + strict CSP, pinned lockfiles, signed releases
- integrity monitoring of build output

**Real cases**

- 2024-11-14 vETH — $447,000 (PoC)

## A17 — Transient storage  (`klass Logic`)

EIP-1153 transient state survives longer than the code assumes, or is reused across calls.

- incidents: **2** | USD parsed: **$785,876** (lower bound)
- SWC: —
- HUNT-OS skills: evm-contract-audit, l2-rollup-audit

**Variants**

- uncleared finalize hash
- auth decided from transient value
- assumption that tstore persists

**Signals**

- tstore in one call path, tload in another, no clear in between
- authorization branch reading transient state

**Detect / run**

```sh
grep -rn 'tstore\|tload\|transient' src/  (and assembly equivalents)
```
```sh
forge test: two calls in one tx, second reuses the first's transient value
```
```sh
slither (recent versions flag transient misuse)
```

**Mitigate**

- treat transient values as function-scoped: set, use, clear
- never base authorization on transient state across calls

**Real cases**

- 2026-10-28 ZkLinkNova — $783,000 (PoC)
- 2026-09-16 Startale — $2,876 (PoC)

## A18 — Freeze, pause & blacklist  (`klass Access`)

Funds cannot move: issuer blacklist, protocol pause, or forced upgrade.

- incidents: **0** | USD parsed: **$0** (lower bound)
- SWC: SWC-105
- HUNT-OS skills: evm-contract-audit, sovereign-ops-protocol

**Variants**

- stablecoin blacklist
- pause() blocks withdraw
- admin upgrade changes withdrawal logic
- guardian halt

**Signals**

- pause modifier on withdraw
- no emergency exit path
- issuer dependency undocumented

**Detect / run**

```sh
grep -rn 'whenNotPaused\|paused()\|blacklist\|freeze' src/
```
- test the admin-evil and admin-gone scenarios end to end
- check whether withdraw/redeem is reachable while paused

**Mitigate**

- pause must never block user exit (or an explicit emergency path exists)
- document all admin power as centralization risk
- time-delayed upgrades
