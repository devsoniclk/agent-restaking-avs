# Changelog

All notable changes to `agent-restaking-avs` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-19

### Added
- **Dual-Quorum Restaked Security Engine (`StakingManager`):** Enforces simultaneous supermajority approval across Quorum 1 (Native Agent Tokens, min 10,000) and Quorum 2 (Restaked ETH, min 10.0 ETH) with real-time USD valuation.
- **Cryptographic Identity & Verifiable Credentials (`IdentityManager`):** W3C DID formatting (`did:agent:eth:0x...`) and tamper-proof credential issuance with HMAC-SHA256 signature verification and hardware TEE claim validation (Intel TDX, AMD SEV-SNP, AWS Nitro, Apple SEP).
- **Cross-Chain State Relays (`CrossChainRelayEngine`):** State relay verification with aggregated multi-operator signatures and deterministic anti-replay protection.
- **Deterministic SLA Dispute Tribunal (`ArbitrationTribunal`):** Objective cryptographic fraud challenge evaluation covering Byzantine double-signing (100% slash + permanent blacklist), unauthorized tool invocation (50% slash), hallucination schema mismatch (40% slash), liveness timeout (15% haircut), and frivolous challenge bond forfeiture.
- **Collateral Slashing Waterfall (`SlashingWaterfallEngine`):** Mathematical conservation engine distributing slashed funds across Challenger Bounty (25%), Protocol Insurance Reserve (45%), and Collateral Burn (30%), with 100% user escrow refund.
- **FastMCP Protocol Suite & Rich CLI:** Complete MCP server endpoints and production Click/Rich command-line suite with `status`, `verify-consensus`, and `audit` commands.
- **Verification Suite:** 43 automated unit and integration tests passing with 99% overall code coverage.
