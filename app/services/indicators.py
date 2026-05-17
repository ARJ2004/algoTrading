from app.domain.schemas import Candle, IndicatorSnapshot, utc_now


class IndicatorEngine:
    """Calculates core MVP indicators from candles and option-chain derived values."""

    def snapshot(
        self,
        symbol: str,
        candles: list[Candle],
        put_oi: int = 560_000,
        call_oi: int = 500_000,
    ) -> IndicatorSnapshot:
        if not candles:
            raise ValueError("at least one candle is required")
        closes = [candle.close for candle in candles]
        volumes = [candle.volume for candle in candles]
        indicators = {
            "sma_20": self.sma(closes, 20),
            "ema_20": self.ema(closes, 20),
            "rsi_14": self.rsi(closes, 14),
            "vwap": self.vwap(candles),
            "pcr": round(put_oi / call_oi, 4) if call_oi else 0.0,
            "oi_change_pct": 4.7,
            "volume": float(volumes[-1]),
        }
        return IndicatorSnapshot(
            symbol=symbol,
            timeframe="5m",
            timestamp=utc_now(),
            indicators=indicators,
        )

    @staticmethod
    def sma(values: list[float], period: int) -> float:
        window = values[-period:] if len(values) >= period else values
        return round(sum(window) / len(window), 4)

    @staticmethod
    def ema(values: list[float], period: int) -> float:
        if not values:
            return 0.0
        multiplier = 2 / (period + 1)
        ema = values[0]
        for value in values[1:]:
            ema = (value - ema) * multiplier + ema
        return round(ema, 4)

    @staticmethod
    def rsi(values: list[float], period: int) -> float:
        if len(values) < 2:
            return 50.0
        deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
        window = deltas[-period:]
        gains = [delta for delta in window if delta > 0]
        losses = [-delta for delta in window if delta < 0]
        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0
        if avg_loss == 0:
            return 100.0 if avg_gain else 50.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 4)

    @staticmethod
    def vwap(candles: list[Candle]) -> float:
        total_volume = sum(candle.volume for candle in candles)
        if not total_volume:
            return candles[-1].close
        total = sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles)
        return round(total / total_volume, 4)
