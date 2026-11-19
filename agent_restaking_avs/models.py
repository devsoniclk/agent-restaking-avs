"""
Data models and type definitions for the Agent Restaking AVS protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OperatorStatus(str, Enum):
    """Lifecycle state of an autonomous agent validator operator."""
    ACTIVE = "ACTIVE"
    JAILED = "JAILED"
    SLASHED_PERMANENT = "SLASHED_PERMANENT"


class DisputeType(str, Enum):
    """Classification of verifiable SLA disputes and fraud claims."""
    BYZANTINE_DOUBLE_SIGNING = "BYZANTINE_DOUBLE_SIGNING"
    UNAUTHORIZED_TOOL_EXECUTION = "UNAUTHORIZED_TOOL_EXECUTION"
    HALLUCINATION_SCHEMA_MISMATCH = "HALLUCINATION_SCHEMA_MISMATCH"
    LIVENESS_LATENCY_BREACH = "LIVENESS_LATENCY_BREACH"
    FRIVOLOUS_CHALLENGE = "FRIVOLOUS_CHALLENGE"


# Statutory slashing percentages per violation
PENALTY_RATES: Dict[DisputeType, float] = {
    DisputeType.BYZANTINE_DOUBLE_SIGNING: 1.00,       # 100% full slash + permanent blacklist
    DisputeType.UNAUTHORIZED_TOOL_EXECUTION: 0.50,     # 50% collateral slash
    DisputeType.HALLUCINATION_SCHEMA_MISMATCH: 0.40,   # 40% collateral slash
    DisputeType.LIVENESS_LATENCY_BREACH: 0.15,         # 15% penalty haircut
    DisputeType.FRIVOLOUS_CHALLENGE: 1.00,             # 100% challenger bond forfeiture
}


@dataclass
class Operator:
    """An autonomous agent validator registered in the AVS network."""
    operator_id: str
    did: str
    public_key: str
    native_stake: float
    restaked_eth: float
    status: OperatorStatus = OperatorStatus.ACTIVE
    tasks_completed: int = 0
    total_slashed_usd: float = 0.0
    registered_at: float = field(default_factory=time.time)

    def is_active(self) -> bool:
        """Return True if operator is eligible for consensus quorums."""
        return self.status == OperatorStatus.ACTIVE


@dataclass
class StakePoolConfig:
    """Configuration parameters and economic thresholds for the AVS."""
    min_native_stake: float = 10000.0      # Minimum native governance tokens
    min_eth_stake: float = 10.0           # Minimum restaked ETH
    consensus_threshold: float = 0.6667   # 2/3 supermajority threshold
    native_token_price_usd: float = 2.50  # USD value of native token
    eth_price_usd: float = 3200.00        # USD value of restaked ETH
    challenger_bounty_pct: float = 0.25   # 25% of slashed funds to challenger
    insurance_reserve_pct: float = 0.45   # 45% of slashed funds to protocol reserve
    burn_pct: float = 0.30                # 30% of slashed funds burned


# Alias for backwards compatibility
StakePool = StakePoolConfig


@dataclass
class VerifiableCredential:
    """W3C-compliant cryptographic credential for an autonomous agent node."""
    credential_id: str
    issuer_did: str
    subject_did: str
    claims: Dict[str, Any]
    issued_at: float
    expires_at: float
    signature: str

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if credential validity has lapsed."""
        now = current_time if current_time is not None else time.time()
        return now > self.expires_at


@dataclass
class CrossChainPacket:
    """Cross-chain state relay packet with anti-replay guarantees."""
    packet_id: str
    source_chain_id: int
    target_chain_id: int
    nonce: int
    payload_hash: str
    state_merkle_root: str
    signatures: Dict[str, str] = field(default_factory=dict)
    executed: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def relay_key(self) -> str:
        """Unique key identifying relay channel and sequence."""
        return f"{self.source_chain_id}:{self.target_chain_id}:{self.nonce}"


@dataclass
class TaskReceipt:
    """Cryptographic receipt of task execution submitted by an agent."""
    task_id: str
    operator_id: str
    escrow_usd: float
    deadline: float
    expected_schema_hash: str
    actual_output_hash: str
    allowed_tools: List[str]
    executed_tools: List[str]
    state_root: str
    submitted_at: float = field(default_factory=time.time)


@dataclass
class FraudClaim:
    """Formal dispute challenge raised by a watchdog or peer agent."""
    claim_id: str
    challenger_did: str
    operator_id: str
    task_id: str
    dispute_type: DisputeType
    bond_usd: float
    evidence: Dict[str, Any]
    created_at: float = field(default_factory=time.time)


@dataclass
class SlashingReceipt:
    """Deterministic result of a slashing waterfall execution."""
    receipt_id: str
    operator_id: str
    dispute_type: DisputeType
    native_slashed: float
    eth_slashed: float
    total_slashed_usd: float
    challenger_bounty_usd: float
    insurance_reserve_usd: float
    burn_usd: float
    user_refund_usd: float
    operator_jailed: bool
    permanent: bool
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusResult:
    """Evaluation output of a dual-quorum consensus verification."""
    approved: bool
    native_weight: float
    native_total: float
    native_pct: float
    eth_weight: float
    eth_total: float
    eth_pct: float
    threshold: float
    signers_count: int
    active_operators_count: int
    rejection_reason: Optional[str] = None
