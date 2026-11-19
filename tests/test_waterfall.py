"""
Tests for the multi-tranche collateral slashing waterfall and conservation.
"""

import pytest
from agent_restaking_avs.models import DisputeType, OperatorStatus, StakePoolConfig
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


@pytest.fixture
def waterfall_setup():
    config = StakePoolConfig(
        min_native_stake=10000.0,
        min_eth_stake=10.0,
        native_token_price_usd=2.50,
        eth_price_usd=3200.00,
        challenger_bounty_pct=0.25,
        insurance_reserve_pct=0.45,
        burn_pct=0.30,
    )
    staking = StakingManager(config)
    staking.register_operator("op-victim", "did:v", "0xv", 20000.0, 20.0)
    waterfall = SlashingWaterfallEngine(staking)
    return staking, waterfall


def test_slashing_mathematical_conservation(waterfall_setup):
    staking, waterfall = waterfall_setup
    # Initial: 20,000 * 2.50 = $50,000 + 20 * 3,200 = $64,000 -> Total $114,000
    # Execute 50% slash (UNAUTHORIZED_TOOL_EXECUTION)
    receipt = waterfall.execute_slashing("op-victim", DisputeType.UNAUTHORIZED_TOOL_EXECUTION, escrow_usd=1000.0)

    # 50% slashed: 10,000 tokens ($25,000) + 10 ETH ($32,000) = $57,000
    assert receipt.total_slashed_usd == 57000.0
    assert receipt.native_slashed == 10000.0
    assert receipt.eth_slashed == 10.0

    # Conservation: Bounty (25%) + Insurance (45%) + Burn (30%) == Total Slashed
    alloc_sum = round(receipt.challenger_bounty_usd + receipt.insurance_reserve_usd + receipt.burn_usd, 2)
    assert alloc_sum == receipt.total_slashed_usd
    assert receipt.challenger_bounty_usd == 14250.0  # 25% of 57,000
    assert receipt.insurance_reserve_usd == 25650.0 # 45% of 57,000
    assert receipt.burn_usd == 17100.0              # 30% of 57,000
    assert receipt.user_refund_usd == 1000.0


def test_jailing_on_stake_depletion(waterfall_setup):
    staking, waterfall = waterfall_setup
    # Operator has exactly 20,000 tokens and 20 ETH
    # A 50% slash leaves 10,000 tokens and 10 ETH (still active)
    r1 = waterfall.execute_slashing("op-victim", DisputeType.UNAUTHORIZED_TOOL_EXECUTION)
    assert r1.operator_jailed is False
    assert staking.get_operator("op-victim").status == OperatorStatus.ACTIVE

    # Another 15% latency penalty drops tokens to 8,500 and ETH to 8.5 (below 10,000 and 10 ETH)
    r2 = waterfall.execute_slashing("op-victim", DisputeType.LIVENESS_LATENCY_BREACH)
    assert r2.operator_jailed is True
    assert staking.get_operator("op-victim").status == OperatorStatus.JAILED


def test_byzantine_permanent_slashing(waterfall_setup):
    staking, waterfall = waterfall_setup
    receipt = waterfall.execute_slashing("op-victim", DisputeType.BYZANTINE_DOUBLE_SIGNING)
    assert receipt.total_slashed_usd == 114000.0
    assert receipt.permanent is True
    assert receipt.operator_jailed is True
    assert staking.get_operator("op-victim").status == OperatorStatus.SLASHED_PERMANENT

    # Attempt to replenish must be blocked
    with pytest.raises(PermissionError, match="permanently blacklisted"):
        waterfall.replenish_and_unjail("op-victim", native_amount=50000.0, eth_amount=50.0)


def test_replenish_and_unjail_regular_operator(waterfall_setup):
    staking, waterfall = waterfall_setup
    # Drop operator into JAILED status
    waterfall.execute_slashing("op-victim", DisputeType.UNAUTHORIZED_TOOL_EXECUTION)
    waterfall.execute_slashing("op-victim", DisputeType.LIVENESS_LATENCY_BREACH)
    op = staking.get_operator("op-victim")
    assert op.status == OperatorStatus.JAILED

    # Replenish collateral above minimums
    waterfall.replenish_and_unjail("op-victim", native_amount=5000.0, eth_amount=5.0)
    assert op.status == OperatorStatus.ACTIVE
    assert op.native_stake >= staking.config.min_native_stake
    assert op.restaked_eth >= staking.config.min_eth_stake


def test_frivolous_forfeiture(waterfall_setup):
    _, waterfall = waterfall_setup
    op_comp, ins = waterfall.execute_frivolous_forfeiture("op-victim", bond_usd=100.0)
    assert op_comp == 50.0
    assert ins == 50.0
    assert waterfall.total_insurance_collected_usd == 50.0
