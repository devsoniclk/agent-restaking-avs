"""
Tests for W3C DIDs, Verifiable Credentials, and hardware TEE claims.
"""

import time
from agent_restaking_avs.identity import IdentityManager


def test_did_formatting():
    assert IdentityManager.format_did("0x1234abcd") == "did:agent:eth:0x1234abcd"
    assert IdentityManager.format_did("did:agent:eth:0x999") == "did:agent:eth:0x999"
    assert IdentityManager.format_did("cluster-node-1") == "did:agent:avs:cluster-node-1"


def test_issue_and_verify_credential():
    secret = "secret-key-12345"
    issuer = "did:agent:eth:0xissuer"
    subject = "did:agent:eth:0xsubject"
    claims = {
        "tee_type": "INTEL_TDX",
        "measurement_digest": "0xabc123",
        "model_weight_digest": "0xdef456",
        "benchmark_score": 94.5,
    }

    vc = IdentityManager.issue_credential(
        issuer_did=issuer,
        subject_did=subject,
        claims=claims,
        secret_key=secret,
        ttl_seconds=3600.0,
    )

    valid, reason = IdentityManager.verify_credential(vc, secret)
    assert valid is True
    assert reason is None

    # Test with wrong secret
    valid_bad, reason_bad = IdentityManager.verify_credential(vc, "wrong-secret")
    assert valid_bad is False
    assert "Invalid cryptographic signature" in (reason_bad or "")

    # Test with tampered claims
    vc.claims["benchmark_score"] = 99.9
    valid_tampered, reason_tampered = IdentityManager.verify_credential(vc, secret)
    assert valid_tampered is False


def test_expired_credential_verification():
    secret = "secret-key"
    now = time.time()
    vc = IdentityManager.issue_credential(
        issuer_did="did:issuer",
        subject_did="did:subject",
        claims={"k": "v"},
        secret_key=secret,
        ttl_seconds=10.0,
        issued_at=now - 100.0,  # Expired 90 seconds ago
    )

    valid, reason = IdentityManager.verify_credential(vc, secret, current_time=now)
    assert valid is False
    assert "expired" in (reason or "").lower()


def test_validate_hardware_tee_claims():
    valid_claims = {
        "tee_type": "AMD_SEV_SNP",
        "measurement_digest": "0x111",
        "model_weight_digest": "0x222",
    }
    ok, err = IdentityManager.validate_hardware_tee_claims(valid_claims)
    assert ok is True
    assert err is None

    # Missing field
    missing_claims = {"tee_type": "AWS_NITRO", "measurement_digest": "0x111"}
    ok_miss, err_miss = IdentityManager.validate_hardware_tee_claims(missing_claims)
    assert ok_miss is False
    assert "model_weight_digest" in (err_miss or "")

    # Unsupported TEE
    bad_tee = {
        "tee_type": "CUSTOM_EMULATOR",
        "measurement_digest": "0x111",
        "model_weight_digest": "0x222",
    }
    ok_bad, err_bad = IdentityManager.validate_hardware_tee_claims(bad_tee)
    assert ok_bad is False
    assert "Unsupported TEE" in (err_bad or "")
