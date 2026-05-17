from abc import ABC, abstractmethod
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import Settings, get_settings
from app.domain.enums import SignalAction
from app.domain.schemas import AISignal, IndicatorSnapshot, MarketQuote, PaperAccount, serialize


class AIProvider(ABC):
    @abstractmethod
    async def generate_signal(
        self,
        account: PaperAccount,
        quote: MarketQuote,
        indicators: IndicatorSnapshot,
        correlation_id: UUID,
    ) -> AISignal:
        raise NotImplementedError


class MockAIProvider(AIProvider):
    async def generate_signal(
        self,
        account: PaperAccount,
        quote: MarketQuote,
        indicators: IndicatorSnapshot,
        correlation_id: UUID,
    ) -> AISignal:
        rsi = indicators.indicators.get("rsi_14", 50)
        action = SignalAction.BUY if rsi < 70 else SignalAction.HOLD
        return AISignal(
            account_id=account.id,
            symbol=quote.symbol,
            action=action,
            confidence=0.72 if action != SignalAction.HOLD else 0.45,
            stop_loss=round(quote.ltp * 0.9, 2) if action != SignalAction.HOLD else None,
            take_profit=round(quote.ltp * 1.2, 2) if action != SignalAction.HOLD else None,
            rationale=(
                "Mock signal: trend remains constructive, price is above VWAP, "
                "and RSI is not overbought."
            ),
            raw_response={"provider": "mock", "correlation_id": str(correlation_id)},
        )


class OllamaAIProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate_signal(
        self,
        account: PaperAccount,
        quote: MarketQuote,
        indicators: IndicatorSnapshot,
        correlation_id: UUID,
    ) -> AISignal:
        import json

        prompt = self._build_prompt(account, quote, indicators)
        headers = {"Content-Type": "application/json"}
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"
        request = Request(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
            data=json.dumps(
                {
                    "model": self.settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                }
            ).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - user-configured endpoint.
                data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Ollama signal request failed: {exc}") from exc

        raw_text = data.get("response", "{}")
        try:
            parsed: dict[str, Any] = json.loads(raw_text)
            return AISignal(
                account_id=account.id,
                symbol=parsed.get("symbol", quote.symbol),
                action=parsed.get("action", "HOLD"),
                confidence=float(parsed.get("confidence", 0)),
                entry_type=parsed.get("entry_type", "MARKET"),
                stop_loss=parsed.get("stop_loss"),
                take_profit=parsed.get("take_profit"),
                rationale=parsed.get("rationale", "Ollama returned no rationale."),
                raw_response={
                    "provider": "ollama",
                    "ollama": data,
                    "correlation_id": str(correlation_id),
                },
            )
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"Invalid Ollama signal response: {raw_text}") from exc

    @staticmethod
    def _build_prompt(
        account: PaperAccount,
        quote: MarketQuote,
        indicators: IndicatorSnapshot,
    ) -> str:
        return f"""
You are an options trading assistant for PAPER TRADING ONLY.
Return JSON only. Required keys: action, symbol, entry_type, confidence, stop_loss,
take_profit, rationale.
Allowed action values: BUY, SELL, HOLD. Never suggest live order execution.

Account: {serialize(account)}
Market quote: {serialize(quote)}
Indicators: {serialize(indicators)}
""".strip()


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    if settings.ai_provider.lower() == "ollama":
        return OllamaAIProvider(settings)
    return MockAIProvider()
