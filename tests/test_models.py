"""
Tests for AVS protocol data models and configuration.
"""

import time
import pytest
from agent_restaking_avs.models import (
    ConsensusResult,
    CrossChainPacket,
    DisputeType,
    Operator,
    OperatorStatus,
    PENALTY_RATES,
    StakePoolConfig,
    VerifiableCredential,
)


def test_penalty_rates_completeness():
    assert PENALTY_RATES[DisputeType.BYZANTINE_DOUBLE_SIGNING] == 1.00
    assert PENALTY_RATES[DisputeType.UNAUTHORIZED_TOOL_EXECUTION] == 0.50
    assert PENALTY_RATES[DisputeType.HALLUCINATION_SCHEMA_MISMATCH] == 0.40
    assert PENALTY_RATES[DisputeType.LIVENESS_LATENCY_BREACH] == 0.15
    assert PENALTY_RATES[DisputeType.FRIVOLOUS_CHALLENGE] == 1.00


def test_operator_lifecycle_states():
    op = Operator(
        operator_id="op-1",
        did="did:agent:eth:0x1",
        public_key="0xpub1",
        native_stake=15000.0,
        restaked_eth=15.0,
    )
    assert op.is_active() is True
    op.status = OperatorStatus.JAILED
    assert op.is_active() is False
    op.status = OperatorStatus.SLASHED_PERMANENT
    assert op.is_active() is False


def test_stake_pool_config_defaults():
    config = StakePoolConfig()
    assert config.min_native_stake == 10000.0
    assert config.min_eth_stake == 10.0
    assert config.consensus_threshold == 0.6667
    assert config.challenger_bounty_pct == 0.25
    assert config.insurance_reserve_pct == 0.45
    assert config.burn_pct == 0.30


def test_verifiable_credential_expiry():
    now = time.time()
    vc = VerifiableCredential(
        credential_id="vc-test",
        issuer_did="did:agent:eth:0xissuer",
        subject_did="did:agent:eth:0xsubject",
        claims={"tee": "INTEL_TDX"},
        issued_at=now - 200,
        expires_at=now - 50,
        signature="0xsig",
    )
    assert vc.is_expired(now) is True
    assert vc.is_expired(now - 100) is False


def test_cross_chain_packet_relay_key():
    packet = CrossChainPacket(
        packet_id="pkt-1",
        source_chain_id=1,
        target_chain_id=42161,
        nonce=104,
        payload_hash="0xhash",
        state_merkle_root="0xroot",
    )
    assert packet.relay_key == "1:42161:104"
    assert packet.executed is False
