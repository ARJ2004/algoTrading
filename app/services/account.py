from uuid import UUID

from app.core.config import Settings, get_settings
from app.domain.schemas import PaperAccount, PaperAccountCreate, RiskProfile
from app.services.audit import AuditService
from app.services.repository import InMemoryRepository, repository


class AccountService:
    def __init__(
        self,
        repo: InMemoryRepository = repository,
        settings: Settings | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.repo = repo
        self.settings = settings or get_settings()
        self.audit = audit or AuditService(repo)

    def create_paper_account(self, request: PaperAccountCreate) -> PaperAccount:
        profile = request.risk_profile or RiskProfile(
            risk_per_trade_pct=self.settings.default_risk_per_trade_pct,
            max_open_positions=self.settings.max_open_positions,
            default_slippage_pct=self.settings.default_slippage_pct,
            fee_per_order=self.settings.default_fee_per_order,
            min_ai_confidence=self.settings.min_ai_confidence,
        )
        account = PaperAccount(
            user_id=request.user_id,
            initial_capital=request.initial_capital,
            available_cash=request.initial_capital,
            risk_profile=profile,
        )
        self.repo.accounts[account.id] = account
        self.audit.record(
            event_type="paper_account_created",
            source="account_service",
            user_id=account.user_id,
            payload={"account_id": str(account.id), "initial_capital": account.initial_capital},
        )
        return account

    def update_risk_profile(self, account_id: UUID, updates: dict) -> PaperAccount:
        account = self.repo.accounts.get(account_id)
        if not account:
            raise KeyError("paper account not found")
        current = account.risk_profile
        merged = {**current.__dict__, **updates}
        account.risk_profile = RiskProfile(**merged)
        self.audit.record(
            event_type="risk_profile_updated",
            source="account_service",
            user_id=account.user_id,
            payload={"account_id": str(account.id), "risk_profile": account.risk_profile},
        )
        return account
