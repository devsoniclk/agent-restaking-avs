#!/usr/bin/env python3
"""
Example: Deterministic SLA Dispute Adjudication and Slashing Waterfall.
"""

from agent_restaking_avs import (
    ArbitrationTribunal,
    DisputeType,
    FraudClaim,
    StakePoolConfig,
    StakingManager,
    SlashingWaterfallEngine,
    TaskReceipt,
)


def main() -> None:
    config = StakePoolConfig()
    staking = StakingManager(config)
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)

    # Register operator
    staking.register_operator(
        operator_id="agent-worker-01",
        did="did:agent:eth:0x4444444444444444444444444444444444444444",
        public_key="0xpub4",
        native_stake=25000.0,
        restaked_eth=25.0,
    )

    # 1. Record completed task execution receipt
    receipt = TaskReceipt(
        task_id="task-web-scrape-001",
        operator_id="agent-worker-01",
        escrow_usd=800.0,
        deadline=1000.0,
        expected_schema_hash="0xvalid_schema",
        actual_output_hash="0xinvalid_schema",  # Schema hallucination
        allowed_tools=["fetch_url", "parse_html"],
        executed_tools=["fetch_url", "parse_html"],
        state_root="0xstate001",
        submitted_at=950.0,
    )
    tribunal.record_receipt(receipt)

    # 2. Watchdog files dispute
    claim = FraudClaim(
        claim_id="claim-fraud-001",
        challenger_did="did:agent:eth:0xwatchdog_did",
        operator_id="agent-worker-01",
        task_id="task-web-scrape-001",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH,
        bond_usd=100.0,
        evidence={"expected_schema_hash": "0xvalid_schema", "actual_output_hash": "0xinvalid_schema"},
    )
    tribunal.file_dispute(claim)

    # 3. Adjudicate and execute waterfall
    is_guilty, resolved_type, slashing = tribunal.adjudicate("claim-fraud-001")
    print("Tribunal Adjudication Results:")
    print(f" • Guilty: {is_guilty}")
    print(f" • Dispute Type: {resolved_type.value}")
    if slashing:
        print(f" • Total Collateral Slashed: ${slashing.total_slashed_usd:,.2f} USD")
        print(f" • User Escrow Refund (100%): ${slashing.user_refund_usd:,.2f} USD")
        print(f" • Challenger Bounty (25%): ${slashing.challenger_bounty_usd:,.2f} USD")
        print(f" • Insurance Reserve (45%): ${slashing.insurance_reserve_usd:,.2f} USD")
        print(f" • Burned (30%): ${slashing.burn_usd:,.2f} USD")
        print(f" • Operator Jailed: {slashing.operator_jailed}")


if __name__ == "__main__":
    main()
