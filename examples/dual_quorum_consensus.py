#!/usr/bin/env python3
"""
Example: Dual-Quorum Consensus Verification in Agent Restaking AVS.
"""

from agent_restaking_avs import OperatorStatus, StakePoolConfig, StakingManager


def main() -> None:
    config = StakePoolConfig(
        min_native_stake=10000.0,
        min_eth_stake=10.0,
        consensus_threshold=0.6667,
    )
    staking = StakingManager(config)

    # Register heterogeneous validator operators
    op1 = staking.register_operator(
        operator_id="operator-alpha",
        did="did:agent:eth:0x1111111111111111111111111111111111111111",
        public_key="0xpub1",
        native_stake=50000.0,
        restaked_eth=50.0,
    )
    op2 = staking.register_operator(
        operator_id="operator-beta",
        did="did:agent:eth:0x2222222222222222222222222222222222222222",
        public_key="0xpub2",
        native_stake=30000.0,
        restaked_eth=30.0,
    )
    op3 = staking.register_operator(
        operator_id="operator-gamma",
        did="did:agent:eth:0x3333333333333333333333333333333333333333",
        public_key="0xpub3",
        native_stake=20000.0,
        restaked_eth=20.0,
    )

    print(f"Total Economic Security: ${staking.total_economic_security_usd():,.2f} USD")
    print(f"Active Operators: {len(staking.list_operators(OperatorStatus.ACTIVE))}")

    # Case A: Alpha + Beta sign (50% + 30% = 80% > 66.67%)
    res_a = staking.verify_dual_quorum(["operator-alpha", "operator-beta"])
    print(f"\nSigners [Alpha, Beta]: Approved={res_a.approved}")
    print(f" • Native Quorum: {res_a.native_pct:.2%}")
    print(f" • ETH Quorum: {res_a.eth_pct:.2%}")

    # Case B: Gamma alone signs (20% < 66.67%)
    res_b = staking.verify_dual_quorum(["operator-gamma"])
    print(f"\nSigners [Gamma]: Approved={res_b.approved}")
    print(f" • Rejection Reason: {res_b.rejection_reason}")


if __name__ == "__main__":
    main()
