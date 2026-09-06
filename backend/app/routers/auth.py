"""Authentication router + the dependency that protects case data.  Owner: BE3"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .. import config
from ..models import AuthUser, LoginRequest, LoginResponse
from ..services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def current_user(request: Request) -> AuthUser:
    """Resolve the caller from the Bearer token, or refuse.

    Every custody entry takes its identity from HERE and never from the
    request body. `uploaded_by` used to be a form field the client filled in,
    which made the chain of custody unfalsifiable in the worst way: anyone
    could act as any officer.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to access case data.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = auth_service.read_token(header.removeprefix("Bearer ").strip())
    if not user_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Session expired or invalid. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    record = auth_service.get_user(user_id)
    if not record:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "This account is no longer active.")
    return AuthUser(**record)


RequireUser = Depends(current_user)


@router.post("/login", response_model=LoginResponse, summary="Sign in")
def login(payload: LoginRequest):
    user = auth_service.authenticate(payload.user_id, payload.password)
    if not user:
        # One message for both wrong-user and wrong-password, and the service
        # hashes either way, so this cannot be used to enumerate accounts.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")

    token, expires = auth_service.issue_token(user["user_id"])
    warning = None
    if auth_service.using_default_password():
        warning = (
            "This instance is still using the documented demo password. "
            "Set DEMO_OFFICER_PASSWORD before handling anything real."
        )
    return LoginResponse(token=token, expires_at=expires,
                         user=AuthUser(**user), warning=warning)


@router.get("/me", response_model=AuthUser, summary="Who am I")
def me(user: AuthUser = RequireUser):
    return user
