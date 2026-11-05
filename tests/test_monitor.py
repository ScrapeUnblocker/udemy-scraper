import pytest

from udemy_scraper import PriceQuote, diff, snapshot
from udemy_scraper.monitor import load_state, save_state


def quote(price, list_price, *, course_id=1, country="us", free=False, currency="USD"):
    off = round((1 - price / list_price) * 100) if list_price and price < list_price else None
    return PriceQuote(course_id, country, currency, price, list_price, off, free)


@pytest.mark.parametrize(
    "before, after, kind",
    [
        (quote(19.99, 19.99), quote(9.99, 19.99), "deal_started"),
        (quote(9.99, 19.99), quote(19.99, 19.99), "deal_ended"),
        (quote(12.99, 19.99), quote(9.99, 19.99), "price_drop"),
        (quote(19.99, 19.99), quote(24.99, 24.99), "price_increase"),
        (quote(19.99, 19.99), quote(0.0, 0.0, free=True), "now_free"),
        (quote(0.0, 0.0, free=True), quote(19.99, 19.99), "now_paid"),
        (quote(9.99, 19.99), quote(9.99, 29.99), "list_price_changed"),
        (quote(104.99, 104.99, currency="EUR"), quote(29.99, 199.99), "currency_changed"),
    ],
)
def test_change_kinds(before, after, kind):
    changes = diff(snapshot([before]), snapshot([after]))
    assert [c.kind for c in changes] == [kind]
    assert changes[0].old_price == before.price and changes[0].new_price == after.price


def test_currency_change_keeps_the_old_currency():
    before = snapshot([quote(80.99, 80.99, currency="RON")])
    (change,) = diff(before, snapshot([quote(29.99, 199.99)]))
    assert (change.kind, change.old_currency, change.currency) == ("currency_changed", "RON", "USD")
    assert change.table_row()[3] == "80.99 RON"


def test_no_change_and_new_courses():
    same = snapshot([quote(9.99, 19.99)])
    assert diff(same, same) == []
    changes = diff(same, snapshot([quote(9.99, 19.99), quote(5.0, 5.0, course_id=2)]))
    assert [(c.course_id, c.kind) for c in changes] == [(2, "new")]


def test_countries_are_tracked_separately():
    before = snapshot([quote(9.99, 19.99, country="us"), quote(30.0, 30.0, country="gb")])
    after = snapshot([quote(9.99, 19.99, country="us"), quote(25.0, 30.0, country="gb")])
    assert [(c.country, c.kind) for c in diff(before, after)] == [("gb", "deal_started")]


def test_state_file_round_trip(tmp_path):
    path = str(tmp_path / "state" / "prices.json")
    assert load_state(path) is None
    state = snapshot([quote(9.99, 19.99)])
    save_state(path, state)
    assert load_state(path) == state
