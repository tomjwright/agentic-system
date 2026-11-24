"""Sign-in with GitHub, owner sessions, CSRF and request limits.

Only GitHub accounts whose numeric user id is allowlisted get a session (logins can be
renamed and re-registered, ids cannot). This is the only code that reads
GITHUB_CLIENT_SECRET; it is sent only to GitHub's fixed token URL.

A session is a random token in a `__Host-` cookie (HttpOnly, Secure, SameSite=Lax). The
database keeps only its SHA-256, so a database leak gives no usable sessions. Requests that
change something must also send the session's CSRF token in X-CSRF-Token, and a browser
Origin other than the page's own is refused.

Two bearer tokens are for the deploy workflow, never for people. The smoke test's token
(SHA-256 in SMOKE_TOKEN_SHA256) acts as owner "smoke" and may only read. The staged browser
test's token (SHA-256 in E2E_TOKEN_SHA256) acts as owner "e2e" and may write, but starts at
most one run every 10 minutes and 3 a day (retention.py deletes its data after a day). A
browser never attaches a bearer token by itself, so a request carrying one cannot be forged by
another site: bearer requests skip the Origin and CSRF checks, which lets the staged page,
on its own one-off origin, use the API. Cookie sessions keep both checks.
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

from route_api.db import AgentRunRecord, GenerationRunRecord, OwnerSessionRecord

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 (a URL)
USER_URL = "https://api.github.com/user"
SESSION_COOKIE = "__Host-route-session"
LOGIN_COOKIE = "__Host-route-login"
SESSION_DAYS = 7
LOGIN_SECONDS = 600
SMOKE_OWNER = "smoke"
E2E_OWNER = "e2e"
E2E_RUNS_PER_DAY = 3
E2E_RUN_GAP = timedelta(minutes=10)
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


def end_sessions_of_removed_owners(engine: Engine, allowed_ids: set[int]) -> None:
    """Changing OWNER_GITHUB_IDS restarts the API. Deleting a removed owner's sessions here
    means re-adding them later does not bring an old cookie back to life."""
    allowed_owners = [f"github:{user_id}" for user_id in allowed_ids]
    with Session(engine) as session:
        session.execute(
            delete(OwnerSessionRecord).where(OwnerSessionRecord.owner_id.not_in(allowed_owners))
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
        e2e_token_sha256: str | None = None,
        requests_per_minute: int = 60,
        runs_per_day: int = 30,
    ):
        self.engine = engine
        self.github = github
        self.app_origin = app_origin
        self.smoke_token_sha256 = smoke_token_sha256
        self.e2e_token_sha256 = e2e_token_sha256
        self.limit = RequestLimit(requests_per_minute)
        self.runs_per_day = runs_per_day

    def owner(self, request: Request) -> tuple[str, str]:
        """The (owner id, CSRF token) of a signed-in request."""
        owner_id = self.bearer_owner(request)
        csrf = ""
        if owner_id is None:
            owner_id, csrf = self.browser_owner(request)
        elif owner_id == SMOKE_OWNER and request.method not in SAFE_METHODS:
            raise AuthError(403, "read_only", "The smoke test may only read")
        self.limit.check(owner_id)
        return owner_id, csrf

    def bearer_owner(self, request: Request) -> str | None:
        """The deploy workflow's owner whose token the request carries, if any."""
        bearer = request.headers.get("Authorization", "")
        if not bearer.startswith("Bearer "):
            return None
        sent = hashed(bearer.removeprefix("Bearer "))
        if self.smoke_token_sha256 and secrets.compare_digest(sent, self.smoke_token_sha256):
            return SMOKE_OWNER
        if self.e2e_token_sha256 and secrets.compare_digest(sent, self.e2e_token_sha256):
            return E2E_OWNER
        return None

    def browser_owner(self, request: Request) -> tuple[str, str]:
        """The owner of the session cookie, after the Origin and CSRF checks."""
        origin = request.headers.get("Origin")
        if origin is not None and origin != self.app_origin:
            raise AuthError(403, "csrf_failed", "Requests must come from the app's own page")
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise AuthError(401, "not_signed_in", "Sign in first")
        with Session(self.engine) as session:
            record = session.get(OwnerSessionRecord, hashed(token))
            if (
                record is None
                or record.expires_at <= datetime.now(UTC)
                or not self.allowed(record.owner_id)
            ):
                raise AuthError(401, "not_signed_in", "Sign in first")
            owner_id, csrf = record.owner_id, record.csrf_token
        if request.method not in SAFE_METHODS:
            sent = request.headers.get("X-CSRF-Token", "")
            if not secrets.compare_digest(sent.encode(), csrf.encode()):
                raise AuthError(403, "csrf_failed", "Missing or wrong CSRF token")
        return owner_id, csrf

    def allowed(self, owner_id: str) -> bool:
        """Checked on every request, so an owner taken off OWNER_GITHUB_IDS is signed out on
        every instance, including an old one still serving during a deploy."""
        allowed_owners = [f"github:{user_id}" for user_id in self.github.allowed_ids]
        return owner_id in allowed_owners

    def check_run_budget(self, session: Session, owner_id: str) -> None:
        """Refuse a new run once the owner started their daily runs in the last 24 hours,
        and an e2e run within 10 minutes of the last one. Holds a lock on the owner until the
        session's transaction ends, so concurrent requests cannot both pass the same check."""
        session.execute(select(func.pg_advisory_xact_lock(func.hashtext(owner_id))))
        now = datetime.now(UTC)
        runs_per_day = self.runs_per_day
        if owner_id == E2E_OWNER:
            runs_per_day = E2E_RUNS_PER_DAY
            if self.runs_started_since(session, owner_id, now - E2E_RUN_GAP) > 0:
                raise AuthError(
                    429, "run_limit_reached", "The e2e owner may start one run every 10 minutes"
                )
        if self.runs_started_since(session, owner_id, now - timedelta(days=1)) >= runs_per_day:
            raise AuthError(
                429, "run_limit_reached", f"At most {runs_per_day} runs a day; try tomorrow"
            )

    def runs_started_since(self, session: Session, owner_id: str, since: datetime) -> int:
        """Generation runs, plus agent runs that made none (a clarification, or not yet)."""
        started = session.scalar(
            select(func.count())
            .select_from(GenerationRunRecord)
            .where(GenerationRunRecord.owner_id == owner_id)
            .where(GenerationRunRecord.started_at > since)
        )
        unrouted_agent_runs = session.scalar(
            select(func.count())
            .select_from(AgentRunRecord)
            .where(AgentRunRecord.owner_id == owner_id)
            .where(AgentRunRecord.generation_run_id.is_(None))
            .where(AgentRunRecord.started_at > since)
        )
        return (started or 0) + (unrouted_agent_runs or 0)


def auth_from_env(engine: Engine) -> Auth:
    """Reads APP_ORIGIN, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, OWNER_GITHUB_IDS (comma
    separated numeric ids, Tom's by default), SMOKE_TOKEN_SHA256, E2E_TOKEN_SHA256,
    REQUESTS_PER_MINUTE and RUNS_PER_DAY."""
    app_origin = os.environ.get("APP_ORIGIN", "http://127.0.0.1:3000")
    allowed_ids = set()
    for part in os.environ.get("OWNER_GITHUB_IDS", "119127762").split(","):
        if part.strip():
            allowed_ids.add(int(part))
    end_sessions_of_removed_owners(engine, allowed_ids)
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
        e2e_token_sha256=os.environ.get("E2E_TOKEN_SHA256") or None,
        requests_per_minute=int(os.environ.get("REQUESTS_PER_MINUTE", "60")),
        runs_per_day=int(os.environ.get("RUNS_PER_DAY", "30")),
    )
