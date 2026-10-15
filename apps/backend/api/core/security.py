from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
import uuid
from api.core.config import settings
from typing import Dict

security = HTTPBearer()

jwks_cache = None

def get_jwks(force_refresh: bool = False):
    global jwks_cache
    if not jwks_cache or force_refresh:
        try:
            response = httpx.get(settings.CLERK_JWKS_URL, timeout=5.0)
            response.raise_for_status()
            jwks_cache = response.json()
        except Exception:
            if jwks_cache:
                # Keep serving the stale cache rather than failing every request
                # if Clerk is transiently unreachable.
                return jwks_cache
            raise HTTPException(status_code=500, detail="Could not fetch JWKS")
    return jwks_cache

def verify_token(token: str) -> Dict:
    # Fail closed: issuer/audience validation must be configured, never silently skipped.
    if not settings.CLERK_ISSUER:
        raise HTTPException(status_code=500, detail="Server misconfiguration: CLERK_ISSUER is not set")
    if not settings.CLERK_AUDIENCE:
        raise HTTPException(status_code=500, detail="Server misconfiguration: CLERK_AUDIENCE is not set")

    jwks = get_jwks()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    def find_key(jwks_data):
        for key in jwks_data.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        return {}

    rsa_key = find_key(jwks)
    if not rsa_key:
        # Key may have rotated on Clerk's side since we cached it - refresh once.
        rsa_key = find_key(get_jwks(force_refresh=True))

    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=settings.CLERK_AUDIENCE,
                issuer=settings.CLERK_ISSUER,
                options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
            )
            return payload
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")
    raise HTTPException(status_code=401, detail="Unable to find appropriate key")

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict:
    if settings.AUTH_MODE == "demo":
        # Dev/demo-only bypass of real Clerk verification - see docs/PROJECT_RULES.md
        # and docs/INFRASTRUCTURE_CLOSURE_REPORT.md for why this exists (Clerk
        # credentials unavailable in this environment). Hard-blocked in production
        # regardless of how AUTH_MODE is set, so this can never leak into a real
        # deployment. Everything downstream (get_current_db_user, require_role,
        # assert_client_access, ClientMembership) is completely unchanged - a demo
        # "sub" still has to resolve to a real seeded User row and still goes through
        # the exact same tenant-authorization logic as a real Clerk user.
        if settings.ENVIRONMENT == "production":
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration: AUTH_MODE=demo is not permitted when ENVIRONMENT=production",
            )
        demo_clerk_id = request.headers.get("X-Demo-User") or "demo-admin"
        return {"sub": demo_clerk_id}

    token = credentials.credentials
    payload = verify_token(token)

    # Clerk stores user ID in the 'sub' claim
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")

    return payload

from fastapi import Request
from api.database.session import get_db
from sqlalchemy.orm import Session
from api.models.user import User
from api.models.membership import ClientMembership

ADMIN_ROLE = "Admin"


def get_current_db_user(
    user_payload: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Resolves the JWT's `sub` claim to a local User row. Rejects unknown users -
    there is no implicit-provisioning path here, by design (fail closed)."""
    clerk_id = user_payload.get("sub")
    user = db.query(User).filter(User.clerk_id == clerk_id).first()
    if not user:
        raise HTTPException(status_code=403, detail="User not found in database")
    return user


def require_role(allowed_roles: list[str]):
    def role_checker(user: User = Depends(get_current_db_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return role_checker


def user_has_client_access(db: Session, user: User, client_id) -> bool:
    """Admins are authorized for every client. Everyone else needs an explicit
    ClientMembership row - a caller-supplied client_id is never trusted on its own."""
    if user.role == ADMIN_ROLE:
        return True
    if client_id is None:
        return False
    if isinstance(client_id, str):
        try:
            client_id = uuid.UUID(client_id)
        except ValueError:
            return False
    return (
        db.query(ClientMembership)
        .filter(ClientMembership.user_id == user.id, ClientMembership.client_id == client_id)
        .first()
        is not None
    )


def assert_client_access(db: Session, user: User, client_id) -> None:
    """Call this after loading any client-scoped resource (report, document, content,
    integration, ...) with the resource's *actual* client_id - never with a caller-supplied
    value alone. Raises 404 rather than 403 so an unauthorized user can't distinguish
    'not yours' from 'doesn't exist' (avoids leaking cross-tenant resource existence)."""
    if not user_has_client_access(db, user, client_id):
        raise HTTPException(status_code=404, detail="Resource not found")


def require_client_access(client_id_param: str = "client_id"):
    """Dependency factory for endpoints where client_id is directly a path or query
    parameter (e.g. GET /clients/{client_id}, GET /documents?client_id=...). For
    endpoints scoped by a *different* resource id (report_id, document_id, ...), load
    the resource first and call assert_client_access(db, user, resource.client_id) instead."""

    def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_db_user),
    ) -> User:
        client_id = request.path_params.get(client_id_param) or request.query_params.get(client_id_param)
        if not client_id:
            raise HTTPException(status_code=400, detail=f"Missing required parameter: {client_id_param}")
        assert_client_access(db, user, client_id)
        return user

    return checker
