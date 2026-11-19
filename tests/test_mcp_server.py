"""
Tests for Agent Restaking FastMCP Server implementation.
"""

import pytest
from agent_restaking_avs.mcp_server import AgentRestakingMCPServer
from agent_restaking_avs.models import DisputeType, OperatorStatus, StakePoolConfig


@pytest.fixture
def mcp_server() -> AgentRestakingMCPServer:
    server = AgentRestakingMCPServer()
    # Register 3 baseline operators
    server.register_operator(
        operator_id="op-1",
        did="did:agent:eth:0x1111111111111111111111111111111111111111",
        public_key="0xpub1",
        native_stake=50000.0,
        restaked_eth=50.0,
    )
    server.register_operator(
        operator_id="op-2",
        did="did:agent:eth:0x2222222222222222222222222222222222222222",
        public_key="0xpub2",
        native_stake=30000.0,
        restaked_eth=30.0,
    )
    server.register_operator(
        operator_id="op-3",
        did="did:agent:eth:0x3333333333333333333333333333333333333333",
        public_key="0xpub3",
        native_stake=20000.0,
        restaked_eth=20.0,
    )
    return server


def test_mcp_get_network_status(mcp_server: AgentRestakingMCPServer):
    status = mcp_server.get_network_status()
    assert status["active_operators_count"] == 3
    assert status["jailed_operators_count"] == 0
    assert status["permanently_slashed_count"] == 0
    assert status["total_economic_security_usd"] == (100000.0 * 2.50) + (100.0 * 3200.00)
    assert status["consensus_threshold_pct"] == pytest.approx(66.67)


def test_mcp_register_operator(mcp_server: AgentRestakingMCPServer):
    res = mcp_server.register_operator(
        operator_id="op-new",
        did="did:agent:eth:0x999",
        public_key="0xpub999",
        native_stake=15000.0,
        restaked_eth=12.0,
    )
    assert res["status"] == "success"
    assert res["operator_id"] == "op-new"
    assert res["operator_status"] == OperatorStatus.ACTIVE.value
    assert res["native_stake"] == 15000.0
    assert res["restaked_eth"] == 12.0


def test_mcp_verify_consensus(mcp_server: AgentRestakingMCPServer):
    # op-1 (50%) + op-2 (30%) = 80% > 66.67%
    approved_res = mcp_server.verify_consensus(["op-1", "op-2"])
    assert approved_res["approved"] is True
    assert approved_res["native_pct"] == 80.0
    assert approved_res["eth_pct"] == 80.0
    assert approved_res["valid_signers_count"] == 2

    # op-3 alone = 20% < 66.67%
    rejected_res = mcp_server.verify_consensus(["op-3"])
    assert rejected_res["approved"] is False
    assert rejected_res["native_pct"] == 20.0
    assert "failed threshold" in rejected_res["rejection_reason"]


def test_mcp_submit_task_receipt_and_dispute(mcp_server: AgentRestakingMCPServer):
    # Submit valid receipt with unauthorized tool execution
    submit_res = mcp_server.submit_task_receipt(
        task_id="task-mcp-100",
        operator_id="op-3",
        escrow_usd=1000.0,
        deadline=5000.0,
        expected_schema_hash="schema_001",
        actual_output_hash="schema_001",
        allowed_tools=["calculator"],
        executed_tools=["calculator", "unauthorized_exec"],
        state_root="0xroot100",
    )
    assert submit_res["status"] == "recorded"
    assert submit_res["task_id"] == "task-mcp-100"

    # File dispute
    dispute_res = mcp_server.file_and_adjudicate_dispute(
        claim_id="claim-mcp-100",
        challenger_did="did:agent:eth:0xchallenger",
        operator_id="op-3",
        task_id="task-mcp-100",
        dispute_type=DisputeType.UNAUTHORIZED_TOOL_EXECUTION.value,
        bond_usd=150.0,
        evidence={"allowed_tools": ["calculator"], "executed_tools": ["calculator", "unauthorized_exec"]},
    )
    assert dispute_res["claim_id"] == "claim-mcp-100"
    assert dispute_res["is_guilty"] is True
    assert dispute_res["resolved_dispute_type"] == DisputeType.UNAUTHORIZED_TOOL_EXECUTION.value
    assert "slashing" in dispute_res

    slashing = dispute_res["slashing"]
    assert slashing["total_slashed_usd"] > 0
    assert slashing["user_refund_usd"] == 1000.0
    assert slashing["challenger_bounty_usd"] == pytest.approx(slashing["total_slashed_usd"] * 0.25, 0.01)
    assert slashing["insurance_reserve_usd"] == pytest.approx(slashing["total_slashed_usd"] * 0.45, 0.01)
    assert slashing["burn_usd"] == pytest.approx(slashing["total_slashed_usd"] * 0.30, 0.01)


def test_mcp_frivolous_dispute_forfeiture(mcp_server: AgentRestakingMCPServer):
    # Submit clean receipt
    mcp_server.submit_task_receipt(
        task_id="task-clean-01",
        operator_id="op-1",
        escrow_usd=500.0,
        deadline=9999999999.0,
        expected_schema_hash="schema_clean",
        actual_output_hash="schema_clean",
        allowed_tools=["search"],
        executed_tools=["search"],
        state_root="0xroot_clean",
    )

    # File bogus claim
    dispute_res = mcp_server.file_and_adjudicate_dispute(
        claim_id="claim-bogus-01",
        challenger_did="did:agent:eth:0xbadchallenger",
        operator_id="op-1",
        task_id="task-clean-01",
        dispute_type=DisputeType.HALLUCINATION_SCHEMA_MISMATCH.value,
        bond_usd=100.0,
        evidence={"expected": "schema_clean", "actual": "schema_clean"},
    )
    assert dispute_res["is_guilty"] is False
    assert dispute_res["resolved_dispute_type"] == DisputeType.FRIVOLOUS_CHALLENGE.value
