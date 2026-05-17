from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.config import Settings, get_settings
from app.domain.schemas import AISignal
from app.services.ai import AIProvider, get_ai_provider
from app.services.audit import AuditService
from app.services.market import MarketDataProvider, get_market_provider
from app.services.repository import InMemoryRepository, repository


class SignalService:
    def __init__(
        self,
        repo: InMemoryRepository = repository,
        ai_provider: AIProvider | None = None,
        market_provider: MarketDataProvider | None = None,
        audit: AuditService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repo = repo
        settings = settings or get_settings()
        self.ai_provider = ai_provider or get_ai_provider(settings)
        self.market_provider = market_provider or get_market_provider(settings)
        self.audit = audit or AuditService(repo)
        self.settings = settings

    async def generate(self, account_id: UUID, symbol: str) -> AISignal:
        account = self.repo.accounts.get(account_id)
        if not account:
            raise KeyError("paper account not found")
        correlation_id = uuid4()
        quote = await self.market_provider.get_quote(symbol)
        quote_age = (datetime.now(UTC) - quote.timestamp).total_seconds()
        if quote_age > self.settings.market_data_max_age_seconds:
            raise RuntimeError("market data is stale; signal generation blocked")
        indicators = await self.market_provider.get_indicators(symbol)
        self.audit.record(
            event_type="market_snapshot_captured",
            source="market_provider",
            user_id=account.user_id,
            correlation_id=correlation_id,
            payload={"quote": quote, "indicators": indicators},
        )
        signal = await self.ai_provider.generate_signal(account, quote, indicators, correlation_id)
        self.repo.signals[signal.id] = signal
        self.audit.record(
            event_type="ai_signal_generated",
            source="ai_provider",
            user_id=account.user_id,
            correlation_id=correlation_id,
            payload={"signal": signal},
        )
        return signal
