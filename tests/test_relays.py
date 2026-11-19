"""
Tests for cross-chain state relays and anti-replay mechanics.
"""

import pytest
from agent_restaking_avs.models import CrossChainPacket, OperatorStatus
from agent_restaking_avs.relays import CrossChainRelayEngine, ReplayAttackError
from agent_restaking_avs.staking import StakingManager


@pytest.fixture
def relay_setup():
    staking = StakingManager()
    staking.register_operator("op-1", "did:1", "0x1", 70000.0, 70.0)
    staking.register_operator("op-2", "did:2", "0x2", 30000.0, 30.0)
    engine = CrossChainRelayEngine(staking)
    return staking, engine


def test_submit_valid_packet(relay_setup):
    _, engine = relay_setup
    packet = CrossChainPacket(
        packet_id="pkt-1",
        source_chain_id=1,
        target_chain_id=10,
        nonce=1,
        payload_hash="0xhash",
        state_merkle_root="0xmerkle",
    )
    engine.submit_packet(packet)
    assert "pkt-1" in engine.packets


def test_submit_same_chain_rejected(relay_setup):
    _, engine = relay_setup
    packet = CrossChainPacket(
        packet_id="pkt-bad",
        source_chain_id=1,
        target_chain_id=1,
        nonce=1,
        payload_hash="0xhash",
        state_merkle_root="0xmerkle",
    )
    with pytest.raises(ValueError, match="cannot be identical"):
        engine.submit_packet(packet)


def test_attach_signature_and_execute(relay_setup):
    staking, engine = relay_setup
    packet = CrossChainPacket(
        packet_id="pkt-exec",
        source_chain_id=1,
        target_chain_id=42161,
        nonce=50,
        payload_hash="0xpayload",
        state_merkle_root="0xroot",
    )
    engine.submit_packet(packet)

    # Attach signature from op-1 (has 70% stake, exceeds 66.67% threshold)
    engine.attach_signature("pkt-exec", "op-1", "0xsignature1")

    executed, consensus = engine.execute_relay("pkt-exec")
    assert executed is True
    assert consensus.approved is True
    assert packet.executed is True
    assert engine.is_nonce_executed(1, 42161, 50) is True


def test_replay_attack_prevention(relay_setup):
    staking, engine = relay_setup
    packet1 = CrossChainPacket(
        packet_id="pkt-100",
        source_chain_id=1,
        target_chain_id=8453,
        nonce=99,
        payload_hash="0xpayload",
        state_merkle_root="0xroot",
    )
    engine.submit_packet(packet1)
    engine.attach_signature("pkt-100", "op-1", "0xsig")
    executed, _ = engine.execute_relay("pkt-100")
    assert executed is True

    # Attempt to submit another packet with the exact same nonce
    packet2 = CrossChainPacket(
        packet_id="pkt-101",
        source_chain_id=1,
        target_chain_id=8453,
        nonce=99,
        payload_hash="0xdifferent",
        state_merkle_root="0xdifferent_root",
    )
    with pytest.raises(ReplayAttackError, match="Replay attack detected"):
        engine.submit_packet(packet2)


def test_jailed_operator_cannot_sign(relay_setup):
    staking, engine = relay_setup
    staking.get_operator("op-2").status = OperatorStatus.JAILED
    packet = CrossChainPacket(
        packet_id="pkt-jailed",
        source_chain_id=1,
        target_chain_id=10,
        nonce=2,
        payload_hash="0x1",
        state_merkle_root="0x2",
    )
    engine.submit_packet(packet)

    with pytest.raises(ValueError, match="cannot sign relays"):
        engine.attach_signature("pkt-jailed", "op-2", "0xsig")
