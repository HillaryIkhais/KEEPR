"""HTTP client for the authoritative ledger service.

Same `.fetch()` interface as AuthoritativeSource, but talks over real HTTP.
"""
from __future__ import annotations

import httpx

DEFAULT_URL = "http://127.0.0.1:8001"


class AuthoritativeLedgerClient:
    """Fetch authoritative records over HTTP from the ledger server."""

    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.calls: list[str] = []

    def fetch(self, invoice_id: str) -> dict:
        self.calls.append(invoice_id)
        url = f"{self.base_url}/ledger/{invoice_id}"
        try:
            resp = httpx.get(url, timeout=self.timeout)
            if resp.status_code == 503:
                return {"ok": False, "error": "HTTP_503 SERVICE_UNAVAILABLE",
                        "tool": "authoritative_ledger",
                        "meta": {"source": "authoritative_ledger"}}
            if resp.status_code == 404:
                return {"ok": False, "error": "HTTP_404 NOT_FOUND",
                        "tool": "authoritative_ledger",
                        "meta": {"source": "authoritative_ledger"}}
            resp.raise_for_status()
            data = resp.json()
            return {"ok": True, "data": data,
                    "meta": {"source": "authoritative_ledger",
                             "observed_at": data.get("updated_at", "")}}
        except httpx.ConnectError:
            return {"ok": False, "error": "CONNECTION_REFUSED",
                    "tool": "authoritative_ledger",
                    "meta": {"source": "authoritative_ledger"}}
        except Exception as e:
            return {"ok": False, "error": f"HTTP_ERROR: {e}",
                    "tool": "authoritative_ledger",
                    "meta": {"source": "authoritative_ledger"}}
