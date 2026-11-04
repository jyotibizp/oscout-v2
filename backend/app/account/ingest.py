"""Account data in (#24): Kite trades()/orders() pulled during the day and the Console tradebook CSV.
Fills are insert-only (deduped on exchange + trade_id, so CSV and Kite overlap safely); orders keep the latest state."""
import csv
import io
import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import as_utc, now_utc
from app.db.models import AccountOrder, AccountTrade

log = logging.getLogger(__name__)

DERIV_EXCHANGES = {"NFO", "BFO"}
_SYM = re.compile(r"^([A-Z0-9&\-]+?)(\d{2})([1-9OND]\d{2}|[A-Z]{3})(\d+(?:\.\d+)?)?(CE|PE|FUT)$")

last_sync: dict = {"at": None, "trades_added": 0, "orders": 0, "error": None}


def parse_symbol(ts: str) -> tuple[str, str] | None:
    """NIFTY2511424500CE / NIFTY25NOV24500PE / BANKNIFTY25NOVFUT / SENSEX25N1381000CE -> (underlying, CE|PE|FUT)."""
    m = _SYM.match(ts.strip().upper())
    if not m or (m.group(5) != "FUT" and not m.group(4)):
        return None
    return m.group(1), m.group(5)


def _parse_ts(v) -> datetime:
    if isinstance(v, datetime):
        return as_utc(v)
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return as_utc(datetime.strptime(s, fmt))  # naive = IST
        except ValueError:
            pass
    raise ValueError(f"bad timestamp {v!r}")


def _add_fill(db: Session, seen: set, row: dict, source: str) -> bool:
    ex = str(row["exchange"]).upper()
    key = (ex, str(row["trade_id"]))
    if ex not in DERIV_EXCHANGES or key in seen:
        return False
    p = parse_symbol(row["tradingsymbol"])
    if p is None:
        return False
    seen.add(key)
    db.add(AccountTrade(trade_id=key[1], order_id=str(row.get("order_id") or "") or None, exchange=ex,
                        tradingsymbol=row["tradingsymbol"].strip().upper(), underlying=p[0], instrument=p[1],
                        side=str(row["side"]).upper(), quantity=abs(int(float(row["quantity"]))),
                        price=float(row["price"]), fill_ts=_parse_ts(row["ts"]), source=source))
    return True


def _seen(db: Session) -> set:
    return set(db.execute(select(AccountTrade.exchange, AccountTrade.trade_id)).all())


def import_csv(db: Session, text: str) -> dict:
    """Zerodha Console tradebook CSV (symbol, exchange, trade_type, quantity, price, trade_id, order_id,
    order_execution_time). Equity rows and duplicates are skipped."""
    rd = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    if not rd.fieldnames:
        raise ValueError("empty file")
    norm = {f: f.strip().lower().replace(" ", "_") for f in rd.fieldnames}
    need = {"symbol", "exchange", "trade_type", "quantity", "price", "trade_id"}
    missing = need - set(norm.values()) - ({"symbol"} if "tradingsymbol" in norm.values() else set())
    if missing:
        raise ValueError(f"not a Kite Console tradebook CSV: missing {', '.join(sorted(missing))}")
    seen, added, skipped, errors = _seen(db), 0, 0, []
    for i, raw in enumerate(rd, start=2):
        r = {norm[k]: v for k, v in raw.items() if k in norm}
        try:
            ts = r.get("order_execution_time") or r.get("trade_date")
            ok = _add_fill(db, seen, {"exchange": r["exchange"], "trade_id": r["trade_id"], "order_id": r.get("order_id"),
                                      "tradingsymbol": r.get("symbol") or r.get("tradingsymbol"), "side": r["trade_type"],
                                      "quantity": r["quantity"], "price": r["price"], "ts": ts}, "CSV")
            added += ok
            skipped += not ok
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f"line {i}: {e}")
    db.commit()
    return {"added": added, "skipped": skipped, "errors": errors[:20], "error_count": len(errors)}


def sync(db: Session, provider, final: bool = False) -> dict:
    """Pull today's fills and orders from the broker. `final` (after the close) also counts modifications."""
    if not hasattr(provider, "account_trades"):
        return {"trades_added": 0, "orders": 0, "skipped": "provider has no account data"}
    seen, added = _seen(db), 0
    for t in provider.account_trades() or []:
        added += _add_fill(db, seen, {"exchange": t["exchange"], "trade_id": t["trade_id"], "order_id": t.get("order_id"),
                                      "tradingsymbol": t["tradingsymbol"], "side": t["transaction_type"],
                                      "quantity": t["quantity"], "price": t["average_price"],
                                      "ts": t.get("fill_timestamp") or t.get("exchange_timestamp") or t["order_timestamp"]}, "KITE")
    orders = 0
    for o in provider.account_orders() or []:
        ex = str(o.get("exchange") or "").upper()
        p = parse_symbol(str(o.get("tradingsymbol") or ""))
        if ex not in DERIV_EXCHANGES or p is None or not o.get("order_timestamp"):
            continue
        row = db.scalar(select(AccountOrder).where(AccountOrder.order_id == str(o["order_id"])))
        if row is None:
            row = AccountOrder(order_id=str(o["order_id"]), placed_ts=_parse_ts(o["order_timestamp"]), exchange=ex,
                               tradingsymbol=o["tradingsymbol"], underlying=p[0], side=o["transaction_type"])
            db.add(row)
        row.order_type, row.product = o.get("order_type"), o.get("product")
        row.quantity, row.filled_quantity = int(o.get("quantity") or 0), int(o.get("filled_quantity") or 0)
        row.price, row.average_price = o.get("price"), o.get("average_price")
        row.status, row.status_message = str(o.get("status") or "")[:24], (o.get("status_message") or None)
        if final and row.modifications is None and row.status in ("COMPLETE", "CANCELLED", "REJECTED"):
            try:
                hist = provider.order_history(row.order_id) or []
                row.modifications = sum(1 for h in hist if h.get("status") == "MODIFIED")
            except Exception as e:  # noqa: BLE001 - modifications are best effort
                log.warning("order_history failed", extra={"ctx": {"order_id": row.order_id, "error": str(e)}})
        orders += 1
    db.commit()
    last_sync.update(at=now_utc().isoformat(), trades_added=added, orders=orders, error=None)
    return {"trades_added": added, "orders": orders}
