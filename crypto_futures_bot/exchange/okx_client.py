"""
okx_client.py — OKX API V5 REST implementasyonu (BaseExchange).

- Public uçlar anahtar gerektirmez (market verisi → paper mod bununla çalışır).
- Private uçlar imzalıdır (bakiye, pozisyon, emir → live/demo için anahtar gerekir).
- OKX_DEMO=true iken isteklere `x-simulated-trading: 1` header'ı eklenir.

İmza: base64( HMAC-SHA256( secret, timestamp + method + requestPath + body ) )
Header'lar: OK-ACCESS-KEY / SIGN / TIMESTAMP / PASSPHRASE.

Tüm HTTP çağrıları hataya dayanıklıdır: ağ/limit hatasında üstel bekleme ile
tekrar dener, yine olmazsa istisna fırlatır (üst katman yakalar, bot çökmez).
"""

from __future__ import annotations

import base64
import hmac
import hashlib
import json
import time
from datetime import datetime, timezone

import requests

from exchange.base_exchange import BaseExchange


OKX_BASE_URL = "https://www.okx.com"


class OKXError(Exception):
    """OKX API'den dönen mantıksal hata (sCode != 0 veya code != 0)."""


class OKXClient(BaseExchange):
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        demo: bool = False,
        base_url: str = OKX_BASE_URL,
        timeout: int = 15,
        max_retries: int = 4,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.demo = demo
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    # ------------------------------------------------------------------
    # İç yardımcılar
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        # OKX ISO8601, milisaniye, UTC, sonu 'Z'
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _sign(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        message = f"{timestamp}{method}{request_path}{body}"
        mac = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _headers(self, method: str, request_path: str, body: str, private: bool) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.demo:
            headers["x-simulated-trading"] = "1"
        if private:
            ts = self._timestamp()
            headers.update({
                "OK-ACCESS-KEY": self.api_key,
                "OK-ACCESS-SIGN": self._sign(ts, method, request_path, body),
                "OK-ACCESS-TIMESTAMP": ts,
                "OK-ACCESS-PASSPHRASE": self.passphrase,
            })
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        body: dict | None = None,
        private: bool = False,
    ) -> list:
        """OKX'e istek gönderir, `data` alanını döndürür. Retry + üstel bekleme."""
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        request_path = path + query
        body_str = json.dumps(body) if body else ""
        url = self.base_url + request_path

        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                headers = self._headers(method, request_path, body_str, private)
                resp = self.session.request(
                    method,
                    url,
                    headers=headers,
                    data=body_str if body_str else None,
                    timeout=self.timeout,
                )
                payload = resp.json()
                # OKX zarfı: {"code": "0", "msg": "", "data": [...]}
                if payload.get("code") not in ("0", 0):
                    raise OKXError(f"OKX code={payload.get('code')} msg={payload.get('msg')} "
                                   f"data={payload.get('data')}")
                return payload.get("data", [])
            except (requests.RequestException, ValueError) as exc:
                # ağ / JSON çözümleme hatası → tekrar dene
                last_err = exc
                sleep_s = 2 ** attempt
                time.sleep(sleep_s)
            except OKXError:
                # mantıksal API hatası: tekrar denemek anlamsız, hemen yükselt
                raise
        raise OKXError(f"OKX isteği {self.max_retries} denemede başarısız: {last_err}")

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_swap_symbols(self) -> list[dict]:
        data = self._request("GET", "/api/v5/public/instruments",
                             params={"instType": "SWAP"})
        out = []
        for it in data:
            # Sadece USDT teminatlı perpetual swap
            if it.get("settleCcy") != "USDT":
                continue
            if it.get("state") != "live":
                continue
            out.append({
                "symbol": it["instId"],
                "ct_val": float(it.get("ctVal", "1") or 1),
                "min_size": float(it.get("minSz", "1") or 1),
                "tick_size": float(it.get("tickSz", "0.0001") or 0.0001),
                "lot_size": float(it.get("lotSz", "1") or 1),
            })
        return out

    def get_ticker(self, symbol: str) -> dict:
        data = self._request("GET", "/api/v5/market/ticker",
                             params={"instId": symbol})
        if not data:
            raise OKXError(f"Ticker verisi boş: {symbol}")
        t = data[0]
        return {
            "last": float(t["last"]),
            "bid": float(t["bidPx"]) if t.get("bidPx") else float(t["last"]),
            "ask": float(t["askPx"]) if t.get("askPx") else float(t["last"]),
            "vol_ccy_24h": float(t.get("volCcy24h", 0) or 0),
        }

    def get_all_tickers(self) -> list[dict]:
        data = self._request("GET", "/api/v5/market/tickers",
                             params={"instType": "SWAP"})
        out = []
        for t in data:
            if not t.get("instId", "").endswith("-USDT-SWAP"):
                continue
            last = float(t.get("last", 0) or 0)
            if last <= 0:
                continue
            out.append({
                "symbol": t["instId"],
                "last": last,
                "bid": float(t["bidPx"]) if t.get("bidPx") else last,
                "ask": float(t["askPx"]) if t.get("askPx") else last,
                "vol_ccy_24h": float(t.get("volCcy24h", 0) or 0),
            })
        return out

    def get_candles(self, symbol: str, timeframe: str, limit: int = 200) -> list[list]:
        data = self._request("GET", "/api/v5/market/candles",
                             params={"instId": symbol, "bar": timeframe, "limit": limit})
        # OKX yeniden eskiye döndürür → eskiden yeniye çevir.
        # Ham format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        candles = []
        for row in reversed(data):
            candles.append([
                int(row[0]),        # timestamp (ms)
                float(row[1]),      # open
                float(row[2]),      # high
                float(row[3]),      # low
                float(row[4]),      # close
                float(row[5]),      # volume (kontrat/coin)
            ])
        return candles

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def get_balance(self, ccy: str = "USDT") -> float:
        data = self._request("GET", "/api/v5/account/balance",
                             params={"ccy": ccy}, private=True)
        if not data:
            return 0.0
        for detail in data[0].get("details", []):
            if detail.get("ccy") == ccy:
                # availBal: kullanılabilir bakiye
                return float(detail.get("availBal") or detail.get("cashBal") or 0)
        return 0.0

    def get_positions(self) -> list[dict]:
        data = self._request("GET", "/api/v5/account/positions",
                             params={"instType": "SWAP"}, private=True)
        out = []
        for p in data:
            pos = float(p.get("pos", 0) or 0)
            if pos == 0:
                continue
            out.append({
                "symbol": p["instId"],
                "side": "long" if p.get("posSide") == "long" or pos > 0 else "short",
                "size": abs(pos),
                "entry_price": float(p.get("avgPx", 0) or 0),
                "leverage": float(p.get("lever", 0) or 0),
                "margin": float(p.get("margin", 0) or p.get("imr", 0) or 0),
                "liq_price": float(p.get("liqPx", 0) or 0) if p.get("liqPx") else 0.0,
                "upl": float(p.get("upl", 0) or 0),
            })
        return out

    def set_leverage(self, symbol: str, leverage: int, margin_mode: str) -> dict:
        body = {
            "instId": symbol,
            "lever": str(leverage),
            "mgnMode": margin_mode,   # "isolated"
        }
        data = self._request("POST", "/api/v5/account/set-leverage",
                             body=body, private=True)
        return data[0] if data else {}

    def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "limit",
        price: float | None = None,
        reduce_only: bool = False,
        pos_side: str | None = None,
    ) -> dict:
        body = {
            "instId": symbol,
            "tdMode": "isolated",
            "side": side,
            "ordType": order_type,
            "sz": str(size),
            "reduceOnly": reduce_only,
        }
        if pos_side:
            body["posSide"] = pos_side
        if order_type == "limit":
            if price is None:
                raise OKXError("Limit emir için fiyat zorunlu.")
            body["px"] = str(price)
        data = self._request("POST", "/api/v5/trade/order", body=body, private=True)
        r = data[0] if data else {}
        if r.get("sCode") not in ("0", 0, None):
            raise OKXError(f"Emir reddedildi sCode={r.get('sCode')} sMsg={r.get('sMsg')}")
        return {
            "order_id": r.get("ordId", ""),
            "status": "submitted",
            "raw": r,
        }

    def place_stop_loss(
        self,
        symbol: str,
        side: str,
        size: float,
        trigger_price: float,
        pos_side: str | None = None,
    ) -> dict:
        # OKX algo order: reduce-only stop-market. Bot çökse bile borsada asılı kalır.
        body = {
            "instId": symbol,
            "tdMode": "isolated",
            "side": side,
            "ordType": "conditional",
            "sz": str(size),
            "reduceOnly": True,
            "slTriggerPx": str(trigger_price),
            "slOrdPx": "-1",              # -1 = market (garantili tetiklenince piyasa emri)
            "slTriggerPxType": "last",
        }
        if pos_side:
            body["posSide"] = pos_side
        data = self._request("POST", "/api/v5/trade/order-algo", body=body, private=True)
        r = data[0] if data else {}
        if r.get("sCode") not in ("0", 0, None):
            raise OKXError(f"Stop reddedildi sCode={r.get('sCode')} sMsg={r.get('sMsg')}")
        return {"algo_id": r.get("algoId", ""), "status": "submitted", "raw": r}

    def amend_stop_loss(self, symbol: str, algo_id: str, new_trigger_price: float) -> dict:
        body = {
            "instId": symbol,
            "algoId": algo_id,
            "newSlTriggerPx": str(new_trigger_price),
        }
        data = self._request("POST", "/api/v5/trade/amend-algos", body=body, private=True)
        return data[0] if data else {}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        body = {"instId": symbol, "ordId": order_id}
        data = self._request("POST", "/api/v5/trade/cancel-order", body=body, private=True)
        return data[0] if data else {}

    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        body = [{"instId": symbol, "algoId": algo_id}]
        data = self._request("POST", "/api/v5/trade/cancel-algos", body=body, private=True)
        return data[0] if data else {}

    def get_order(self, symbol: str, order_id: str) -> dict:
        data = self._request("GET", "/api/v5/trade/order",
                             params={"instId": symbol, "ordId": order_id}, private=True)
        if not data:
            return {"status": "unknown", "filled_size": 0.0, "avg_price": 0.0}
        o = data[0]
        state_map = {
            "live": "open", "partially_filled": "partial",
            "filled": "filled", "canceled": "canceled",
        }
        return {
            "status": state_map.get(o.get("state", ""), o.get("state", "")),
            "filled_size": float(o.get("accFillSz", 0) or 0),
            "avg_price": float(o.get("avgPx", 0) or 0),
        }
