import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

API_VERSION = "2026-10"
MAX_RETRIES = 5


def throttle_wait_seconds(cost: dict | None) -> float:
    """Seconds to wait so the next query of the same cost fits in the bucket.

    Shopify's GraphQL API refills query points at `restoreRate` per second up to
    `maximumAvailable`; `cost` is the response's extensions.cost.
    """
    if not cost:
        return 0.0
    status = cost["throttleStatus"]
    needed = cost["requestedQueryCost"] - status["currentlyAvailable"]
    return max(0.0, needed / status["restoreRate"])


class ShopifyClient:
    def __init__(self) -> None:
        self.domain = os.environ["SHOPIFY_STORE_DOMAIN"].strip()
        self.http = httpx.Client(timeout=30)
        self.token = self._fetch_token()

    def _fetch_token(self) -> str:
        """Client credentials grant; the token lasts 24h, longer than any run."""
        response = self.http.post(
            f"https://{self.domain}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": os.environ["SHOPIFY_CLIENT_ID"].strip(),
                "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"].strip(),
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """Run a query, retrying when throttled and pausing when the bucket runs low."""
        for _ in range(MAX_RETRIES):
            response = self.http.post(
                f"https://{self.domain}/admin/api/{API_VERSION}/graphql.json",
                headers={"X-Shopify-Access-Token": self.token},
                json={"query": query, "variables": variables or {}},
            )
            response.raise_for_status()
            body = response.json()
            cost = body.get("extensions", {}).get("cost")
            errors = body.get("errors") or []
            if any(e.get("extensions", {}).get("code") == "THROTTLED" for e in errors):
                time.sleep(max(1.0, throttle_wait_seconds(cost)))
                continue
            if errors:
                raise RuntimeError(f"Shopify GraphQL errors: {errors}")
            time.sleep(throttle_wait_seconds(cost))
            return body["data"]
        raise RuntimeError("Shopify API still throttled after retries")
