import hashlib
import hmac
import secrets
from uuid import UUID

from app.domain.schemas import AuthToken, User
from app.services.audit import AuditService
from app.services.repository import InMemoryRepository, repository


class AuthService:
    """Small local auth service for MVP demos; replace with OAuth/KYC in production."""

    def __init__(self, repo: InMemoryRepository = repository) -> None:
        self.repo = repo
        self.audit = AuditService(repo)

    def register(self, email: str, password: str) -> AuthToken:
        self._validate(email, password)
        if any(user.email == email for user in self.repo.users.values()):
            raise ValueError("email is already registered")
        user = User(email=email, password_hash=self._hash(password))
        self.repo.users[user.id] = user
        token = self._issue(user.id)
        self.audit.record(
            event_type="user_registered",
            source="auth_service",
            user_id=str(user.id),
            payload={"email": email, "kyc_status": user.kyc_status},
        )
        return AuthToken(token=token, user=user)

    def login(self, email: str, password: str) -> AuthToken:
        password_hash = self._hash(password)
        for user in self.repo.users.values():
            if user.email == email and hmac.compare_digest(user.password_hash, password_hash):
                return AuthToken(token=self._issue(user.id), user=user)
        raise ValueError("invalid email or password")

    def me(self, token: str) -> User:
        user_id = self.repo.sessions.get(token)
        if not user_id or user_id not in self.repo.users:
            raise KeyError("invalid or expired session")
        return self.repo.users[user_id]

    def _issue(self, user_id: UUID) -> str:
        token = secrets.token_urlsafe(32)
        self.repo.sessions[token] = user_id
        return token

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate(email: str, password: str) -> None:
        if "@" not in email:
            raise ValueError("valid email is required")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
