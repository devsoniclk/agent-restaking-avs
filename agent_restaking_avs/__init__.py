"""
Agent Restaking AVS Protocol.

Autonomous agent economic security, dual-quorum consensus,
identity attestation, cross-chain relays, and deterministic SLA arbitration.
"""

__version__ = "0.1.1"
__author__ = "Lakshitha Dananjaya"

from .models import (
    OperatorStatus,
    DisputeType,
    Operator,
    StakePool,
    StakePoolConfig,
    VerifiableCredential,
    CrossChainPacket,
    TaskReceipt,
    FraudClaim,
    SlashingReceipt,
    ConsensusResult,
    PENALTY_RATES,
)
from .staking import StakingManager
from .identity import IdentityManager
from .relays import CrossChainRelayEngine
from .arbitration import ArbitrationTribunal
from .waterfall import SlashingWaterfallEngine

__all__ = [
    "OperatorStatus",
    "DisputeType",
    "Operator",
    "StakePool",
    "StakePoolConfig",
    "VerifiableCredential",
    "CrossChainPacket",
    "TaskReceipt",
    "FraudClaim",
    "SlashingReceipt",
    "ConsensusResult",
    "PENALTY_RATES",
    "StakingManager",
    "IdentityManager",
    "CrossChainRelayEngine",
    "ArbitrationTribunal",
    "SlashingWaterfallEngine",
]
