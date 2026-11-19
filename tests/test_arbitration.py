"""
Tests for the deterministic SLA dispute arbitration tribunal.
"""

import pytest
from agent_restaking_avs.arbitration import ArbitrationTribunal
from agent_restaking_avs.models import (
    DisputeType,
    FraudClaim,
    OperatorStatus,
    TaskReceipt,
)
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


@pytest.fixture
def tribunal_setup():
    staking = StakingManager()
    staking.register_operator("op-agent", "did:agent:1", "0x1", 30000.0, 30.0)
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)
    return staking, waterfall, tribunal


def test_record_receipt_and_insufficient_bond(tribunal_setup):
    _, _, tribunal = tribunal_setup
    receipt = TaskReceipt(
        task_id="task-1",
        operator_id="op-agent",
        escrow_usd=1000.0,
        deadline=500.0,
        expected_schema_hash="0xexpected",
        actual_output_hash="0xactual",
        allowed_tools=["read"],
        executed_tools=["read"],
        state_root="0xroot",
    )
    tribunal.record_receipt(receipt)

    # Required bond is 10% of $1000 = $100
    claim_bad = FraudClaim(
        claim_id="claim-low-bond",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-1",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH,
        bond_usd=90.0,
        evidence={},
    )
    with pytest.raises(ValueError, match="10% minimum"):
        tribunal.file_dispute(claim_bad)


def test_adjudicate_byzantine_double_signing(tribunal_setup):
    staking, _, tribunal = tribunal_setup
    claim = FraudClaim(
        claim_id="claim-byz",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-any",
        dispute_type=DisputeType.BYZANTINE_DOUBLE_SIGNING,
        bond_usd=50.0,
        evidence={"root_1": "0xrootA", "root_2": "0xrootB"},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-byz")

    assert guilty is True
    assert resolved_type == DisputeType.BYZANTINE_DOUBLE_SIGNING
    assert slashing is not None
    assert slashing.permanent is True
    assert staking.get_operator("op-agent").status == OperatorStatus.SLASHED_PERMANENT


def test_adjudicate_unauthorized_tools(tribunal_setup):
    _, _, tribunal = tribunal_setup
    receipt = TaskReceipt(
        task_id="task-tools",
        operator_id="op-agent",
        escrow_usd=200.0,
        deadline=1000.0,
        expected_schema_hash="0xexp",
        actual_output_hash="0xexp",
        allowed_tools=["curl", "grep"],
        executed_tools=["curl", "grep", "eval_untrusted"],
        state_root="0x1",
    )
    tribunal.record_receipt(receipt)

    claim = FraudClaim(
        claim_id="claim-tools",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-tools",
        dispute_type=DisputeType.UNAUTHORIZED_TOOL_EXECUTION,
        bond_usd=25.0,
        evidence={},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-tools")

    assert guilty is True
    assert resolved_type == DisputeType.UNAUTHORIZED_TOOL_EXECUTION
    assert slashing is not None


def test_adjudicate_hallucination_mismatch(tribunal_setup):
    _, _, tribunal = tribunal_setup
    receipt = TaskReceipt(
        task_id="task-hal",
        operator_id="op-agent",
        escrow_usd=300.0,
        deadline=1000.0,
        expected_schema_hash="0xschema_valid",
        actual_output_hash="0xoutput_garbage",
        allowed_tools=["run"],
        executed_tools=["run"],
        state_root="0x1",
    )
    tribunal.record_receipt(receipt)

    claim = FraudClaim(
        claim_id="claim-hal",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-hal",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH,
        bond_usd=35.0,
        evidence={},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-hal")

    assert guilty is True
    assert resolved_type == DisputeType.HALLUCINATION_SCHEMA_MISMATCH


def test_adjudicate_liveness_timeout(tribunal_setup):
    _, _, tribunal = tribunal_setup
    receipt = TaskReceipt(
        task_id="task-late",
        operator_id="op-agent",
        escrow_usd=400.0,
        deadline=500.0,
        expected_schema_hash="0xok",
        actual_output_hash="0xok",
        allowed_tools=["run"],
        executed_tools=["run"],
        state_root="0x1",
        submitted_at=600.0,  # 100 seconds late
    )
    tribunal.record_receipt(receipt)

    claim = FraudClaim(
        claim_id="claim-late",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-late",
        dispute_type=DisputeType.LIVENESS_LATENCY_BREACH,
        bond_usd=50.0,
        evidence={},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-late")

    assert guilty is True
    assert resolved_type == DisputeType.LIVENESS_LATENCY_BREACH


def test_adjudicate_frivolous_claim(tribunal_setup):
    staking, waterfall, tribunal = tribunal_setup
    # Valid execution on time with allowed tools and matching hash
    receipt = TaskReceipt(
        task_id="task-clean",
        operator_id="op-agent",
        escrow_usd=500.0,
        deadline=1000.0,
        expected_schema_hash="0xclean",
        actual_output_hash="0xclean",
        allowed_tools=["run"],
        executed_tools=["run"],
        state_root="0x1",
        submitted_at=800.0,
    )
    tribunal.record_receipt(receipt)

    # Challenger files false schema mismatch
    claim = FraudClaim(
        claim_id="claim-false",
        challenger_did="did:challenger",
        operator_id="op-agent",
        task_id="task-clean",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH,
        bond_usd=60.0,
        evidence={},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-false")

    assert guilty is False
    assert resolved_type == DisputeType.FRIVOLOUS_CHALLENGE
    assert slashing is None
    # Operator was not slashed
    assert staking.get_operator("op-agent").status == OperatorStatus.ACTIVE
