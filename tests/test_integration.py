"""
End-to-end integration tests for Agent Restaking AVS Protocol.
"""

import time
import pytest
from agent_restaking_avs.arbitration import ArbitrationTribunal
from agent_restaking_avs.identity import IdentityManager
from agent_restaking_avs.models import (
    DisputeType,
    FraudClaim,
    OperatorStatus,
    StakePoolConfig,
    TaskReceipt,
)
from agent_restaking_avs.relays import CrossChainRelayEngine, ReplayAttackError
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


def test_full_avs_lifecycle_e2e():
    """
    Simulate full operational cycle of an autonomous agent AVS network:
    1. Register multiple heterogeneous agent operators (validator cluster).
    2. Attest cryptographic identity with hardware TEE proofs.
    3. Execute cross-chain state relay under dual-quorum consensus.
    4. Guard against Byzantine replay attacks.
    5. Detect SLA violation, execute multi-tranche slashing waterfall.
    6. Verify strict mathematical conservation across all funds.
    7. Jail depleted operator and restore upon stake replenishment.
    """
    config = StakePoolConfig(
        min_native_stake=10000.0,
        min_eth_stake=10.0,
        consensus_threshold=0.6667,
        native_token_price_usd=2.50,
        eth_price_usd=3200.00,
        challenger_bounty_pct=0.25,
        insurance_reserve_pct=0.45,
        burn_pct=0.30,
    )

    staking = StakingManager(config)
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)
    relay_engine = CrossChainRelayEngine(staking)

    # 1. Register operators
    op_alpha = staking.register_operator(
        operator_id="agent-alpha",
        did="did:agent:eth:0xaaaa",
        public_key="0xpub_alpha",
        native_stake=40000.0,
        restaked_eth=40.0,
    )
    op_beta = staking.register_operator(
        operator_id="agent-beta",
        did="did:agent:eth:0xbbbb",
        public_key="0xpub_beta",
        native_stake=40000.0,
        restaked_eth=40.0,
    )
    op_gamma = staking.register_operator(
        operator_id="agent-gamma",
        did="did:agent:eth:0xcccc",
        public_key="0xpub_gamma",
        native_stake=20000.0,
        restaked_eth=20.0,
    )

    total_security = staking.total_economic_security_usd()
    assert total_security == (100000.0 * 2.50) + (100.0 * 3200.00)

    # 2. Issue and verify W3C DID Credential with TEE claims
    claims = {
        "tee_type": "INTEL_TDX",
        "measurement_digest": "0x123456789abcdef",
        "model_weight_digest": "sha256:fedcba987654321",
    }
    vc = IdentityManager.issue_credential(
        issuer_did="did:agent:avs:governance",
        subject_did=op_alpha.did,
        claims=claims,
        secret_key="master_secret_key",
        ttl_seconds=3600.0,
    )
    is_valid, reason = IdentityManager.verify_credential(vc, "master_secret_key")
    assert is_valid is True
    assert reason is None

    is_tee_valid, tee_err = IdentityManager.validate_hardware_tee_claims(vc.claims)
    assert is_tee_valid is True
    assert tee_err is None

    # 3. Cross-chain state relay
    from agent_restaking_avs.models import CrossChainPacket
    raw_packet = CrossChainPacket(
        packet_id="pkt-bridge-001",
        source_chain_id=1,
        target_chain_id=42161,  # Arbitrum
        nonce=1,
        payload_hash="0xpayloadhash001",
        state_merkle_root="0xroot001",
    )
    packet = relay_engine.submit_packet(raw_packet)

    # Alpha (40%) + Beta (40%) = 80% > 66.67%
    relay_engine.attach_signature("pkt-bridge-001", "agent-alpha", "0xsig_alpha")
    relay_engine.attach_signature("pkt-bridge-001", "agent-beta", "0xsig_beta")

    executed, consensus_result = relay_engine.execute_relay("pkt-bridge-001")
    assert executed is True
    assert consensus_result.approved is True
    assert packet.executed is True
    assert relay_engine.is_nonce_executed(1, 42161, 1) is True

    # 4. Anti-replay test
    with pytest.raises(ReplayAttackError, match="Replay attack detected"):
        relay_engine.submit_packet(
            CrossChainPacket(
                packet_id="pkt-bridge-duplicate",
                source_chain_id=1,
                target_chain_id=42161,
                nonce=1,
                payload_hash="0xpayloadhash001",
                state_merkle_root="0xroot001",
            )
        )

    # 5. SLA Violation & Slashing
    receipt = TaskReceipt(
        task_id="task-sla-999",
        operator_id="agent-gamma",
        escrow_usd=2000.0,
        deadline=1000.0,
        expected_schema_hash="0xvalid_schema",
        actual_output_hash="0xinvalid_schema",
        allowed_tools=["read_file"],
        executed_tools=["read_file"],
        state_root="0xstate999",
        submitted_at=900.0,
    )
    tribunal.record_receipt(receipt)

    claim = FraudClaim(
        claim_id="claim-sla-999",
        challenger_did="did:agent:eth:0xwatchdog",
        operator_id="agent-gamma",
        task_id="task-sla-999",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH,
        bond_usd=300.0,
        evidence={"expected_schema_hash": "0xvalid_schema", "actual_output_hash": "0xinvalid_schema"},
    )
    tribunal.file_dispute(claim)

    is_guilty, resolved_type, slashing = tribunal.adjudicate("claim-sla-999")
    assert is_guilty is True
    assert resolved_type == DisputeType.HALLUCINATION_SCHEMA_MISMATCH
    assert slashing is not None

    # 40% slash on Gamma (20,000 * 0.40 = 8,000 native; 20 * 0.40 = 8 ETH)
    assert slashing.native_slashed == 8000.0
    assert slashing.eth_slashed == 8.0
    assert slashing.user_refund_usd == 2000.0

    # 6. Conservation Invariant Check
    total_slashed = slashing.total_slashed_usd
    expected_bounty = total_slashed * 0.25
    expected_insurance = total_slashed * 0.45
    expected_burn = total_slashed * 0.30
    assert slashing.challenger_bounty_usd == pytest.approx(expected_bounty, 0.01)
    assert slashing.insurance_reserve_usd == pytest.approx(expected_insurance, 0.01)
    assert slashing.burn_usd == pytest.approx(expected_burn, 0.01)
    assert (slashing.challenger_bounty_usd + slashing.insurance_reserve_usd + slashing.burn_usd) == pytest.approx(total_slashed, 0.01)

    # Gamma remaining: 12,000 native >= 10k, 12 ETH >= 10 ETH -> still ACTIVE
    assert op_gamma.native_stake == 12000.0
    assert op_gamma.restaked_eth == 12.0
    assert op_gamma.status == OperatorStatus.ACTIVE

    # 7. Second breach causes stake depletion below minimum -> JAILED
    receipt2 = TaskReceipt(
        task_id="task-sla-1000",
        operator_id="agent-gamma",
        escrow_usd=1000.0,
        deadline=1000.0,
        expected_schema_hash="0xvalid_schema",
        actual_output_hash="0xvalid_schema",
        allowed_tools=["read_file"],
        executed_tools=["read_file", "malicious_subshell"],
        state_root="0xstate1000",
        submitted_at=950.0,
    )
    tribunal.record_receipt(receipt2)

    claim2 = FraudClaim(
        claim_id="claim-sla-1000",
        challenger_did="did:agent:eth:0xwatchdog",
        operator_id="agent-gamma",
        task_id="task-sla-1000",
        dispute_type=DisputeType.UNAUTHORIZED_TOOL_EXECUTION,
        bond_usd=200.0,
        evidence={"allowed_tools": ["read_file"], "executed_tools": ["read_file", "malicious_subshell"]},
    )
    tribunal.file_dispute(claim2)
    _, _, slashing2 = tribunal.adjudicate("claim-sla-1000")
    assert slashing2 is not None
    # 50% slash on 12,000 native = 6,000 remaining (<10,000 min) -> JAILED
    assert op_gamma.native_stake == 6000.0
    assert op_gamma.restaked_eth == 6.0
    assert op_gamma.status == OperatorStatus.JAILED
    assert slashing2.operator_jailed is True

    # Replenish collateral and unjail
    waterfall.replenish_and_unjail("agent-gamma", native_amount=5000.0, eth_amount=5.0)
    assert op_gamma.native_stake == 11000.0
    assert op_gamma.restaked_eth == 11.0
    assert op_gamma.status == OperatorStatus.ACTIVE
