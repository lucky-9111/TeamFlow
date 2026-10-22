from fastapi import APIRouter, Request, Response, status

from app.api.deps import DB, CurrentSession, CurrentUserAllowPending, client_ip
from app.core.config import get_settings
from app.schemas.auth import ChangePasswordRequest, CsrfResponse, CurrentUser, LoginRequest, LoginResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, token: str | None, csrf_token: str) -> None:
    settings = get_settings()
    max_age = settings.session_max_days * 24 * 3600
    if token is not None:
        response.set_cookie(
            settings.session_cookie_name,
            token,
            max_age=max_age,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    # Readable by the SPA, which echoes it in the X-CSRF-Token header (double submit).
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    for name in (settings.session_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite="lax")


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> LoginResponse:
    issued = auth_service.login(
        db, body.email, body.password, client_ip(request), request.headers.get("user-agent")
    )
    _set_auth_cookies(response, issued.token, issued.csrf_token)
    return LoginResponse(user=CurrentUser.model_validate(issued.user), csrf_token=issued.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(session: CurrentSession, db: DB) -> Response:
    auth_service.logout(db, session)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_auth_cookies(response)
    return response


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUserAllowPending) -> CurrentUser:
    return CurrentUser.model_validate(user)


@router.get("/csrf", response_model=CsrfResponse)
def refresh_csrf(session: CurrentSession, response: Response, db: DB) -> CsrfResponse:
    """Issue a fresh CSRF token for the current session (e.g. if the cookie was cleared)."""
    csrf_token = auth_service.rotate_csrf(db, session)
    _set_auth_cookies(response, None, csrf_token)
    return CsrfResponse(csrf_token=csrf_token)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordRequest, session: CurrentSession, db: DB) -> Response:
    auth_service.change_password(db, session, body.current_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
