from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings, get_settings
from app.domain.schemas import Candle, IndicatorSnapshot, MarketQuote
from app.services.indicators import IndicatorEngine


class MarketDataProvider(ABC):
    @abstractmethod
    async def get_quote(self, symbol: str) -> MarketQuote:
        raise NotImplementedError

    @abstractmethod
    async def get_indicators(self, symbol: str) -> IndicatorSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def get_candles(self, symbol: str, limit: int = 80) -> list[Candle]:
        raise NotImplementedError


class MockMarketDataProvider(MarketDataProvider):
    async def get_quote(self, symbol: str) -> MarketQuote:
        price = 125.5 if symbol.endswith("CE") else 118.2
        return MarketQuote(
            symbol=symbol,
            instrument_key=f"MOCK::{symbol}",
            ltp=price,
            bid=round(price - 0.2, 2),
            ask=round(price + 0.3, 2),
            volume=125_000,
            open_interest=450_000,
            source="mock",
        )

    async def get_indicators(self, symbol: str) -> IndicatorSnapshot:
        candles = await self.get_candles(symbol)
        snapshot = IndicatorEngine().snapshot(symbol, candles)
        # Keep the default mock signal in BUY territory for deterministic demos/tests.
        snapshot.indicators["rsi_14"] = 58.3
        snapshot.indicators["pcr"] = 1.12
        snapshot.indicators["oi_change_pct"] = 4.7
        return snapshot

    async def get_candles(self, symbol: str, limit: int = 80) -> list[Candle]:
        base = 120.0 if symbol.endswith("CE") else 116.0
        now = datetime.now(UTC)
        candles: list[Candle] = []
        for index in range(limit):
            drift = index * 0.08
            wave = (index % 7) * 0.12
            close = round(base + drift + wave, 2)
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=now - timedelta(minutes=(limit - index) * 5),
                    open=round(close - 0.3, 2),
                    high=round(close + 0.7, 2),
                    low=round(close - 0.8, 2),
                    close=close,
                    volume=100_000 + index * 350,
                )
            )
        return candles


class UpstoxMarketDataProvider(MarketDataProvider):
    """Upstox adapter boundary for production market-data ingestion."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = "https://api.upstox.com/v2"

    async def get_quote(self, symbol: str) -> MarketQuote:
        if not self.settings.upstox_access_token:
            raise RuntimeError("UPSTOX_ACCESS_TOKEN is required for the Upstox provider")
        import json

        query = urlencode({"instrument_key": symbol})
        request = Request(
            f"{self.base_url}/market-quote/quotes?{query}",
            headers={"Authorization": f"Bearer {self.settings.upstox_access_token}"},
        )
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - URL is fixed Upstox API.
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"Upstox quote request failed: {exc}") from exc
        data = payload.get("data", {})
        item = next(iter(data.values()), {}) if data else {}
        ltp = item.get("last_price") or item.get("ltp")
        if not ltp:
            raise RuntimeError(f"Upstox quote missing last price for {symbol}")
        return MarketQuote(
            symbol=symbol,
            instrument_key=symbol,
            ltp=float(ltp),
            volume=int(item.get("volume", 0) or 0),
            open_interest=int(item.get("oi", 0) or 0),
            source="upstox",
        )

    async def get_indicators(self, symbol: str) -> IndicatorSnapshot:
        candles = await self.get_candles(symbol)
        return IndicatorEngine().snapshot(symbol, candles)

    async def get_candles(self, symbol: str, limit: int = 80) -> list[Candle]:
        quote = await self.get_quote(symbol)
        now = datetime.now(UTC)
        return [
            Candle(
                symbol=symbol,
                timestamp=now - timedelta(minutes=(limit - index) * 5),
                open=quote.ltp,
                high=quote.ltp,
                low=quote.ltp,
                close=quote.ltp,
                volume=quote.volume,
            )
            for index in range(limit)
        ]


def get_market_provider(settings: Settings | None = None) -> MarketDataProvider:
    settings = settings or get_settings()
    if settings.market_provider.lower() == "upstox":
        return UpstoxMarketDataProvider(settings)
    return MockMarketDataProvider()
