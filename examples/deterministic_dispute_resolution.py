"""
Example demonstrating cryptographic fraud challenge and automated collateral slashing waterfall.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_restaking_avs.arbitration import ArbitrationTribunal
from agent_restaking_avs.models import DisputeType, FraudClaim, TaskReceipt
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


def main():
    print("--- 1. Setting Up AVS Arbitration Tribunal ---")
    staking = StakingManager()
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)

    staking.register_operator(
        operator_id="agent-worker-01",
        did="did:agent:eth:0x4444444444444444444444444444444444444444",
        public_key="0xworker_pubkey",
        native_stake=25000.0,
        restaked_eth=20.0,
    )

    print("--- 2. Recording Completed Task Execution ---")
    receipt = TaskReceipt(
        task_id="task-crypto-sentiment-99",
        operator_id="agent-worker-01",
        escrow_usd=1000.0,
        deadline=1000.0,
        expected_schema_hash="0xexpected_schema",
        actual_output_hash="0xexpected_schema",
        allowed_tools=["fetch_news", "parse_json"],
        executed_tools=["fetch_news", "parse_json", "send_private_key_egress"],  # Rogue tool execution!
        state_root="0xroot99",
        submitted_at=950.0,
    )
    tribunal.record_receipt(receipt)
    print("Task receipt recorded in tribunal ledger.\n")

    print("--- 3. Watchdog Files Fraud Claim ---")
    claim = FraudClaim(
        claim_id="fraud-claim-001",
        challenger_did="did:agent:eth:0xwatchdog_agent",
        operator_id="agent-worker-01",
        task_id="task-crypto-sentiment-99",
        dispute_type=DisputeType.UNAUTHORIZED_TOOL_EXECUTION,
        bond_usd=100.0,
        evidence={},
    )
    tribunal.file_dispute(claim)
    print("Dispute filed with $100.00 USD challenger bond.\n")

    print("--- 4. Adjudicating Claim and Executing Slashing Waterfall ---")
    guilty, resolved_type, slashing = tribunal.adjudicate("fraud-claim-001")
    print(f"Operator Guilty? {guilty}")
    print(f"Resolved Violation: {resolved_type.value}")
    if slashing:
        print(f" • Total Collateral Slashed: ${slashing.total_slashed_usd:,.2f} USD")
        print(f" • Challenger Bounty (25%):   ${slashing.challenger_bounty_usd:,.2f} USD")
        print(f" • Insurance Reserve (45%):   ${slashing.insurance_reserve_usd:,.2f} USD")
        print(f" • Burned Collateral (30%):   ${slashing.burn_usd:,.2f} USD")
        print(f" • User Escrow Refund (100%): ${slashing.user_refund_usd:,.2f} USD")
        print(f" • Operator Jailed? {slashing.operator_jailed}")


if __name__ == "__main__":
    main()
