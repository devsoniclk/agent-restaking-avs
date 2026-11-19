"""
Targeted tests for edge cases to achieve >99% code coverage.
"""

import pytest
from agent_restaking_avs.arbitration import ArbitrationTribunal
from agent_restaking_avs.models import (
    CrossChainPacket,
    DisputeType,
    FraudClaim,
    StakePoolConfig,
    TaskReceipt,
)
from agent_restaking_avs.relays import CrossChainRelayEngine, ReplayAttackError
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


def test_arbitration_edge_cases():
    staking = StakingManager()
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)

    # 1. Receipt with unregistered operator (line 38)
    receipt = TaskReceipt(
        task_id="task-unknown",
        operator_id="op-ghost",
        escrow_usd=100.0,
        deadline=500.0,
        expected_schema_hash="h1",
        actual_output_hash="h1",
        allowed_tools=[],
        executed_tools=[],
        state_root="0x1",
    )
    tribunal.record_receipt(receipt)
    assert "task-unknown" in tribunal.receipts

    # 2. Duplicate claim_id (line 43)
    claim1 = FraudClaim(
        claim_id="claim-dup",
        challenger_did="did:1",
        operator_id="op-ghost",
        task_id="task-unknown",
        dispute_type=DisputeType.FRIVOLOUS_CHALLENGE,
        bond_usd=50.0,
        evidence={},
    )
    tribunal.file_dispute(claim1)
    with pytest.raises(ValueError, match="already exists"):
        tribunal.file_dispute(claim1)

    # 3. Adjudicate non-existent claim (line 52)
    with pytest.raises(KeyError, match="not found"):
        tribunal.adjudicate("non-existent-claim")

    # 4. Byzantine claim with missing roots (line 67)
    claim_bad_byz = FraudClaim(
        claim_id="claim-byz-empty",
        challenger_did="did:1",
        operator_id="op-ghost",
        task_id="task-unknown",
        dispute_type=DisputeType.BYZANTINE_DOUBLE_SIGNING,
        bond_usd=20.0,
        evidence={"root_1": "", "root_2": ""},
    )
    tribunal.file_dispute(claim_bad_byz)
    guilty, _, _ = tribunal.adjudicate("claim-byz-empty")
    assert guilty is False

    # 5. Liveness claim where task was submitted on time (line 80)
    receipt_ontime = TaskReceipt(
        task_id="task-ontime",
        operator_id="op-ghost",
        escrow_usd=100.0,
        deadline=1000.0,
        expected_schema_hash="h",
        actual_output_hash="h",
        allowed_tools=[],
        executed_tools=[],
        state_root="0x1",
        submitted_at=900.0,  # on time
    )
    tribunal.record_receipt(receipt_ontime)
    claim_ontime = FraudClaim(
        claim_id="claim-ontime",
        challenger_did="did:1",
        operator_id="op-ghost",
        task_id="task-ontime",
        dispute_type=DisputeType.LIVENESS_LATENCY_BREACH,
        bond_usd=20.0,
        evidence={},
    )
    tribunal.file_dispute(claim_ontime)
    assert len(tribunal.claims) == 3
    guilty_late, _, _ = tribunal.adjudicate("claim-ontime")
    assert guilty_late is False


def test_relays_edge_cases():
    staking = StakingManager()
    staking.register_operator("op-1", "did:1", "0x1", 50000.0, 50.0)
    engine = CrossChainRelayEngine(staking)

    # 1. Duplicate packet_id (line 52)
    p = CrossChainPacket("pkt-dup", 1, 10, 1, "0x1", "0x2")
    engine.submit_packet(p)
    with pytest.raises(ValueError, match="already exists"):
        engine.submit_packet(p)

    # 2. Attach signature to missing packet (line 60)
    with pytest.raises(KeyError, match="not found"):
        engine.attach_signature("missing-pkt", "op-1", "0xsig")

    # 3. Attach signature to executed packet (line 64)
    p.executed = True
    with pytest.raises(ValueError, match="already been executed"):
        engine.attach_signature("pkt-dup", "op-1", "0xsig")

    # 4. Execute missing packet (line 81)
    with pytest.raises(KeyError, match="not found"):
        engine.execute_relay("ghost-pkt")

    # 5. Execute already executed packet (line 85)
    with pytest.raises(ValueError, match="already marked executed"):
        engine.execute_relay("pkt-dup")

    # 6. Replay check right before execution (line 89)
    p2 = CrossChainPacket("pkt-pre-replay", 1, 10, 2, "0x1", "0x2")
    engine.submit_packet(p2)
    engine._executed_relays.add(p2.relay_key)
    with pytest.raises(ReplayAttackError, match="was already executed"):
        engine.execute_relay("pkt-pre-replay")


    # 7. Execute packet failing consensus
    p3 = CrossChainPacket("pkt-fail-consensus", 1, 10, 3, "0x1", "0x2")
    engine.submit_packet(p3)
    # op-low only has 10% stake
    staking.register_operator("op-low", "did:low", "0xlow", 10000.0, 10.0)
    engine.attach_signature("pkt-fail-consensus", "op-low", "0xsig_low")
    success, res = engine.execute_relay("pkt-fail-consensus")
    assert success is False
    assert res.approved is False
    assert not p3.executed


def test_staking_edge_cases():
    staking = StakingManager()
    assert len(staking.operators) == 0
    with pytest.raises(KeyError, match="not found"):
        staking.get_operator("non-existent-operator")

    # Empty network consensus (line 125)
    res = staking.verify_dual_quorum(["ghost-op"])
    assert res.approved is False
    assert "No active stake available" in res.rejection_reason

    # Single quorum failure: Quorum 2 fails (line 171)
    staking.register_operator("op-high-native", "did:hn", "0xhn", 100000.0, 10.0)
    staking.register_operator("op-high-eth", "did:he", "0xhe", 10000.0, 100.0)
    # op-high-native has 100k/110k = 90.9% native (passes), but 10/110 = 9.1% ETH (fails)
    res_q2_fail = staking.verify_dual_quorum(["op-high-native"])
    assert res_q2_fail.approved is False
    assert "Quorum 2 (ETH:" in res_q2_fail.rejection_reason
