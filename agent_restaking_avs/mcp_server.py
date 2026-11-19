"""
FastMCP Server implementation exposing Agent Restaking AVS tools for AI agents.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .arbitration import ArbitrationTribunal
from .models import (
    DisputeType,
    FraudClaim,
    OperatorStatus,
    StakePoolConfig,
    TaskReceipt,
)
from .staking import StakingManager
from .waterfall import SlashingWaterfallEngine


class AgentRestakingMCPServer:
    """In-process MCP tool runner providing AVS staking and arbitration endpoints."""

    def __init__(self, config: Optional[StakePoolConfig] = None) -> None:
        self.config = config or StakePoolConfig()
        self.staking = StakingManager(self.config)
        self.waterfall = SlashingWaterfallEngine(self.staking)
        self.tribunal = ArbitrationTribunal(self.staking, self.waterfall)

    def get_network_status(self) -> Dict[str, Any]:
        """Return overall AVS network metrics, total security, and operator counts."""
        active_ops = self.staking.list_operators(OperatorStatus.ACTIVE)
        jailed_ops = self.staking.list_operators(OperatorStatus.JAILED)
        permanently_slashed = self.staking.list_operators(OperatorStatus.SLASHED_PERMANENT)

        return {
            "total_economic_security_usd": self.staking.total_economic_security_usd(),
            "active_operators_count": len(active_ops),
            "jailed_operators_count": len(jailed_ops),
            "permanently_slashed_count": len(permanently_slashed),
            "consensus_threshold_pct": self.config.consensus_threshold * 100,
            "min_native_stake": self.config.min_native_stake,
            "min_eth_stake": self.config.min_eth_stake,
        }

    def register_operator(
        self,
        operator_id: str,
        did: str,
        public_key: str,
        native_stake: float,
        restaked_eth: float,
    ) -> Dict[str, Any]:
        """Register an operator with native and ETH restaked collateral."""
        op = self.staking.register_operator(
            operator_id=operator_id,
            did=did,
            public_key=public_key,
            native_stake=native_stake,
            restaked_eth=restaked_eth,
        )
        return {
            "status": "success",
            "operator_id": op.operator_id,
            "did": op.did,
            "native_stake": op.native_stake,
            "restaked_eth": op.restaked_eth,
            "operator_status": op.status.value,
        }

    def verify_consensus(self, signing_operator_ids: List[str]) -> Dict[str, Any]:
        """Verify dual-quorum consensus for a given set of signing operators."""
        res = self.staking.verify_dual_quorum(signing_operator_ids)
        return {
            "approved": res.approved,
            "native_pct": round(res.native_pct * 100, 2),
            "eth_pct": round(res.eth_pct * 100, 2),
            "threshold_pct": round(res.threshold * 100, 2),
            "valid_signers_count": res.signers_count,
            "rejection_reason": res.rejection_reason,
        }

    def submit_task_receipt(
        self,
        task_id: str,
        operator_id: str,
        escrow_usd: float,
        deadline: float,
        expected_schema_hash: str,
        actual_output_hash: str,
        allowed_tools: List[str],
        executed_tools: List[str],
        state_root: str,
    ) -> Dict[str, Any]:
        """Record task execution receipt into the tribunal ledger."""
        receipt = TaskReceipt(
            task_id=task_id,
            operator_id=operator_id,
            escrow_usd=escrow_usd,
            deadline=deadline,
            expected_schema_hash=expected_schema_hash,
            actual_output_hash=actual_output_hash,
            allowed_tools=allowed_tools,
            executed_tools=executed_tools,
            state_root=state_root,
        )
        self.tribunal.record_receipt(receipt)
        return {"status": "recorded", "task_id": task_id, "operator_id": operator_id}

    def file_and_adjudicate_dispute(
        self,
        claim_id: str,
        challenger_did: str,
        operator_id: str,
        task_id: str,
        dispute_type: str,
        bond_usd: float,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """File a fraud challenge and immediately execute deterministic tribunal adjudication."""
        dtype = DisputeType(dispute_type)
        claim = FraudClaim(
            claim_id=claim_id,
            challenger_did=challenger_did,
            operator_id=operator_id,
            task_id=task_id,
            dispute_type=dtype,
            bond_usd=bond_usd,
            evidence=evidence,
        )
        self.tribunal.file_dispute(claim)
        is_guilty, resolved_type, slashing = self.tribunal.adjudicate(claim_id)

        response: Dict[str, Any] = {
            "claim_id": claim_id,
            "is_guilty": is_guilty,
            "resolved_dispute_type": resolved_type.value,
        }
        if slashing:
            response["slashing"] = {
                "total_slashed_usd": slashing.total_slashed_usd,
                "challenger_bounty_usd": slashing.challenger_bounty_usd,
                "insurance_reserve_usd": slashing.insurance_reserve_usd,
                "burn_usd": slashing.burn_usd,
                "user_refund_usd": slashing.user_refund_usd,
                "operator_jailed": slashing.operator_jailed,
                "permanent": slashing.permanent,
            }
        return response
