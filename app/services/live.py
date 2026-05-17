from app.core.config import Settings, get_settings
from app.domain.schemas import LiveReadiness


class LiveTradingReadinessService:
    """Reports readiness while keeping live trading disabled.

    Broker order execution must stay unavailable until compliance and safety gates pass.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def status(self) -> LiveReadiness:
        checklist = {
            "paper_mode_validated": True,
            "upstox_credentials_configured": bool(self.settings.upstox_access_token),
            "kyc_and_user_consent_completed": False,
            "broker_order_adapter_implemented": False,
            "dual_confirmation_enabled": False,
            "kill_switch_enabled": False,
            "regulatory_review_completed": False,
        }
        return LiveReadiness(
            enabled=False,
            reason="Live trading is intentionally disabled until all compliance gates pass.",
            checklist=checklist,
        )
