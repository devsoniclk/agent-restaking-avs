#!/usr/bin/env python3
"""
Performance benchmarks for Agent Restaking AVS cryptographic operations and quorum verification.
"""

import time
from agent_restaking_avs import (
    CrossChainPacket,
    CrossChainRelayEngine,
    IdentityManager,
    StakePoolConfig,
    StakingManager,
)


def benchmark_credential_issuance_and_verification(n_iterations: int = 1000) -> None:
    claims = {
        "tee_type": "INTEL_TDX",
        "measurement_digest": "0x123456789abcdef",
        "model_weight_digest": "sha256:fedcba987654321",
    }
    secret = "benchmark_secret_key_long_entropy_string"

    start = time.perf_counter()
    for i in range(n_iterations):
        vc = IdentityManager.issue_credential(
            issuer_did="did:agent:avs:benchmark",
            subject_did=f"did:agent:eth:0x{i:040x}",
            claims=claims,
            secret_key=secret,
            ttl_seconds=3600.0,
        )
        is_valid, _ = IdentityManager.verify_credential(vc, secret)
        assert is_valid is True
    duration = time.perf_counter() - start
    ops_per_sec = n_iterations / duration
    print(f"Credential Issue & Verify: {n_iterations} iterations in {duration:.4f}s ({ops_per_sec:,.1f} ops/sec)")


def benchmark_dual_quorum_verification(n_iterations: int = 1000) -> None:
    staking = StakingManager(StakePoolConfig())
    # Register 100 operators
    for i in range(100):
        staking.register_operator(
            operator_id=f"op-{i}",
            did=f"did:agent:eth:0x{i:040x}",
            public_key=f"0xpub{i}",
            native_stake=10000.0 + (i * 100),
            restaked_eth=10.0 + (i * 0.5),
        )

    # 70 operators sign (sufficient for 66.67% supermajority)
    signers = [f"op-{i}" for i in range(30, 100)]

    start = time.perf_counter()
    for _ in range(n_iterations):
        res = staking.verify_dual_quorum(signers)
        assert res.approved is True
    duration = time.perf_counter() - start
    ops_per_sec = n_iterations / duration
    print(f"Dual-Quorum 100-Node Consensus: {n_iterations} iterations in {duration:.4f}s ({ops_per_sec:,.1f} ops/sec)")


def main() -> None:
    print("=== Agent Restaking AVS Protocol Performance Benchmarks ===\n")
    benchmark_credential_issuance_and_verification(1000)
    benchmark_dual_quorum_verification(1000)
    print("\nBenchmark Suite Completed Successfully.")


if __name__ == "__main__":
    main()
