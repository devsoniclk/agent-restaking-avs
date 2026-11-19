"""
W3C Decentralized Identifier (DID) and Verifiable Credential management.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from .models import VerifiableCredential


class IdentityManager:
    """Manages agent identity attestation, credential issuance, and cryptographic verification."""

    @staticmethod
    def format_did(identifier: str) -> str:
        """Format an operator identifier into a canonical W3C DID string."""
        clean = identifier.strip().lower()
        if clean.startswith("did:agent:"):
            return clean
        if clean.startswith("0x"):
            return f"did:agent:eth:{clean}"
        return f"did:agent:avs:{clean}"

    @staticmethod
    def canonical_digest(data: Dict[str, Any]) -> str:
        """Generate a deterministic SHA-256 digest for JSON-serializable dictionaries."""
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def issue_credential(
        cls,
        issuer_did: str,
        subject_did: str,
        claims: Dict[str, Any],
        secret_key: str,
        ttl_seconds: float = 86400.0,
        issued_at: Optional[float] = None,
    ) -> VerifiableCredential:
        """Issue a signed W3C-style Verifiable Credential for an autonomous agent."""
        now = issued_at if issued_at is not None else time.time()
        expires_at = now + ttl_seconds
        credential_id = f"vc-agent-{uuid.uuid4().hex[:12]}"

        payload = {
            "credential_id": credential_id,
            "issuer_did": issuer_did,
            "subject_did": subject_did,
            "claims": claims,
            "issued_at": now,
            "expires_at": expires_at,
        }
        digest = cls.canonical_digest(payload)
        signature = hmac.new(
            secret_key.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        return VerifiableCredential(
            credential_id=credential_id,
            issuer_did=issuer_did,
            subject_did=subject_did,
            claims=claims,
            issued_at=now,
            expires_at=expires_at,
            signature=signature,
        )

    @classmethod
    def verify_credential(
        cls,
        credential: VerifiableCredential,
        secret_key: str,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Verify credential signature and check expiration status."""
        now = current_time if current_time is not None else time.time()
        if credential.is_expired(now):
            return False, f"Credential {credential.credential_id} expired at {credential.expires_at}."

        payload = {
            "credential_id": credential.credential_id,
            "issuer_did": credential.issuer_did,
            "subject_did": credential.subject_did,
            "claims": credential.claims,
            "issued_at": credential.issued_at,
            "expires_at": credential.expires_at,
        }
        digest = cls.canonical_digest(payload)
        expected_sig = hmac.new(
            secret_key.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(credential.signature, expected_sig):
            return False, "Invalid cryptographic signature."

        return True, None

    @staticmethod
    def validate_hardware_tee_claims(claims: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate presence of required TEE attestation claims in agent credential."""
        required_fields = ["tee_type", "measurement_digest", "model_weight_digest"]
        for field in required_fields:
            if field not in claims:
                return False, f"Missing required hardware attestation claim: '{field}'."

        allowed_tees = {"INTEL_TDX", "AMD_SEV_SNP", "AWS_NITRO", "APPLE_SEP"}
        tee_type = str(claims.get("tee_type", "")).upper()
        if tee_type not in allowed_tees:
            return False, f"Unsupported TEE type '{tee_type}'. Must be one of {allowed_tees}."

        return True, None
