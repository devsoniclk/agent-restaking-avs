"""
Example demonstrating cross-chain state relay and nonce anti-replay protection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_restaking_avs.models import CrossChainPacket
from agent_restaking_avs.relays import CrossChainRelayEngine, ReplayAttackError
from agent_restaking_avs.staking import StakingManager


def main():
    print("--- 1. Initializing Cross-Chain Relay Network ---")
    staking = StakingManager()
    staking.register_operator("op-relayer-1", "did:agent:eth:0xrelayer1", "0xpub1", 60000.0, 60.0)
    staking.register_operator("op-relayer-2", "did:agent:eth:0xrelayer2", "0xpub2", 40000.0, 40.0)
    engine = CrossChainRelayEngine(staking)

    print("--- 2. Submitting Packet (Ethereum -> Arbitrum) ---")
    packet = CrossChainPacket(
        packet_id="packet-eth-arb-001",
        source_chain_id=1,        # Ethereum Mainnet
        target_chain_id=42161,    # Arbitrum One
        nonce=101,
        payload_hash="0xintent_swap_dai_usdc",
        state_merkle_root="0xmerkle_root_state",
    )
    engine.submit_packet(packet)
    print(f"Packet submitted with key {packet.relay_key}")

    print("--- 3. Attaching Multi-Operator Signatures ---")
    engine.attach_signature("packet-eth-arb-001", "op-relayer-1", "0xsig_relayer_1")
    engine.attach_signature("packet-eth-arb-001", "op-relayer-2", "0xsig_relayer_2")

    print("--- 4. Executing Cross-Chain Relay ---")
    executed, consensus = engine.execute_relay("packet-eth-arb-001")
    print(f"Relay Executed: {executed}")
    print(f"Native Voting Weight: {consensus.native_pct:.1%}")
    print(f"ETH Voting Weight: {consensus.eth_pct:.1%}")

    print("--- 5. Simulating Replay Attack (Duplicate Nonce 101) ---")
    duplicate_packet = CrossChainPacket(
        packet_id="packet-replay-attempt",
        source_chain_id=1,
        target_chain_id=42161,
        nonce=101,  # Already used!
        payload_hash="0xmalicious_drain",
        state_merkle_root="0xbad_root",
    )
    try:
        engine.submit_packet(duplicate_packet)
    except ReplayAttackError as e:
        print(f"✔ Replay Attack Caught: {e}")


if __name__ == "__main__":
    main()
