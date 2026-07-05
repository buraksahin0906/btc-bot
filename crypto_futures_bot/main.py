"""
main.py — Crypto Futures Trading Bot orkestrasyonu (OKX V5).

GÜVENLİK ÖZETİ:
  - Varsayılan paper_trade=True, live_trading=False → hiçbir gerçek emir gönderilmez.
  - Gerçek emir SADECE live_trading=True VE paper_trade=False iken.
  - Live'a geçişte terminalde büyük harf `LIVE` onayı istenir.

Döngü (her scan_interval_seconds): bakiye → açık pozisyon yönet → risk kapıları →
coin tara → indikatör/skor → sinyal → (geçerse) işlem aç → net hedef+stop+trailing
→ rapor → SQLite/CSV. API hatasında bot çökmez, bekleyip devam eder.

ÇALIŞTIRMA (bu klasörden):  python main.py
"""

from __future__ import annotations

import sys
import time

from config import CONFIG, SECRETS
from data.candle_fetcher import CandleFetcher
from data.market_scanner import MarketScanner
from exchange.okx_client import OKXClient
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager
from notifier.telegram_notifier import TelegramNotifier
from paper.paper_trader import PaperTrader
from persistence.state_store import StateStore
from risk.position_sizer import compute_position_size, liquidation_price
from risk.risk_manager import RiskManager
from strategy.signal_engine import evaluate_symbol, pick_best_signal

# logs paketi hem modül (trade_logger) hem log çıktısı klasörü
from logs.trade_logger import TradeLogger, setup_logger


# ======================================================================
# Kurulum
# ======================================================================

def is_live_mode() -> bool:
    """Gerçek emir gönderilecek mi? Çift katmanlı güvenlik."""
    return CONFIG.live_trading and not CONFIG.paper_trade


def confirm_live_or_exit(logger) -> None:
    """Live modda terminal onayı ister. Kullanıcı 'LIVE' yazmazsa çıkar."""
    print("\n" + "!" * 60)
    print("  DİKKAT: GERÇEK PARA / CANLI İŞLEM MODU AKTİF")
    print("  Bu mod gerçek emir gönderir ve gerçek para riski taşır.")
    print("  Devam etmek için büyük harflerle LIVE yazın, iptal için Enter.")
    print("!" * 60)
    try:
        answer = input("Onay > ").strip()
    except EOFError:
        answer = ""
    if answer != "LIVE":
        logger.info("Canlı işlem onayı verilmedi. Bot güvenli şekilde durduruldu.")
        sys.exit(0)
    if not SECRETS.has_okx_keys():
        logger.error("Canlı mod için OKX API anahtarları eksik (.env). Durduruluyor.")
        sys.exit(1)
    logger.warning("Canlı işlem onaylandı. Gerçek emirler gönderilecek.")


def build_exchange() -> OKXClient:
    return OKXClient(
        api_key=SECRETS.okx_api_key,
        api_secret=SECRETS.okx_api_secret,
        passphrase=SECRETS.okx_api_passphrase,
        demo=SECRETS.okx_demo,
    )


def get_balance(exchange, paper: PaperTrader, live: bool) -> float:
    """Aktif bakiye: live'da borsadan, paper'da simülasyondan."""
    if live:
        try:
            return exchange.get_balance("USDT")
        except Exception:  # noqa: BLE001
            return 0.0
    return paper.get_balance()


# ======================================================================
# Borsa senkronizasyonu (açılışta)
# ======================================================================

def sync_with_exchange(exchange, state: StateStore, live: bool, logger) -> None:
    """SQLite açık pozisyonu ile borsayı karşılaştırır. Çelişkide BORSA esastır.

    Paper modda borsada gerçek pozisyon olmaz; SQLite kaydı korunur (kaldığı yerden).
    """
    saved = state.get_open_position()
    if not live:
        if saved:
            logger.info(f"Paper: kayıtlı açık pozisyon devralındı → {saved['symbol']} "
                        f"{saved['direction']}")
        return

    try:
        exch_positions = exchange.get_positions()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Borsa pozisyonları çekilemedi, senkron atlanıyor: {exc}")
        return

    exch_by_symbol = {p["symbol"]: p for p in exch_positions}

    if saved and saved["symbol"] not in exch_by_symbol:
        logger.warning(f"SQLite'ta var ama borsada yok ({saved['symbol']}) → "
                       f"pozisyon kapanmış, kayıt temizleniyor")
        state.clear_open_position()
        saved = None

    for sym, p in exch_by_symbol.items():
        if not saved or saved["symbol"] != sym:
            logger.warning(f"Borsada açık pozisyon var ama SQLite'ta yok ({sym}) → "
                           f"yönetime alınıyor (borsa gerçeği esas)")
            # Minimum alanlarla kaydı oluştur; trailing sıfırdan başlar.
            state.save_open_position({
                "symbol": sym, "direction": p["side"], "entry_price": p["entry_price"],
                "contracts": p["size"], "ct_val": 0.0, "entry_maker": False,
                "stop_price": 0.0, "algo_id": "", "net_target": 0.0,
                "peak_net": 0.0, "trailing_active": False,
                "stop_moved_to_entry": False, "opened_ts": time.time(),
                "adopted_from_exchange": True,
            })


# ======================================================================
# İşlem açma
# ======================================================================

def try_open_trade(signal, ctx) -> bool:
    """Sinyali işleme çevirir: boyut, stop doğrulama, giriş, stop, trailing planı.

    ctx: çalışma bağlamı (exchange, scanner, orders, state, risk, paper, ...).
    Döndürür: pozisyon açıldıysa True.
    """
    log = ctx["log"]
    symbol = signal.symbol
    scanner: MarketScanner = ctx["scanner"]
    inst = scanner.get_instrument(symbol)
    if not inst:
        log.info(f"{symbol} enstrüman bilgisi yok, atlanıyor")
        return False

    balance = ctx["balance"]
    price = signal.entry_price
    direction = signal.direction

    # 1) Reentry cooldown
    r = ctx["risk"].check_reentry(symbol)
    if not r.allowed:
        log.info(f"{symbol} atlandı: {r.reason}")
        return False

    # 2) Pozisyon boyutu (margin = bakiye %2, 2x)
    size = compute_position_size(
        balance, price, inst["ct_val"], inst["lot_size"], inst["min_size"]
    )
    if size is None:
        log.info(f"{symbol} atlandı: geçerli pozisyon boyutu hesaplanamadı "
                 f"(bakiye {balance:.2f} yetersiz olabilir)")
        return False

    # 3) Net kâr hedefi (açılışta KİLİTLENİR)
    net_target = balance * (CONFIG.net_profit_target_percent_of_balance / 100.0)

    # 4) Stop (ATR bazlı) + R/R doğrulama
    atr = signal.atr or price * 0.005
    stop_dist = atr * CONFIG.atr_stop_multiplier
    stop = price - stop_dist if direction == "long" else price + stop_dist

    # Stop mesafesi net hedeften büyükse spec kuralı uygula
    stop_loss_usdt = size.notional_usdt * (stop_dist / price)
    if stop_loss_usdt > net_target:
        if CONFIG.stop_wider_than_target_action == "clamp":
            # Stop'u kâr hedefine denk gelecek mesafeye çek (R/R = 1:1)
            clamp_dist = net_target / size.notional_usdt * price
            stop = price - clamp_dist if direction == "long" else price + clamp_dist
            log.info(f"{symbol} stop, hedefe eşitlendi (R/R 1:1)")
        else:  # "skip"
            log.info(f"{symbol} atlandı: ATR stop hedeften büyük (R/R < 1:1)")
            return False

    stop_check = ctx["risk"].validate_stop(price, stop, direction, net_target,
                                           size.notional_usdt)
    if not stop_check.allowed:
        log.info(f"{symbol} atlandı: {stop_check.reason}")
        return False

    # 5) Giriş emri
    fill = ctx["orders"].open_entry(symbol, direction, size.contracts, price, inst["ct_val"])
    if fill is None:
        log.info(f"{symbol} giriş gerçekleşmedi (slippage/timeout/hata)")
        return False

    entry_price = fill["entry_price"]

    # 6) Borsada asılı reduce-only stop
    algo_id = ctx["orders"].place_stop(symbol, direction, fill["contracts"], stop)

    # 7) Pozisyon kaydı (SQLite) — net hedef kilitli
    liq = liquidation_price(entry_price, direction, CONFIG.leverage)
    pos = {
        "symbol": symbol, "direction": direction, "entry_price": entry_price,
        "contracts": fill["contracts"], "ct_val": inst["ct_val"],
        "entry_maker": fill.get("entry_maker", True),
        "stop_price": stop, "algo_id": algo_id or "", "net_target": net_target,
        "peak_net": 0.0, "trailing_active": False, "stop_moved_to_entry": False,
        "opened_ts": time.time(), "long_score": signal.long_score,
        "short_score": signal.short_score, "liq_price": liq,
    }
    ctx["state"].save_open_position(pos)
    ctx["state"].set_last_entry_time(symbol)

    _print_trade_summary(signal, size, entry_price, stop, net_target, liq)
    ctx["notifier"].send(
        f"🟢 AÇILDI {symbol} {direction.upper()} | skor {signal.score:.0f} | "
        f"giriş {entry_price:.4f} | stop {stop:.4f} | net hedef {net_target:.4f} USDT | "
        f"{'CANLI' if ctx['live'] else 'PAPER'}"
    )
    return True


def _print_trade_summary(signal, size, entry, stop, net_target, liq) -> None:
    """Spec'teki örnek terminal kutusunu basar."""
    d = signal.direction.upper()
    mode = "Live Trade" if is_live_mode() else "Paper Trade"
    print("\n" + "=" * 54)
    print(f"Coin: {signal.symbol}")
    print(f"Direction: {d}")
    print(f"Long Score: {signal.long_score:.0f}")
    print(f"Short Score: {signal.short_score:.0f}")
    print(f"Entry: {entry:.4f}")
    print(f"Net Profit Target: {net_target:.4f} USDT "
          f"({CONFIG.net_profit_target_percent_of_balance}% of balance)")
    print("Trailing: starts at target, then trails")
    print(f"Stop: {stop:.4f} (R/R 1:1)")
    print(f"Liquidation: ~{liq:.4f} ({CONFIG.leverage}x isolated)")
    print(f"Leverage: {CONFIG.leverage}x")
    print(f"Margin: Balance %{CONFIG.risk_per_trade_percent} ({size.margin_usdt:.2f} USDT)")
    print(f"Mode: {CONFIG.margin_mode.capitalize()}")
    print(f"Status: {mode}")
    print("=" * 54 + "\n")


# ======================================================================
# Tek tarama döngüsü
# ======================================================================

def scan_cycle(ctx) -> None:
    log = ctx["log"]
    exchange = ctx["exchange"]
    state: StateStore = ctx["state"]
    paper: PaperTrader = ctx["paper"]
    live = ctx["live"]

    # 1) Bakiye + günlük reset
    balance = get_balance(exchange, paper, live)
    ctx["balance"] = balance
    state.reset_daily_if_new_day(balance)

    # 2) Açık pozisyon varsa yönet, yeni işlem arama
    open_pos = state.get_open_position()
    if open_pos:
        # Adopte edilmiş (borsadan devralınan) pozisyonda ct_val eksik olabilir
        if not open_pos.get("ct_val"):
            inst = ctx["scanner"].get_instrument(open_pos["symbol"])
            if inst:
                open_pos["ct_val"] = inst["ct_val"]
                state.save_open_position(open_pos)
        ctx["position_manager"].manage(open_pos)
        return

    # 3) Risk kapıları
    rt = state.get_runtime_state()
    day_start = rt["day_start_balance"] or balance
    gate = ctx["risk"].can_open_new_trade(balance, day_start)
    if not gate.allowed:
        log.info(f"Yeni işlem yok: {gate.reason}")
        return

    # 4) Coin tara (tek ticker çağrısı → en likit N)
    candidates = ctx["scanner"].scan_candidates()
    if not candidates:
        log.info("Uygun likit coin bulunamadı")
        return

    btc_bias = ctx["fetcher"].get_btc_bias()

    # 5) Her aday için indikatör + skor + sinyal
    signals = []
    for c in candidates:
        symbol = c["symbol"]
        dfs = ctx["fetcher"].get_all_timeframes(symbol)
        if dfs is None:
            continue
        signal, reason = evaluate_symbol(
            symbol, dfs[CONFIG.tf_trend], dfs[CONFIG.tf_entry],
            btc_bias, c["spread_pct"],
        )
        if signal:
            signals.append(signal)

    # 6) En iyi sinyali seç
    best = pick_best_signal(signals)
    if best is None:
        log.info(f"Sinyal yok — {len(candidates)} coin tarandı, hepsi bekleme "
                 f"(BTC bias {btc_bias:+.2f})")
        return

    # 7) İşlemi aç
    try_open_trade(best, ctx)


# ======================================================================
# Giriş noktası
# ======================================================================

def main() -> None:
    logger = setup_logger()
    live = is_live_mode()

    logger.info("=" * 54)
    logger.info("Crypto Futures Bot başlıyor")
    logger.info(f"Mod: {'CANLI (gerçek emir)' if live else 'PAPER (simülasyon)'} | "
                f"paper_trade={CONFIG.paper_trade} live_trading={CONFIG.live_trading}")
    logger.info(f"Borsa: {CONFIG.exchange_name} | demo={SECRETS.okx_demo} | "
                f"kaldıraç {CONFIG.leverage}x {CONFIG.margin_mode}")
    logger.info("=" * 54)

    if live:
        confirm_live_or_exit(logger)

    exchange = build_exchange()
    state = StateStore(CONFIG.db_path)
    paper = PaperTrader()
    trade_logger = TradeLogger()
    notifier = TelegramNotifier(logger)
    scanner = MarketScanner(exchange, logger)
    fetcher = CandleFetcher(exchange, logger)
    risk = RiskManager(state)
    orders = OrderManager(exchange, paper, live, logger)
    position_manager = PositionManager(
        exchange, orders, paper, state, risk, trade_logger, notifier, live, logger
    )

    scanner.load_instruments()
    sync_with_exchange(exchange, state, live, logger)

    ctx = {
        "exchange": exchange, "state": state, "paper": paper, "notifier": notifier,
        "scanner": scanner, "fetcher": fetcher, "risk": risk, "orders": orders,
        "position_manager": position_manager, "live": live, "log": logger,
        "balance": 0.0,
    }

    logger.info(f"Başlangıç bakiyesi: {get_balance(exchange, paper, live):.2f} USDT")
    logger.info("Döngü başladı. Durdurmak için CTRL+C.")

    try:
        while True:
            try:
                scan_cycle(ctx)
            except Exception as exc:  # noqa: BLE001 — döngü asla çökmesin
                logger.error(f"Döngü hatası (devam ediliyor): {exc}", exc_info=True)
                time.sleep(5)
            time.sleep(CONFIG.scan_interval_seconds)
    except KeyboardInterrupt:
        logger.info("CTRL+C — bot durduruluyor.")
    finally:
        stats = state.get_trade_stats()
        logger.info("-" * 54)
        logger.info(f"Özet: {stats['trades']} işlem | win rate {stats['win_rate']:.1f}% | "
                    f"toplam net {stats['total_net']:+.4f} USDT")
        logger.info(f"Ort. kâr {stats['avg_win']:.4f} | ort. zarar {stats['avg_loss']:.4f} | "
                    f"kâr/zarar {stats['profit_factor']:.2f}")
        state.close()


if __name__ == "__main__":
    main()
