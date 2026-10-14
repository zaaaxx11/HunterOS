#!/bin/bash
# PHASE 5: ON-CHAIN / DEFI RECON & EXPLOIT PREP
# Input: targets.yaml (with contract addresses, chain IDs)
# Output: contracts.txt, storage.txt, functions.txt, exploit-plan.yaml

set -euo pipefail

TARGETS_FILE="${1}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

log "=== PHASE 5: ON-CHAIN / DEFI ==="
log "Targets: $TARGETS_FILE"

# Check required tools
for tool in cast forge; do
    if ! command -v $tool &> /dev/null; then
        log "ERROR: $tool not found. Install Foundry: curl -L https://foundry.paradigm.xyz | bash"
        exit 1
    fi
done

# Parse targets.yaml (simple grep for now, use yq for production)
CONTRACTS=$(grep -A 10 "contracts:" "$TARGETS_FILE" | grep -E "^\s*-" | sed 's/^\s*-\s*//')
CHAIN_ID=$(grep "chain:" "$TARGETS_FILE" | head -1 | sed 's/.*://' | tr -d ' ')
RPC_URL="${RPC_URL:-https://eth-mainnet.g.alchemy.com/v2/demo}"

log "Chain ID: $CHAIN_ID"
log "RPC: $RPC_URL"
log "Contracts: $(echo "$CONTRACTS" | wc -l)"

for CONTRACT in $CONTRACTS; do
    log "Analyzing $CONTRACT..."
    CONTRACT_DIR="$OUT_DIR/$CONTRACT"
    mkdir -p "$CONTRACT_DIR"
    
    # 1. Verify contract
    log "  Verifying source..."
    forge verify-check --chain-id "$CHAIN_ID" "$CONTRACT" --rpc-url "$RPC_URL" \
        > "$CONTRACT_DIR/verify.txt" 2>&1 || true
    
    # 2. Get bytecode
    log "  Getting bytecode..."
    cast code "$CONTRACT" --rpc-url "$RPC_URL" > "$CONTRACT_DIR/bytecode.txt"
    
    # 3. Storage layout (first 50 slots)
    log "  Reading storage (slots 0-49)..."
    for i in {0..49}; do
        cast storage "$CONTRACT" "$i" --rpc-url "$RPC_URL" \
            >> "$CONTRACT_DIR/storage.txt" 2>&1 || true
    done
    
    # 4. Function selectors (from bytecode)
    log "  Extracting function selectors..."
    cast 4byte "$CONTRACT" --rpc-url "$RPC_URL" 2>/dev/null | \
        grep -E "^\s*0x" | anew "$CONTRACT_DIR/selectors.txt" || true
    
    # 5. Known function calls
    KNOWN_FUNCTIONS=(
        "owner()(address)"
        "admin()(address)"
        "pendingAdmin()(address)"
        "implementation()(address)"
        "getAdmin()(address)"
        "getImplementation()(address)"
        "paused()(bool)"
        "totalSupply()(uint256)"
        "balanceOf(address)(uint256)"
        "allowance(address,address)(uint256)"
        "getReserves()(uint112,uint112,uint32)"
        "token0()(address)"
        "token1()(address)"
        "factory()(address)"
        "fee()(uint256)"
        "kLast()(uint256)"
    )
    
    log "  Calling known functions..."
    for fn in "${KNOWN_FUNCTIONS[@]}"; do
        sig=$(echo "$fn" | sed 's/(.*)//')
        cast call "$CONTRACT" "$fn" --rpc-url "$RPC_URL" \
            >> "$CONTRACT_DIR/known-functions.txt" 2>&1 || true
    done
    
    # 6. Check for upgradeability (proxy patterns)
    log "  Checking upgradeability..."
    cast call "$CONTRACT" "implementation()(address)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/proxy-check.txt" 2>&1 || true
    cast call "$CONTRACT" "admin()(address)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/proxy-check.txt" 2>&1 || true
    
    # 7. Token analysis (if ERC20)
    log "  Checking ERC20..."
    cast call "$CONTRACT" "name()(string)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/token-info.txt" 2>&1 || true
    cast call "$CONTRACT" "symbol()(string)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/token-info.txt" 2>&1 || true
    cast call "$CONTRACT" "decimals()(uint8)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/token-info.txt" 2>&1 || true
    cast call "$CONTRACT" "totalSupply()(uint256)" --rpc-url "$RPC_URL" \
        >> "$CONTRACT_DIR/token-info.txt" 2>&1 || true
    
    # 8. Balance check (contract's own balance)
    log "  Checking balances..."
    cast balance "$CONTRACT" --rpc-url "$RPC_URL" >> "$CONTRACT_DIR/balances.txt" 2>&1 || true
    
    # Common tokens
    for token in "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2" "0xA0b86a33E6441b8c4C8C8C8C8C8C8C8C8C8C8C8C8" "0x6B175474E89094C44Da98b954EedeAC495271d0F"; do
        cast call "$token" "balanceOf(address)(uint256)" "$CONTRACT" --rpc-url "$RPC_URL" \
            >> "$CONTRACT_DIR/balances.txt" 2>&1 || true
    done
    
    log "  Done $CONTRACT"
done

# ===== CONSOLIDATE =====
log "Consolidating findings..."
cat "$OUT_DIR"/*/storage.txt 2>/dev/null | sort -u > "$OUT_DIR/all-storage.txt"
cat "$OUT_DIR"/*/known-functions.txt 2>/dev/null | sort -u > "$OUT_DIR/all-known-functions.txt"
cat "$OUT_DIR"/*/proxy-check.txt 2>/dev/null | sort -u > "$OUT_DIR/all-proxy-check.txt"
cat "$OUT_DIR"/*/token-info.txt 2>/dev/null | sort -u > "$OUT_DIR/all-token-info.txt"
cat "$OUT_DIR"/*/balances.txt 2>/dev/null | sort -u > "$OUT_DIR/all-balances.txt"

# ===== EXPLOIT PLAN GENERATION =====
log "Generating exploit plan template..."
cat > "$OUT_DIR/exploit-plan.yaml" << 'EOF'
# Exploit Plan - Fill in based on findings
# Use with SOUL.md Core Loop: ELIMINATE → TRACE → WALK → LOOP

target_analysis:
  # Contract: findings
  # e.g., "0x123...": 
  #   proxy: true
  #   admin: 0xabc...
  #   upgradeable: true
  #   storage_slot_admin: 0
  #   token_balance: 1000000 USDC

vulnerability_candidates:
  # - type: "reentrancy"
  #   contract: "0x123..."
  #   function: "withdraw()"
  #   evidence: "external call before state update"
  #   calculus: {value: 50000, cost: 10, risk: 3, clean: true, fallback: "flashloan repay"}

  # - type: "oracle_manipulation"
  #   contract: "0x456..."
  #   oracle: "UniswapV2 TWAP"
  #   window: "30 min"
  #   calculus: {value: 20000, cost: 50, risk: 5, clean: false}

  # - type: "access_control"
  #   contract: "0x789..."
  #   function: "setAdmin()"
  #   issue: "no authorization check"
  #   calculus: {value: 100000, cost: 5, risk: 2, clean: true}

deep_mode_trigger:
  attempts: 0
  max_attempts: 3
  # When 3+ targets yield no vulns → auto deep mode

trojan_mode_candidates:
  # - gatekeeper: "multisig timelock"
  #   visible_value: "propose security upgrade"
  #   strategic_value: "delayed execution bypass"
  #   acceptance_signal: "timelock delay passed"

next_actions:
  - "Verify all findings manually"
  - "Build PoC for each candidate"
  - "Simulate on fork (forge test --fork-url $RPC)"
  - "Calculate exact gas costs"
  - "Prepare flashloan / capital if needed"
  - "Define abort conditions"
EOF

log "=== PHASE 5 COMPLETE ==="
log "Outputs:"
log "  $OUT_DIR/*/storage.txt (storage layouts)"
log "  $OUT_DIR/*/known-functions.txt (function calls)"
log "  $OUT_DIR/*/proxy-check.txt (upgradeability)"
log "  $OUT_DIR/*/token-info.txt (ERC20 details)"
log "  $OUT_DIR/*/balances.txt (contract balances)"
log "  $OUT_DIR/all-*.txt (consolidated)"
log "  $OUT_DIR/exploit-plan.yaml (template)"

# Export for next phase
echo "$OUT_DIR/exploit-plan.yaml" > "$OUT_DIR/.phase5-plan"