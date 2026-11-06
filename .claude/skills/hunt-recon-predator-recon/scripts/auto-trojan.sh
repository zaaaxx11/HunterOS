#!/bin/bash
# AUTO-TROJAN MODE
# Fallback when direct force fails (3+ vectors, no results)
# SOUL.md Trojan Mode: Gatekeeper → Two-Layer Objective → Horse Architecture → Verdict

set -euo pipefail

VULNS_FILE="${1}"
TARGETS_FILE="${2}"
OUT_DIR="${OUT_DIR:-$(pwd)/recon-$(date +%Y%m%d-%H%M)}"
mkdir -p "$OUT_DIR"

TROJAN_PLAN="$OUT_DIR/trojan-plan.yaml"
ASSUMPTIONS_LOG="$OUT_DIR/assumptions.log"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$ASSUMPTIONS_LOG"; }

log "=== AUTO-TROJAN MODE TRIGGERED ==="
log "Direct exploit failed. Switching to indirect strategy."
log "Principle: Strongest barrier defeated not by force but by understanding what gatekeeper admits."

# ===== GATEKEEPER MODEL =====
log "Analyzing gatekeepers..."

cat > "$TROJAN_PLAN" << 'EOF'
# TROJAN MODE PLAN - Auto-generated
# SOUL.md V8.1 Trojan Horse Doctrine

mission: "Achieve strategic objective through gatekeeper acceptance, not direct force"

gatekeeper_analysis:
  # For each gatekeeper found during recon:
  # - name: "Multisig Timelock"
  #   gate: "Contract upgrade / admin function"
  #   keeper: "Multisig signers (3/5)"
  #   signal: "Proposal with valid signature + timelock delay"
  #   reward: "Protocol improvement / security fix / upgrade"
  #   inspection: "Code review / simulation / timelock delay"
  #   weak_signal: "Emergency upgrades bypass timelock"
  #   urgency_override: "Critical severity bypasses review"
  
  # - name: "Oracle Price Feed"
  #   gate: "Price acceptance for liquidation / minting"
  #   keeper: "Chainlink / TWAP / Custom oracle"
  #   signal: "Price within deviation threshold"
  #   reward: "Accurate pricing / protocol stability"
  #   inspection: "Deviation checks / heartbeat / multiple sources"
  #   weak_signal: "Single source / stale data acceptance"
  #   urgency_override: "Liquidation cascades force acceptance"

two_layer_objectives:
  visible_value: ""
  strategic_value: ""

horse_architecture:
  chamber_1_exterior:
    description: "Real value that survives scrutiny"
    example: "Security improvement proposal / Gas optimization / Feature request"
  
  chamber_2_acceptance_mechanism:
    description: "Why the gate opens"
    signals:
      - "Incentive: Protocol gets measurable improvement"
      - "Authority: Signed by recognized security researcher"
      - "Social proof: Endorsed by known auditors"
      - "Familiarity: Uses standard patterns (OpenZeppelin, etc.)"
      - "Convenience: One-click deploy / minimal governance friction"
      - "Urgency: Critical fix needed NOW"
      - "Curiosity: Novel approach worth reviewing"
      - "Scarcity: Limited window for this optimization"
  
  chamber_3_hidden_dependency:
    description: "Assumption introduced by acceptance"
    examples:
      - "New governance dependency (timelock delay)"
      - "New oracle dependency (price feed assumption)"
      - "New admin role (emergency pause power)"
      - "New contract dependency (library upgrade)"
  
  chamber_4_reveal_condition:
    description: "Event activating strategic value"
    requirements: "Explicit, measurable, authorized, reversible"
    examples:
      - "Timelock expiry + execute()"
      - "Oracle price deviation trigger"
      - "Emergency pause activation"
      - "Governance vote passing"
  
  chamber_5_exit:
    description: "Rollback / audit / stabilization"
    requirement: "No Trojan complete without rollback path"
    paths:
      - "Timelock cancel before execution"
      - "Governance veto"
      - "Emergency pause by admin"
      - "Contract self-destruct / upgrade revert"

indirect_victory_protocol:
  comparison:
    force: "Direct exploit attempt (failed)"
    bypass: "Use existing legitimate upgrade path"
    reframe: "Change decision criteria (security → efficiency)"
    incentivize: "Make cooperation rational (bounty + reputation)"
    embed: "Become part of accepted workflow (auditor / contributor)"
    wait: "Let conditions change (upgrade window / governance cycle)"
  
  selection_rule: "Least destructive route with verifiable result"
  formula: "Indirect Advantage = Acceptance Prob × Strategic Leverage − Trust Cost − Irreversibility"

trojan_defense_check:
  # Run on ANY proposal you receive or make
  triggers:
    - "Unusually valuable / effortless / urgent / perfectly timed"
  steps:
    1. "Verify origin (who proposed? history? reputation?)"
    2. "Verify contents (code review / simulation / formal verification)"
    3. "Verify requested access (least privilege? time-bound?)"
    4. "Identify hidden dependencies (new trust assumptions?)"
    5. "Test in isolation (fork simulation / staging)"
    6. "Monitor delayed behavior (post-deployment hooks)"
    7. "Preserve rollback path (timelock / governance veto)"

trojan_verdict:
  proceed_only_if_survives:
    - "Inspection (code review passes)"
    - "Disclosure (all assumptions documented)"
    - "Rejection (would survive 'no' from gatekeeper)"
    - "Misuse analysis (what if malicious actor submits same?)"
    - "Rollback testing (can we undo in < 1 block?)"

next_actions:
  1. "Identify ALL gatekeepers from Phase 1-4 recon"
  2. "Map each: Gate, Keeper, Signal, Reward, Inspection"
  3. "Design Two-Layer Objective for highest-value gate"
  4. "Build Horse Architecture (5 chambers)"
  4. "Run Indirect Victory comparison"
  5. "Run Trojan Defense check on own plan"
  6. "Execute smallest authorized deployment first"
  7. "Monitor → Verify → Escalate or Rollback"

soul_integration:
  calculus: "Value > Cost + Risk + Irreversibility (including trust cost)"
  blind_spot: "What did I NOT look at? What would devs expect me to miss?"
  anti_delusion: "Flag: confirmation bias / sunk cost / narrative / false urgency / ego"
  trojan_synthesis: "Professor designs sequence. Trojan designs acceptance point."
  trojan_ayanokoji: "Minimal force. Let value carry proposal. Preserve optionality."

EOF

log "=== TROJAN PLAN GENERATED ==="
log "File: $TROJAN_PLAN"
log ""
log "NEXT STEPS:"
log "  1. Edit trojan-plan.yaml with actual gatekeeper data from recon"
log "  2. Design Visible Value + Strategic Value for target gatekeeper"
log "  3. Build Horse Architecture (5 chambers)"
log "  4. Run Indirect Victory comparison"
log "  5. Run Trojan Defense check on YOUR plan"
log "  6. Execute smallest authorized step"
log "  7. Monitor → Verify → Escalate or Rollback"