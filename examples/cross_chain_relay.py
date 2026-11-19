#!/usr/bin/env python3
"""
Example: Cross-Chain State Relay with Anti-Replay Protection.
"""

from agent_restaking_avs import (
    CrossChainPacket,
    CrossChainRelayEngine,
    StakePoolConfig,
    StakingManager,
)
from agent_restaking_avs.relays import ReplayAttackError


def main() -> None:
    config = StakePoolConfig()
    staking = StakingManager(config)
    relay = CrossChainRelayEngine(staking)

    # Register validators
    staking.register_operator("val-1", "did:agent:eth:0x1", "0xpub1", 50000.0, 50.0)
    staking.register_operator("val-2", "did:agent:eth:0x2", "0xpub2", 50000.0, 50.0)

    # 1. Submit packet for cross-chain execution (Ethereum -> Base)
    packet = CrossChainPacket(
        packet_id="pkt-relay-42",
        source_chain_id=1,        # Ethereum
        target_chain_id=8453,     # Base
        nonce=101,
        payload_hash="0xde0b6b3a7640000",
        state_merkle_root="0xmerkle_root_state",
    )
    relay.submit_packet(packet)
    print(f"Submitted Packet: {packet.packet_id} on Channel {packet.relay_key}")

    # 2. Collect validator signatures
    relay.attach_signature("pkt-relay-42", "val-1", "0xsig1")
    relay.attach_signature("pkt-relay-42", "val-2", "0xsig2")

    # 3. Execute cross-chain relay
    executed, consensus = relay.execute_relay("pkt-relay-42")
    print(f"Relay Execution: Executed={executed}, Dual-Quorum Consensus Approved={consensus.approved}")

    # 4. Attempt replay attack
    print("\nAttempting Duplicate Relay Submission (Replay Attack)...")
    try:
        dup = CrossChainPacket(
            packet_id="pkt-replay-hack",
            source_chain_id=1,
            target_chain_id=8453,
            nonce=101,  # Same nonce on same channel
            payload_hash="0xhacked_payload",
            state_merkle_root="0xroot",
        )
        relay.submit_packet(dup)
    except ReplayAttackError as e:
        print(f"✔ Cryptographic Defense Blocked Replay: {e}")


if __name__ == "__main__":
    main()
