"""
Dual-quorum economic security and operator staking management.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .models import ConsensusResult, Operator, OperatorStatus, StakePoolConfig

logger = logging.getLogger(__name__)


class StakingManager:
    """Manages restaked collateral, operator lifecycle, and dual-quorum consensus."""

    def __init__(self, config: Optional[StakePoolConfig] = None) -> None:
        self.config = config or StakePoolConfig()
        self._operators: Dict[str, Operator] = {}

    @property
    def operators(self) -> Dict[str, Operator]:
        """Access registered operators."""
        return self._operators

    def register_operator(
        self,
        operator_id: str,
        did: str,
        public_key: str,
        native_stake: float,
        restaked_eth: float,
    ) -> Operator:
        """Register a new autonomous agent operator with dual collateral."""
        if operator_id in self._operators:
            raise ValueError(f"Operator {operator_id} is already registered.")

        for op in self._operators.values():
            if op.did == did:
                raise ValueError(f"DID {did} is already registered to operator {op.operator_id}.")

        if native_stake < self.config.min_native_stake:
            raise ValueError(
                f"Native stake {native_stake} is below required minimum {self.config.min_native_stake}."
            )

        if restaked_eth < self.config.min_eth_stake:
            raise ValueError(
                f"Restaked ETH {restaked_eth} is below required minimum {self.config.min_eth_stake}."
            )

        operator = Operator(
            operator_id=operator_id,
            did=did,
            public_key=public_key,
            native_stake=native_stake,
            restaked_eth=restaked_eth,
            status=OperatorStatus.ACTIVE,
        )
        self._operators[operator_id] = operator
        return operator

    def deposit_native(self, operator_id: str, amount: float) -> float:
        """Add native token collateral to an operator."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        operator = self.get_operator(operator_id)
        operator.native_stake += amount
        return operator.native_stake

    def deposit_eth(self, operator_id: str, amount: float) -> float:
        """Add restaked ETH collateral to an operator."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        operator = self.get_operator(operator_id)
        operator.restaked_eth += amount
        return operator.restaked_eth

    def get_operator(self, operator_id: str) -> Operator:
        """Retrieve an operator by ID or raise KeyError."""
        if operator_id not in self._operators:
            raise KeyError(f"Operator {operator_id} not found.")
        return self._operators[operator_id]

    def list_operators(self, status: Optional[OperatorStatus] = None) -> List[Operator]:
        """List operators, optionally filtered by status."""
        if status is None:
            return list(self._operators.values())
        return [op for op in self._operators.values() if op.status == status]

    def total_economic_security_usd(self) -> float:
        """Calculate total blended economic security across all active operators in USD."""
        total = 0.0
        for op in self._operators.values():
            if op.is_active():
                native_usd = op.native_stake * self.config.native_token_price_usd
                eth_usd = op.restaked_eth * self.config.eth_price_usd
                total += native_usd + eth_usd
        return round(total, 2)

    def active_quorum_totals(self) -> Tuple[float, float]:
        """Return total (native_tokens, restaked_eth) staked by active operators."""
        total_native = 0.0
        total_eth = 0.0
        for op in self._operators.values():
            if op.is_active():
                total_native += op.native_stake
                total_eth += op.restaked_eth
        return total_native, total_eth

    def verify_dual_quorum(self, signing_operator_ids: List[str]) -> ConsensusResult:
        """
        Verify if a set of signing operators satisfies dual-quorum supermajority.
        
        Requires:
        (sum(Q1_signed) / sum(Q1_active) >= threshold) AND
        (sum(Q2_signed) / sum(Q2_active) >= threshold)
        """
        total_native, total_eth = self.active_quorum_totals()
        active_ops = [op for op in self._operators.values() if op.is_active()]
        threshold = self.config.consensus_threshold

        if total_native == 0.0 or total_eth == 0.0 or not active_ops:
            return ConsensusResult(
                approved=False,
                native_weight=0.0,
                native_total=total_native,
                native_pct=0.0,
                eth_weight=0.0,
                eth_total=total_eth,
                eth_pct=0.0,
                threshold=threshold,
                signers_count=0,
                active_operators_count=len(active_ops),
                rejection_reason="No active stake available in the network",
            )

        # Deduplicate signers
        unique_signers = set(signing_operator_ids)
        signed_native = 0.0
        signed_eth = 0.0
        valid_signer_count = 0

        for signer_id in unique_signers:
            op = self._operators.get(signer_id)
            if op and op.is_active():
                signed_native += op.native_stake
                signed_eth += op.restaked_eth
                valid_signer_count += 1

        native_pct = signed_native / total_native if total_native > 0 else 0.0
        eth_pct = signed_eth / total_eth if total_eth > 0 else 0.0

        q1_met = native_pct >= threshold
        q2_met = eth_pct >= threshold
        approved = q1_met and q2_met

        rejection_reason = None
        if not approved:
            if not q1_met and not q2_met:
                rejection_reason = (
                    f"Both Quorum 1 (Native: {native_pct:.2%}) and Quorum 2 (ETH: {eth_pct:.2%}) "
                    f"failed threshold {threshold:.2%}"
                )
            elif not q1_met:
                rejection_reason = (
                    f"Quorum 1 (Native: {native_pct:.2%}) failed threshold {threshold:.2%}"
                )
            else:
                rejection_reason = (
                    f"Quorum 2 (ETH: {eth_pct:.2%}) failed threshold {threshold:.2%}"
                )

        return ConsensusResult(
            approved=approved,
            native_weight=signed_native,
            native_total=total_native,
            native_pct=native_pct,
            eth_weight=signed_eth,
            eth_total=total_eth,
            eth_pct=eth_pct,
            threshold=threshold,
            signers_count=valid_signer_count,
            active_operators_count=len(active_ops),
            rejection_reason=rejection_reason,
        )
