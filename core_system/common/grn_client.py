from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings


class GRNServiceError(RuntimeError):
    pass


class GRNServiceClient:
    def __init__(self, *, base_url: str | None = None, api_key: str | None = None, timeout: int = 30):
        self.base_url = (base_url or settings.GRN_SERVICE_BASE_URL or "").rstrip("/")
        self.api_key = api_key or settings.GRN_SERVICE_API_KEY
        self.timeout = timeout

        if not self.base_url:
            raise GRNServiceError("GRN_SERVICE_BASE_URL is not configured.")

    def request(self, method: str, path: str, payload: dict | None = None):
        body = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        if self.api_key:
            headers["X-API-Key"] = self.api_key

        request = Request(
            url=f"{self.base_url}/{path.lstrip('/')}",
            data=body,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                content = response.read().decode("utf-8").strip()
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8").strip()
            raise GRNServiceError(f"GRN service returned {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise GRNServiceError(f"Unable to reach GRN service: {exc.reason}") from exc

        if not content:
            return None

        return json.loads(content)

    def fetch_grn(self, *, grn_no: str | None = None):
        path = "api/grn/"
        if grn_no:
            path = f"{path}?grn_no={quote(grn_no)}"
        return self.request("GET", path)

    def move_grn_to_qcr(self, grn_id: int):
        return self.request("POST", f"api/grn/{grn_id}/move-to-qcr/", payload={})

