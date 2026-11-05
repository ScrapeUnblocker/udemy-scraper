"""Price snapshots and change detection for :meth:`UdemyScraper.watch`."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

from .models import Change, PriceQuote


def _key(quote: PriceQuote) -> str:
    return f"{quote.course_id}:{quote.country or '-'}"


def snapshot(quotes: Iterable[PriceQuote]) -> dict[str, dict[str, Any]]:
    """The state saved between runs: one entry per course and country."""
    return {_key(q): q.to_dict() for q in quotes}


def _change(kind: str, now: dict[str, Any], before: dict[str, Any] | None) -> Change:
    return Change(
        course_id=int(now["course_id"]),
        country=now.get("country"),
        kind=kind,
        currency=now.get("currency"),
        old_price=(before or {}).get("price"),
        new_price=now.get("price"),
        old_currency=(before or {}).get("currency"),
        list_price=now.get("list_price"),
        discount_percent=now.get("discount_percent"),
    )


def _kind(before: dict[str, Any], now: dict[str, Any]) -> str | None:
    """The most telling difference between two snapshots of one course, if any."""
    if bool(now.get("is_free")) != bool(before.get("is_free")):
        return "now_free" if now.get("is_free") else "now_paid"
    if before.get("currency") != now.get("currency"):
        # Prices in two currencies don't compare.
        return "currency_changed"
    on_sale, was_on_sale = bool(now.get("discount_percent")), bool(before.get("discount_percent"))
    if on_sale and not was_on_sale:
        return "deal_started"
    if was_on_sale and not on_sale:
        return "deal_ended"
    old, new = before.get("price"), now.get("price")
    if old is not None and new is not None and old != new:
        return "price_drop" if new < old else "price_increase"
    if before.get("list_price") != now.get("list_price"):
        return "list_price_changed"
    return None


def diff(before: dict[str, dict[str, Any]], now: dict[str, dict[str, Any]]) -> list[Change]:
    """Changes from the ``before`` snapshot to ``now`` (courses new to the watch list too)."""
    changes = []
    for key, current in now.items():
        previous = before.get(key)
        if previous is None:
            changes.append(_change("new", current, None))
            continue
        kind = _kind(previous, current)
        if kind:
            changes.append(_change(kind, current, previous))
    return changes


def load_state(path: str) -> dict[str, dict[str, Any]] | None:
    """The saved snapshot, or ``None`` on the first run."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else None


def save_state(path: str, state: dict[str, dict[str, Any]]) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
