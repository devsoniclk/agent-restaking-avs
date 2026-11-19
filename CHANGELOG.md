# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-19

### Enhanced
- **Verification & QA Hardening**: Expanded test suite to 45 automated unit and end-to-end integration tests achieving 99.5% code coverage.
- **Reference Examples & Benchmarks**: Added comprehensive live reference scripts (`examples/cross_chain_relay.py`, `examples/slashing_waterfall_demo.py`, `examples/dual_quorum_consensus.py`) and throughput benchmarks (`benchmarks/run_benchmarks.py`) demonstrating >60k ops/sec.
- **Architecture & Protocol Documentation**: Comprehensive README with complete multi-tier Mermaid diagrams, mathematical quorum formulations, FastMCP tool integration, and CLI reference.

## [0.1.0] - 2026-11-19

### Added
- **Dual-Quorum Economic Security (`StakingManager`)**: Restaked ETH/Symbiotic collateral paired with native agent governance tokens enforcing $2/3$ supermajority threshold across both quorums simultaneously.
- **Cryptographic Identity & Verifiable Credentials (`IdentityManager`)**: W3C DID formatting (`did:agent:eth:0x...`), HMAC-SHA256 credential issuance/verification, and hardware TEE attestation claims validation (Intel TDX, AMD SEV-SNP, AWS Nitro, Apple SEP).
- **Cross-Chain State Relays (`CrossChainRelayEngine`)**: Multi-chain packet submission, signature aggregation, and strict cryptographic replay attack defense.
- **Deterministic SLA Arbitration Tribunal (`ArbitrationTribunal`)**: Verifiable fraud challenge games evaluating Byzantine double signing, unauthorized tool execution, schema invalidation (hallucination), and liveness latency breaches.
- **Multi-Tranche Slashing Waterfall (`SlashingWaterfallEngine`)**: Mathematically conserved liquidation engine (100% escrow refund, 25% challenger bounty, 45% protocol insurance reserve, 30% permanent burn) with automated operator jailing and unjailing upon replenishment.
- **FastMCP Tool Integration (`AgentRestakingMCPServer`)**: Native in-process FastMCP server exposing status, registration, consensus verification, receipt submission, and dispute adjudication to LLM agents.
- **Command-Line Interface (`cli.py`)**: Rich-powered CLI supporting network status inspection, consensus verification, and automated waterfall invariant auditing.
- **Comprehensive Test Suite**: 45 unit and end-to-end integration tests achieving 99.5% code coverage.
