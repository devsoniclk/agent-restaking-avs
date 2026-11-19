"""
Tests for staking manager, dual-quorum calculations, and operator lifecycle.
"""

import pytest
from agent_restaking_avs.models import OperatorStatus, StakePoolConfig
from agent_restaking_avs.staking import StakingManager


def test_operator_registration_success():
    manager = StakingManager()
    op = manager.register_operator(
        operator_id="op-1",
        did="did:agent:eth:0x1",
        public_key="0xpub1",
        native_stake=10000.0,
        restaked_eth=10.0,
    )
    assert op.operator_id == "op-1"
    assert op.status == OperatorStatus.ACTIVE
    assert manager.get_operator("op-1") == op


def test_registration_validation_errors():
    manager = StakingManager()
    # Below min native
    with pytest.raises(ValueError, match="below required minimum"):
        manager.register_operator("op-bad1", "did:1", "0x1", 9999.0, 10.0)

    # Below min ETH
    with pytest.raises(ValueError, match="below required minimum"):
        manager.register_operator("op-bad2", "did:2", "0x2", 10000.0, 9.9)

    # Register valid
    manager.register_operator("op-valid", "did:valid", "0x3", 10000.0, 10.0)

    # Duplicate operator_id
    with pytest.raises(ValueError, match="already registered"):
        manager.register_operator("op-valid", "did:other", "0x4", 10000.0, 10.0)

    # Duplicate DID
    with pytest.raises(ValueError, match="already registered"):
        manager.register_operator("op-other", "did:valid", "0x5", 10000.0, 10.0)


def test_deposit_collateral():
    manager = StakingManager()
    manager.register_operator("op-1", "did:1", "0x1", 10000.0, 10.0)
    new_native = manager.deposit_native("op-1", 5000.0)
    assert new_native == 15000.0
    new_eth = manager.deposit_eth("op-1", 5.0)
    assert new_eth == 15.0

    with pytest.raises(ValueError, match="positive"):
        manager.deposit_native("op-1", -10)
    with pytest.raises(ValueError, match="positive"):
        manager.deposit_eth("op-1", 0)


def test_total_economic_security_calculation():
    config = StakePoolConfig(native_token_price_usd=2.0, eth_price_usd=3000.0)
    manager = StakingManager(config)
    manager.register_operator("op-1", "did:1", "0x1", 10000.0, 10.0)  # 20k + 30k = 50k
    manager.register_operator("op-2", "did:2", "0x2", 20000.0, 20.0)  # 40k + 60k = 100k

    assert manager.total_economic_security_usd() == 150000.0

    # If op-2 is jailed, its stake is excluded from active economic security
    manager.get_operator("op-2").status = OperatorStatus.JAILED
    assert manager.total_economic_security_usd() == 50000.0


def test_dual_quorum_consensus_scenarios():
    config = StakePoolConfig(consensus_threshold=0.6667)
    manager = StakingManager(config)

    # Setup 3 operators
    # Total Active: Native = 100,000, ETH = 100.0
    manager.register_operator("op-alpha", "did:a", "0xa", 50000.0, 50.0)  # 50%
    manager.register_operator("op-beta", "did:b", "0xb", 30000.0, 30.0)   # 30%
    manager.register_operator("op-gamma", "did:c", "0xc", 20000.0, 20.0)  # 20%

    # Scenario 1: Alpha + Beta sign (50k+30k=80k => 80% native, 50+30=80 => 80% ETH)
    res1 = manager.verify_dual_quorum(["op-alpha", "op-beta"])
    assert res1.approved is True
    assert res1.native_pct == 0.80
    assert res1.eth_pct == 0.80
    assert res1.rejection_reason is None

    # Scenario 2: Beta + Gamma sign (30k+20k=50k => 50% native, 50% ETH) -> fails both
    res2 = manager.verify_dual_quorum(["op-beta", "op-gamma"])
    assert res2.approved is False
    assert "Both Quorum 1" in (res2.rejection_reason or "")

    # Scenario 3: Asymmetric stake distribution
    manager.deposit_native("op-gamma", 50000.0)  # Total native: 150,000, op-gamma has 70,000
    # Alpha has 50k/150k = 33.3% native, but 50/100 = 50% ETH
    # Alpha + Beta: Native = 80k/150k = 53.33% (fails), ETH = 80/100 = 80% (passes)
    res3 = manager.verify_dual_quorum(["op-alpha", "op-beta"])
    assert res3.approved is False
    assert "Quorum 1" in (res3.rejection_reason or "")


def test_consensus_with_jailed_or_invalid_signers():
    manager = StakingManager()
    manager.register_operator("op-1", "did:1", "0x1", 60000.0, 60.0)
    manager.register_operator("op-2", "did:2", "0x2", 40000.0, 40.0)

    # Jail op-1
    manager.get_operator("op-1").status = OperatorStatus.JAILED
    # op-2 is now 100% of the active stake!
    res = manager.verify_dual_quorum(["op-2"])
    assert res.approved is True

    # op-1 signing while jailed adds 0 weight
    res_jailed = manager.verify_dual_quorum(["op-1"])
    assert res_jailed.approved is False
