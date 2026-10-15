import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwk as jose_jwk
from jose import jwt as jose_jwt

from api.core import security
from api.core.config import settings

TEST_ISSUER = "https://test.clerk.dev"
TEST_AUDIENCE = "test-audience"
TEST_KID = "test-kid-1"


@pytest.fixture(autouse=True)
def _configure_clerk_settings(monkeypatch):
    monkeypatch.setattr(settings, "CLERK_ISSUER", TEST_ISSUER)
    monkeypatch.setattr(settings, "CLERK_AUDIENCE", TEST_AUDIENCE)
    security.jwks_cache = None
    yield
    security.jwks_cache = None


@pytest.fixture(scope="module")
def rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    jwk_dict = jose_jwk.construct(public_pem, algorithm="RS256").to_dict()
    jwk_dict["kid"] = TEST_KID
    jwk_dict["use"] = "sig"
    return {"private_pem": private_pem, "jwks": {"keys": [jwk_dict]}}


@pytest.fixture(autouse=True)
def _mock_jwks(monkeypatch, rsa_keypair):
    monkeypatch.setattr(security, "get_jwks", lambda force_refresh=False: rsa_keypair["jwks"])


def make_token(rsa_keypair, *, sub="user_123", iss=TEST_ISSUER, aud=TEST_AUDIENCE, exp_delta=3600, kid=TEST_KID):
    claims = {"sub": sub, "iss": iss, "aud": aud, "exp": int(time.time()) + exp_delta}
    return jose_jwt.encode(claims, rsa_keypair["private_pem"], algorithm="RS256", headers={"kid": kid})


def test_valid_token_is_authenticated(rsa_keypair):
    token = make_token(rsa_keypair)
    payload = security.verify_token(token)
    assert payload["sub"] == "user_123"


def test_no_token_rejected():
    with pytest.raises(HTTPException):
        security.verify_token("")


def test_invalid_token_signature_rejected(rsa_keypair):
    token = make_token(rsa_keypair)
    tampered = token[:-4] + ("A" * 4)
    with pytest.raises(HTTPException) as exc:
        security.verify_token(tampered)
    assert exc.value.status_code == 401


def test_expired_token_rejected(rsa_keypair):
    token = make_token(rsa_keypair, exp_delta=-3600)
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 401


def test_wrong_issuer_rejected(rsa_keypair):
    token = make_token(rsa_keypair, iss="https://attacker.example")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 401


def test_wrong_audience_rejected(rsa_keypair):
    token = make_token(rsa_keypair, aud="some-other-app")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 401


def test_unknown_kid_rejected(rsa_keypair):
    token = make_token(rsa_keypair, kid="nonexistent-kid")
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 401


def test_missing_issuer_config_fails_closed(monkeypatch, rsa_keypair):
    monkeypatch.setattr(settings, "CLERK_ISSUER", "")
    token = make_token(rsa_keypair)
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 500


def test_missing_audience_config_fails_closed(monkeypatch, rsa_keypair):
    monkeypatch.setattr(settings, "CLERK_AUDIENCE", "")
    token = make_token(rsa_keypair)
    with pytest.raises(HTTPException) as exc:
        security.verify_token(token)
    assert exc.value.status_code == 500
