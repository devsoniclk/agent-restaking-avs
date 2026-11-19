"""
Performance benchmarks for the Agent Restaking AVS protocol.
Evaluates dual-quorum consensus throughput, DID credential verification latency,
and deterministic slashing waterfall throughput.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_restaking_avs.identity import IdentityManager
from agent_restaking_avs.models import DisputeType, StakePoolConfig
from agent_restaking_avs.staking import StakingManager
from agent_restaking_avs.waterfall import SlashingWaterfallEngine


def benchmark_consensus_verification():
    staking = StakingManager()
    op_ids = []
    for i in range(100):
        op_id = f"op-{i}"
        staking.register_operator(
            operator_id=op_id,
            did=f"did:agent:eth:0x{i:040x}",
            public_key=f"0xpub{i}",
            native_stake=10000.0,
            restaked_eth=10.0,
        )
        op_ids.append(op_id)

    # Benchmark verifying consensus across 75 signers
    signers = op_ids[:75]
    iterations = 10_000
    start = time.perf_counter()
    for _ in range(iterations):
        staking.verify_dual_quorum(signers)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    latency_us = (elapsed / iterations) * 1_000_000
    print(f"Dual-Quorum Consensus (100 Operators, 75 Signers): {rate:,.0f} ops/sec ({latency_us:.2f} µs/op)")


def benchmark_credential_verification():
    secret = "benchmark-secret-key"
    vc = IdentityManager.issue_credential(
        issuer_did="did:agent:eth:0xissuer",
        subject_did="did:agent:eth:0xsubject",
        claims={"tee_type": "INTEL_TDX", "digest": "0x123"},
        secret_key=secret,
    )

    iterations = 20_000
    start = time.perf_counter()
    for _ in range(iterations):
        IdentityManager.verify_credential(vc, secret)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    latency_us = (elapsed / iterations) * 1_000_000
    print(f"Verifiable Credential Verification: {rate:,.0f} ops/sec ({latency_us:.2f} µs/op)")


def benchmark_slashing_waterfall():
    staking = StakingManager()
    waterfall = SlashingWaterfallEngine(staking)
    staking.register_operator("op-victim", "did:v", "0xv", 100_000.0, 100.0)

    iterations = 10_000
    start = time.perf_counter()
    for _ in range(iterations):
        # Replenish and slash
        staking.get_operator("op-victim").native_stake = 100_000.0
        staking.get_operator("op-victim").restaked_eth = 100.0
        waterfall.execute_slashing("op-victim", DisputeType.UNAUTHORIZED_TOOL_EXECUTION, escrow_usd=500.0)
    elapsed = time.perf_counter() - start

    rate = iterations / elapsed
    latency_us = (elapsed / iterations) * 1_000_000
    print(f"Slashing Waterfall Execution: {rate:,.0f} ops/sec ({latency_us:.2f} µs/op)")


if __name__ == "__main__":
    print("=" * 60)
    print("Agent Restaking AVS Protocol Performance Benchmarks")
    print("=" * 60)
    benchmark_consensus_verification()
    benchmark_credential_verification()
    benchmark_slashing_waterfall()
    print("=" * 60)
