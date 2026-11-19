"""
Cross-chain state relay coordinator and anti-replay protection.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Set, Tuple

from .models import ConsensusResult, CrossChainPacket
from .staking import StakingManager

logger = logging.getLogger(__name__)


class ReplayAttackError(Exception):
    """Raised when a duplicated cross-chain relay nonce is detected."""


class CrossChainRelayEngine:
    """Coordinates cross-chain state relays, validates dual-quorum consensus, and prevents replays."""

    def __init__(self, staking_manager: StakingManager) -> None:
        self.staking_manager = staking_manager
        self._packets: Dict[str, CrossChainPacket] = {}
        self._executed_relays: Set[str] = set()

    @property
    def packets(self) -> Dict[str, CrossChainPacket]:
        """Access registered cross-chain packets."""
        return self._packets

    def is_nonce_executed(self, source_chain_id: int, target_chain_id: int, nonce: int) -> bool:
        """Check if a specific channel nonce has previously been finalized."""
        key = f"{source_chain_id}:{target_chain_id}:{nonce}"
        return key in self._executed_relays

    def submit_packet(self, packet: CrossChainPacket) -> CrossChainPacket:
        """Submit a new cross-chain state relay packet."""
        if packet.source_chain_id == packet.target_chain_id:
            raise ValueError(
                f"Source chain {packet.source_chain_id} and target chain cannot be identical."
            )

        if self.is_nonce_executed(packet.source_chain_id, packet.target_chain_id, packet.nonce):
            raise ReplayAttackError(
                f"Replay attack detected: Nonce {packet.nonce} on channel "
                f"{packet.source_chain_id}->{packet.target_chain_id} already executed."
            )

        if packet.packet_id in self._packets:
            raise ValueError(f"Packet ID {packet.packet_id} already exists.")

        self._packets[packet.packet_id] = packet
        return packet

    def attach_signature(self, packet_id: str, operator_id: str, signature: str) -> None:
        """Attach an operator's attestation signature to an existing packet."""
        if packet_id not in self._packets:
            raise KeyError(f"Packet {packet_id} not found.")

        packet = self._packets[packet_id]
        if packet.executed:
            raise ValueError(f"Packet {packet_id} has already been executed.")

        operator = self.staking_manager.get_operator(operator_id)
        if not operator.is_active():
            raise ValueError(
                f"Operator {operator_id} is in status {operator.status.value} and cannot sign relays."
            )

        packet.signatures[operator_id] = signature

    def execute_relay(self, packet_id: str) -> Tuple[bool, ConsensusResult]:
        """
        Execute cross-chain relay if dual-quorum consensus is satisfied.
        
        Returns (executed_bool, ConsensusResult).
        """
        if packet_id not in self._packets:
            raise KeyError(f"Packet {packet_id} not found.")

        packet = self._packets[packet_id]
        if packet.executed:
            raise ValueError(f"Packet {packet_id} is already marked executed.")

        # Re-check replay defense right before execution
        if self.is_nonce_executed(packet.source_chain_id, packet.target_chain_id, packet.nonce):
            raise ReplayAttackError(
                f"Replay attack detected: Nonce {packet.nonce} on channel "
                f"{packet.source_chain_id}->{packet.target_chain_id} was already executed."
            )

        signers = list(packet.signatures.keys())
        consensus = self.staking_manager.verify_dual_quorum(signers)

        if not consensus.approved:
            logger.warning(
                "Packet %s failed dual-quorum consensus: %s",
                packet_id,
                consensus.rejection_reason,
            )
            return False, consensus

        # Mark packet as executed and record nonce in anti-replay ledger
        packet.executed = True
        self._executed_relays.add(packet.relay_key)
        logger.info(
            "Packet %s executed successfully on channel %s",
            packet_id,
            packet.relay_key,
        )
        return True, consensus
