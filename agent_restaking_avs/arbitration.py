"""
Deterministic SLA dispute arbitration tribunal and fraud challenge game.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .models import (
    DisputeType,
    FraudClaim,
    SlashingReceipt,
    TaskReceipt,
)
from .staking import StakingManager
from .waterfall import SlashingWaterfallEngine

logger = logging.getLogger(__name__)


class ArbitrationTribunal:
    """Evaluates cryptographic fraud proofs and adjudicates SLA breaches deterministically."""

    def __init__(
        self,
        staking_manager: StakingManager,
        waterfall_engine: SlashingWaterfallEngine,
    ) -> None:
        self.staking_manager = staking_manager
        self.waterfall_engine = waterfall_engine
        self._receipts: Dict[str, TaskReceipt] = {}
        self._claims: Dict[str, FraudClaim] = {}

    @property
    def receipts(self) -> Dict[str, TaskReceipt]:
        """Access recorded task execution receipts."""
        return self._receipts

    @property
    def claims(self) -> Dict[str, FraudClaim]:
        """Access filed fraud claims."""
        return self._claims

    def record_receipt(self, receipt: TaskReceipt) -> None:
        """Register a completed task execution receipt in the tribunal ledger."""
        self._receipts[receipt.task_id] = receipt
        # Increment operator completed count
        try:
            op = self.staking_manager.get_operator(receipt.operator_id)
            op.tasks_completed += 1
        except KeyError:
            pass

    def file_dispute(self, claim: FraudClaim) -> str:
        """File a formal fraud challenge with required challenger bond."""
        if claim.task_id in self._receipts:
            receipt = self._receipts[claim.task_id]
            min_bond = round(0.10 * receipt.escrow_usd, 2)
            if claim.bond_usd < min_bond:
                raise ValueError(
                    f"Challenger bond ${claim.bond_usd} is below the 10% minimum (${min_bond}) "
                    f"for task escrow ${receipt.escrow_usd}."
                )

        if claim.claim_id in self._claims:
            raise ValueError(f"Claim ID {claim.claim_id} already exists.")

        self._claims[claim.claim_id] = claim
        return claim.claim_id

    def adjudicate(self, claim_id: str) -> Tuple[bool, DisputeType, Optional[SlashingReceipt]]:
        """
        Adjudicate a filed dispute claim using cryptographic evidence.
        
        Returns:
            (is_guilty, resolved_dispute_type, SlashingReceipt_if_guilty)
        """
        if claim_id not in self._claims:
            raise KeyError(f"Claim {claim_id} not found.")

        claim = self._claims[claim_id]
        receipt = self._receipts.get(claim.task_id)
        evidence = claim.evidence

        is_substantiated = False

        if claim.dispute_type == DisputeType.BYZANTINE_DOUBLE_SIGNING:
            root1 = evidence.get("root_1", "")
            root2 = evidence.get("root_2", "")
            if root1 and root2 and root1 != root2:
                is_substantiated = True

        elif claim.dispute_type == DisputeType.UNAUTHORIZED_TOOL_EXECUTION:
            allowed = set(evidence.get("allowed_tools") or (receipt.allowed_tools if receipt else []))
            executed = set(evidence.get("executed_tools") or (receipt.executed_tools if receipt else []))
            unauthorized = executed - allowed
            if len(unauthorized) > 0:
                is_substantiated = True

        elif claim.dispute_type == DisputeType.HALLUCINATION_SCHEMA_MISMATCH:
            expected = evidence.get("expected_schema_hash") or (receipt.expected_schema_hash if receipt else "")
            actual = evidence.get("actual_output_hash") or (receipt.actual_output_hash if receipt else "")
            if expected and actual and expected != actual:
                is_substantiated = True

        elif claim.dispute_type == DisputeType.LIVENESS_LATENCY_BREACH:
            deadline = evidence.get("deadline") or (receipt.deadline if receipt else 0.0)
            submitted = evidence.get("submitted_at") or (receipt.submitted_at if receipt else 0.0)
            if submitted > deadline > 0.0:
                is_substantiated = True

        if is_substantiated:
            escrow = receipt.escrow_usd if receipt else 0.0
            slashing_receipt = self.waterfall_engine.execute_slashing(
                operator_id=claim.operator_id,
                dispute_type=claim.dispute_type,
                escrow_usd=escrow,
            )
            return True, claim.dispute_type, slashing_receipt

        # Frivolous claim: challenger bond forfeited
        self.waterfall_engine.execute_frivolous_forfeiture(
            operator_id=claim.operator_id,
            bond_usd=claim.bond_usd,
        )
        return False, DisputeType.FRIVOLOUS_CHALLENGE, None
