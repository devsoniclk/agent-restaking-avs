"""
Multi-tranche collateral slashing waterfall and economic conservation engine.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

from .models import (
    DisputeType,
    Operator,
    OperatorStatus,
    PENALTY_RATES,
    SlashingReceipt,
)
from .staking import StakingManager

logger = logging.getLogger(__name__)


class SlashingWaterfallEngine:
    """Executes deterministic collateral liquidation with mathematical conservation."""

    def __init__(self, staking_manager: StakingManager) -> None:
        self.staking_manager = staking_manager
        self.config = staking_manager.config
        self.total_bounties_paid_usd = 0.0
        self.total_insurance_collected_usd = 0.0
        self.total_burned_usd = 0.0
        self.total_refunds_usd = 0.0

    def execute_slashing(
        self,
        operator_id: str,
        dispute_type: DisputeType,
        escrow_usd: float = 0.0,
    ) -> SlashingReceipt:
        """
        Execute statutory slashing waterfall against an operator's dual collateral.
        
        Conservation Invariant:
        Total Slashed == Challenger Bounty (25%) + Insurance Reserve (45%) + Burn (30%)
        """
        operator = self.staking_manager.get_operator(operator_id)
        rate = PENALTY_RATES[dispute_type]

        native_slashed = round(operator.native_stake * rate, 4)
        eth_slashed = round(operator.restaked_eth * rate, 4)

        operator.native_stake = max(0.0, round(operator.native_stake - native_slashed, 4))
        operator.restaked_eth = max(0.0, round(operator.restaked_eth - eth_slashed, 4))

        native_slashed_usd = native_slashed * self.config.native_token_price_usd
        eth_slashed_usd = eth_slashed * self.config.eth_price_usd
        total_slashed_usd = round(native_slashed_usd + eth_slashed_usd, 2)

        # Distribute according to statutory waterfall
        bounty_usd = round(total_slashed_usd * self.config.challenger_bounty_pct, 2)
        insurance_usd = round(total_slashed_usd * self.config.insurance_reserve_pct, 2)
        # Mathematical conservation: burn remainder to ensure sum(allocations) == total_slashed
        burn_usd = round(total_slashed_usd - bounty_usd - insurance_usd, 2)
        user_refund = round(escrow_usd, 2)

        self.total_bounties_paid_usd += bounty_usd
        self.total_insurance_collected_usd += insurance_usd
        self.total_burned_usd += burn_usd
        self.total_refunds_usd += user_refund
        operator.total_slashed_usd += total_slashed_usd

        # Evaluate jailing conditions
        is_permanent = False
        is_jailed = False

        if dispute_type == DisputeType.BYZANTINE_DOUBLE_SIGNING:
            operator.status = OperatorStatus.SLASHED_PERMANENT
            is_permanent = True
            is_jailed = True
        else:
            below_native = operator.native_stake < self.config.min_native_stake
            below_eth = operator.restaked_eth < self.config.min_eth_stake
            if below_native or below_eth:
                operator.status = OperatorStatus.JAILED
                is_jailed = True

        receipt = SlashingReceipt(
            receipt_id=f"sl-rcpt-{uuid.uuid4().hex[:12]}",
            operator_id=operator_id,
            dispute_type=dispute_type,
            native_slashed=native_slashed,
            eth_slashed=eth_slashed,
            total_slashed_usd=total_slashed_usd,
            challenger_bounty_usd=bounty_usd,
            insurance_reserve_usd=insurance_usd,
            burn_usd=burn_usd,
            user_refund_usd=user_refund,
            operator_jailed=is_jailed,
            permanent=is_permanent,
        )

        logger.info(
            "Executed slashing for operator %s: %s (Total: $%s USD, Jailed: %s)",
            operator_id,
            dispute_type.value,
            total_slashed_usd,
            is_jailed,
        )
        return receipt

    def execute_frivolous_forfeiture(
        self,
        operator_id: str,
        bond_usd: float,
    ) -> Tuple[float, float]:
        """
        Forfeit challenger bond on unsubstantiated claim.
        50% paid to operator as compensation, 50% to protocol insurance reserve.
        """
        operator_compensation = round(bond_usd * 0.50, 2)
        insurance_reserve = round(bond_usd - operator_compensation, 2)

        self.total_insurance_collected_usd += insurance_reserve
        logger.info(
            "Frivolous challenge bond $%s forfeited: $%s to operator %s, $%s to insurance.",
            bond_usd,
            operator_compensation,
            operator_id,
            insurance_reserve,
        )
        return operator_compensation, insurance_reserve

    def replenish_and_unjail(
        self,
        operator_id: str,
        native_amount: float = 0.0,
        eth_amount: float = 0.0,
    ) -> Operator:
        """
        Deposit collateral to replenish stake and restore active status.
        Permanently slashed Byzantine operators cannot unjail.
        """
        operator = self.staking_manager.get_operator(operator_id)
        if operator.status == OperatorStatus.SLASHED_PERMANENT:
            raise PermissionError(
                f"Operator {operator_id} is permanently blacklisted (SLASHED_PERMANENT) "
                "and cannot replenish stake or unjail."
            )

        if native_amount > 0:
            operator.native_stake += round(native_amount, 4)
        if eth_amount > 0:
            operator.restaked_eth += round(eth_amount, 4)

        # Check if thresholds are satisfied to restore ACTIVE status
        has_min_native = operator.native_stake >= self.config.min_native_stake
        has_min_eth = operator.restaked_eth >= self.config.min_eth_stake

        if has_min_native and has_min_eth and operator.status == OperatorStatus.JAILED:
            operator.status = OperatorStatus.ACTIVE
            logger.info("Operator %s successfully unjailed and restored to ACTIVE.", operator_id)

        return operator
