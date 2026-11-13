"""Minimal dependency-free OANDA v3 REST client (practice + live hosts).

Uses only the Python standard library so it drops into the FRIDAY Universe
repo with zero pip dependencies.
"""
import json
import urllib.error
import urllib.request

API_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com/v3",
    "live": "https://api-fxtrade.oanda.com/v3",
}


class OandaError(RuntimeError):
    """Raised for any OANDA API failure (HTTP or transport)."""


class OandaClient:
    def __init__(self, token, environment="practice", timeout=30):
        if environment not in API_HOSTS:
            raise ValueError(f"unknown environment: {environment}")
        self.token = token
        self.timeout = timeout
        self.base = API_HOSTS[environment]

    # ------------------------------------------------------------------ core
    def _request(self, method, path, body=None, query=""):
        url = self.base + path
        if query:
            url += "?" + query
        payload = None
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept-Datetime-Format": "UNIX",
        }
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise OandaError(f"OANDA HTTP {exc.code} on {method} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise OandaError(f"OANDA connection failed on {method} {path}: {exc.reason}") from exc

    # -------------------------------------------------------------- accounts
    def list_accounts(self):
        return self._request("GET", "/accounts")

    def account_summary(self, account_id):
        return self._request("GET", f"/accounts/{account_id}/summary")

    # --------------------------------------------------- instruments / data
    def instruments(self, account_id, names):
        return self._request(
            "GET", f"/accounts/{account_id}/instruments",
            query="instruments=" + ",".join(names),
        )

    def candles(self, instrument, granularity="H1", count=400, price="M", smooth=False,
                to_time=None):
        query = (f"granularity={granularity}&count={count}&price={price}"
                 f"&smooth={str(smooth).lower()}")
        if to_time is not None:
            query += f"&to={to_time:.0f}"
        return self._request("GET", f"/instruments/{instrument}/candles", query=query)

    def pricing(self, account_id, instruments):
        return self._request(
            "GET", f"/accounts/{account_id}/pricing",
            query="instruments=" + ",".join(instruments),
        )

    # ----------------------------------------------------- orders / trades
    def create_order(self, account_id, order):
        return self._request("POST", f"/accounts/{account_id}/orders", body=order)

    def open_trades(self, account_id):
        return self._request("GET", f"/accounts/{account_id}/trades")

    def trade_details(self, account_id, trade_id):
        return self._request("GET", f"/accounts/{account_id}/trades/{trade_id}")

    def modify_trade_protective_orders(self, account_id, trade_id, stop_loss=None, take_profit=None):
        body = {}
        if stop_loss is not None:
            body["stopLoss"] = {"price": str(stop_loss), "timeInForce": "GTC"}
        if take_profit is not None:
            body["takeProfit"] = {"price": str(take_profit), "timeInForce": "GTC"}
        return self._request(
            "PUT", f"/accounts/{account_id}/trades/{trade_id}/orders", body=body,
        )

    def close_trade(self, account_id, trade_id, units=None):
        body = {"units": str(units)} if units is not None else {}
        return self._request(
            "PUT", f"/accounts/{account_id}/trades/{trade_id}/close", body=body,
        )
