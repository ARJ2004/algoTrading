"""Reserved for future framework route adapters.

The current MVP uses the standard-library HTTP server in app.main so it can run in
restricted environments without downloading dependencies. The service layer is intentionally
framework-agnostic and can be mounted behind FastAPI, Django, or another router later.
"""
