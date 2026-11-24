"""Sign-in with GitHub, owner sessions, CSRF and request limits.

Only GitHub accounts whose numeric user id is allowlisted get a session (logins can be
renamed and re-registered, ids cannot). This is the only code that reads
GITHUB_CLIENT_SECRET; it is sent only to GitHub's fixed token URL.

A session is a random token in a `__Host-` cookie (HttpOnly, Secure, SameSite=Lax). The
database keeps only its SHA-256, so a database leak gives no usable sessions. Requests that
change something must also send the session's CSRF token in X-CSRF-Token, and a browser
Origin other than the page's own is refused.

The deploy smoke test signs in with a bearer token whose SHA-256 is SMOKE_TOKEN_SHA256. It
acts as its own owner, "smoke", and may only read.
"""

import base64
import hashlib
import os
import secrets
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import Request
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from route_api.db import GenerationRunRecord, OwnerSessionRecord

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 (a URL)
USER_URL = "https://api.github.com/user"
SESSION_COOKIE = "__Host-route-session"
LOGIN_COOKIE = "__Host-route-login"
SESSION_DAYS = 7
LOGIN_SECONDS = 600
SMOKE_OWNER = "smoke"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthError(Exception):
    """A refused sign-in or request, answered as {"error": {"code", "message"}}."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


class GitHubOAuth:
    def __init__(
        self,
        http: httpx.Client,
        client_id: str | None,
        client_secret: str | None,
        callback_url: str,
        allowed_ids: set[int],
        authorize_url: str = AUTHORIZE_URL,
    ):
        self.http = http
        self.client_id = client_id
        self.client_secret = client_secret
        self.callback_url = callback_url
        self.allowed_ids = allowed_ids
        self.authorize_url = authorize_url

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.allowed_ids)

    def login_url(self, state: str, verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        query = {
            "client_id": self.client_id or "",
            "redirect_uri": self.callback_url,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "allow_signup": "false",
        }
        return f"{self.authorize_url}?{urlencode(query)}"

    def allowed_user_id(self, code: str, verifier: str) -> int:
        """Swap the code for a token, ask GitHub who it is, and check the allowlist."""
        if not self.configured:
            raise AuthError(503, "sign_in_not_configured", "Sign-in is not configured")
        form = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.callback_url,
            "code_verifier": verifier,
        }
        try:
            answer = self.http.post(
                TOKEN_URL, data=form, headers={"Accept": "application/json"}, timeout=10
            )
            token = answer.json().get("access_token")
            if not token:
                raise AuthError(403, "not_allowed", "GitHub did not confirm this sign-in")
            user = self.http.get(
                USER_URL,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=10,
            )
            user_id = user.json().get("id")
        except (httpx.HTTPError, ValueError) as error:
            raise AuthError(502, "sign_in_failed", "GitHub sign-in failed; try again") from error
        if user_id not in self.allowed_ids:
            raise AuthError(403, "not_allowed", "This GitHub account may not use the app")
        return int(user_id)


def hashed(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(engine: Engine, owner_id: str) -> tuple[str, str]:
    """Store a new session for the owner and return its (cookie token, CSRF token)."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            OwnerSessionRecord(
                token_sha256=hashed(token),
                owner_id=owner_id,
                csrf_token=csrf,
                created_at=now,
                expires_at=now + timedelta(days=SESSION_DAYS),
            )
        )
        session.commit()
    return token, csrf


def end_session(engine: Engine, token: str) -> None:
    with Session(engine) as session:
        session.execute(
            delete(OwnerSessionRecord).where(OwnerSessionRecord.token_sha256 == hashed(token))
        )
        session.commit()


class RequestLimit:
    """At most `per_minute` requests per owner in any 60 seconds (one API instance)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.recent: dict[str, deque[float]] = {}

    def check(self, owner_id: str) -> None:
        now = time.monotonic()
        times = self.recent.setdefault(owner_id, deque())
        while times and times[0] < now - 60:
            times.popleft()
        if len(times) >= self.per_minute:
            raise AuthError(429, "rate_limited", "Too many requests; wait a minute")
        times.append(now)


class Auth:
    """Works out the owner of each request, or refuses it."""

    def __init__(
        self,
        engine: Engine,
        github: GitHubOAuth,
        app_origin: str,
        smoke_token_sha256: str | None = None,
        requests_per_minute: int = 60,
        runs_per_day: int = 30,
    ):
        self.engine = engine
        self.github = github
        self.app_origin = app_origin
        self.smoke_token_sha256 = smoke_token_sha256
        self.limit = RequestLimit(requests_per_minute)
        self.runs_per_day = runs_per_day

    def owner(self, request: Request) -> tuple[str, str]:
        """The (owner id, CSRF token) of a signed-in request."""
        origin = request.headers.get("Origin")
        if origin is not None and origin != self.app_origin:
            raise AuthError(403, "csrf_failed", "Requests must come from the app's own page")
        owner_id, csrf = self.signed_in(request)
        if request.method not in SAFE_METHODS:
            if owner_id == SMOKE_OWNER:
                raise AuthError(403, "read_only", "The smoke test may only read")
            sent = request.headers.get("X-CSRF-Token", "")
            if not secrets.compare_digest(sent.encode(), csrf.encode()):
                raise AuthError(403, "csrf_failed", "Missing or wrong CSRF token")
        self.limit.check(owner_id)
        return owner_id, csrf

    def signed_in(self, request: Request) -> tuple[str, str]:
        bearer = request.headers.get("Authorization", "")
        if self.smoke_token_sha256 and bearer.startswith("Bearer "):
            sent = hashed(bearer.removeprefix("Bearer "))
            if secrets.compare_digest(sent, self.smoke_token_sha256):
                return SMOKE_OWNER, ""
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            with Session(self.engine) as session:
                record = session.get(OwnerSessionRecord, hashed(token))
                if record is not None and record.expires_at > datetime.now(UTC):
                    return record.owner_id, record.csrf_token
        raise AuthError(401, "not_signed_in", "Sign in first")

    def check_run_budget(self, session: Session, owner_id: str) -> None:
        """Refuse a new run once the owner started runs_per_day in the last 24 hours."""
        since = datetime.now(UTC) - timedelta(days=1)
        started = session.scalar(
            select(func.count())
            .select_from(GenerationRunRecord)
            .where(GenerationRunRecord.owner_id == owner_id)
            .where(GenerationRunRecord.started_at > since)
        )
        if (started or 0) >= self.runs_per_day:
            raise AuthError(
                429, "run_limit_reached", f"At most {self.runs_per_day} runs a day; try tomorrow"
            )


def auth_from_env(engine: Engine) -> Auth:
    """Reads APP_ORIGIN, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, OWNER_GITHUB_IDS (comma
    separated numeric ids, Tom's by default), SMOKE_TOKEN_SHA256, REQUESTS_PER_MINUTE and
    RUNS_PER_DAY."""
    app_origin = os.environ.get("APP_ORIGIN", "http://127.0.0.1:3000")
    allowed_ids = set()
    for part in os.environ.get("OWNER_GITHUB_IDS", "119127762").split(","):
        if part.strip():
            allowed_ids.add(int(part))
    github = GitHubOAuth(
        httpx.Client(),
        client_id=os.environ.get("GITHUB_CLIENT_ID"),
        client_secret=os.environ.get("GITHUB_CLIENT_SECRET"),
        callback_url=f"{app_origin}/api/auth/callback",
        allowed_ids=allowed_ids,
    )
    return Auth(
        engine,
        github,
        app_origin=app_origin,
        smoke_token_sha256=os.environ.get("SMOKE_TOKEN_SHA256") or None,
        requests_per_minute=int(os.environ.get("REQUESTS_PER_MINUTE", "60")),
        runs_per_day=int(os.environ.get("RUNS_PER_DAY", "30")),
    )
