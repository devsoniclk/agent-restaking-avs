"""
Example demonstrating dual-quorum threshold consensus with native tokens and restaked ETH.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.models import StakePoolConfig


def main():
    print("--- 1. Initializing AVS Staking Pool ---")
    config = StakePoolConfig(
        min_native_stake=10000.0,
        min_eth_stake=10.0,
        consensus_threshold=0.6667,
    )
    staking = StakingManager(config)

    # Register autonomous agent operators
    staking.register_operator(
        operator_id="agent-claude",
        did="did:agent:eth:0x1111111111111111111111111111111111111111",
        public_key="0xclaude_pubkey",
        native_stake=50000.0,
        restaked_eth=50.0,
    )
    staking.register_operator(
        operator_id="agent-deepseek",
        did="did:agent:eth:0x2222222222222222222222222222222222222222",
        public_key="0xdeepseek_pubkey",
        native_stake=30000.0,
        restaked_eth=30.0,
    )
    staking.register_operator(
        operator_id="agent-llama",
        did="did:agent:eth:0x3333333333333333333333333333333333333333",
        public_key="0xllama_pubkey",
        native_stake=20000.0,
        restaked_eth=20.0,
    )

    total_security = staking.total_economic_security_usd()
    print(f"Total Blended Economic Security: ${total_security:,.2f} USD\n")

    print("--- 2. Checking Consensus: Claude + DeepSeek Sign ---")
    res1 = staking.verify_dual_quorum(["agent-claude", "agent-deepseek"])
    print(f"Native Stake Participation: {res1.native_pct:.1%}")
    print(f"Restaked ETH Participation: {res1.eth_pct:.1%}")
    print(f"Consensus Approved? {res1.approved}\n")

    print("--- 3. Checking Consensus: Llama Alone Signs ---")
    res2 = staking.verify_dual_quorum(["agent-llama"])
    print(f"Native Stake Participation: {res2.native_pct:.1%}")
    print(f"Restaked ETH Participation: {res2.eth_pct:.1%}")
    print(f"Consensus Approved? {res2.approved}")
    print(f"Reason: {res2.rejection_reason}")


if __name__ == "__main__":
    main()
