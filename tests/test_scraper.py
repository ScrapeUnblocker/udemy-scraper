import logging

import pytest
from conftest import (
    COURSE,
    CURRICULUM,
    INCENTIVES,
    INSTRUCTOR_HTML,
    NO_RESULTS_HTML,
    BlockedError,
    StepFailedError,
    TargetNotFoundError,
    card,
    dump,
    pricing_answer,
    reviews_answer,
    search_html,
    taught_answer,
)

from udemy_scraper import InputError, NotFoundError, ParseError, SearchQuery
from udemy_scraper.scraper import LOCAL_PRICE_TRIES, SEARCH_STEPS


def two_pages():
    page1 = search_html(card(1, "a", "A"), card(2, "b", "B"), pages=(1, 2), total="3")
    page2 = search_html(card(2, "b", "B"), card(3, "c", "C"), pages=(1, 2), total="3")
    return page1, page2


def test_search_renders_the_page_in_english_from_one_country(make_scraper, search_page):
    scraper, client = make_scraper({"/courses/search/": search_page}, country="DE")
    page = scraper.search("python", sort="newest", languages=["en"], min_rating=4.0)
    assert len(page.courses) == 3
    url, kwargs = client.calls[0]
    assert "q=python" in url and "sort=newest" in url and "lang=en" in url
    assert "ratings=4.0" in url and "locale=en_US" in url
    assert kwargs == {"proxy_country": "de", "steps": SEARCH_STEPS}


def test_search_past_the_last_page_is_empty(make_scraper):
    end = search_html(pages=(1, 2, 3))
    scraper, client = make_scraper({"/courses/search/": StepFailedError("wait_for", html=end)})
    page = scraper.search("python", page=9)
    assert page.courses == [] and not page.has_next
    assert len(client.calls) == 1


def test_search_without_results(make_scraper):
    scraper, _ = make_scraper({"/courses/search/": NO_RESULTS_HTML})
    assert scraper.search("zzqx").no_results


def test_transient_errors_are_retried_with_backoff(make_scraper, search_page):
    waits = []
    scraper, client = make_scraper(
        {"/courses/search/": [BlockedError("blocked"), BlockedError("blocked"), search_page]},
        sleep=waits.append,
        backoff=1.5,
    )
    assert scraper.search("python").courses
    assert waits == [1.5, 3.0]
    assert scraper.requests == 3


def test_retries_give_up(make_scraper):
    scraper, _ = make_scraper({"/courses/search/": BlockedError("blocked")}, max_retries=2)
    with pytest.raises(BlockedError):
        scraper.search("python")


def test_bad_answer_is_fetched_once_more_then_raises(make_scraper):
    scraper, client = make_scraper({"/courses/search/": "<html><body>Oops</body></html>"})
    with pytest.raises(ParseError):
        scraper.search("python")
    assert len(client.calls) == 2


def test_other_errors_are_not_retried(make_scraper):
    scraper, client = make_scraper({"/courses/search/": RuntimeError("invalid API key")})
    with pytest.raises(RuntimeError):
        scraper.search("python")
    assert len(client.calls) == 1


def test_filters_udemy_did_not_apply_are_reported(make_scraper, caplog):
    page = search_html(card(1, "a", "A"), applied=1)
    scraper, _ = make_scraper({"/courses/search/": page})
    with caplog.at_level(logging.WARNING):
        scraper.search(SearchQuery("python", languages=("en",), price="paid"))
    assert "1 applied filters for a search with 2" in caplog.text


def test_pages_stop_at_the_last_page(make_scraper):
    page1, page2 = two_pages()
    scraper, client = make_scraper({"p=2": page2, "/courses/search/": page1})
    pages = list(scraper.iter_pages("python", pages=5))
    assert [p.page for p in pages] == [1, 2]
    assert len(client.calls) == 2


def test_search_courses_dedupes_and_limits(make_scraper):
    page1, page2 = two_pages()
    scraper, _ = make_scraper({"p=2": page2, "/courses/search/": page1})
    courses = scraper.search_courses(["python", "java"], pages=2)
    assert [c.course_id for c in courses] == [1, 2, 3]
    assert len(scraper.search_courses("python", pages=2, limit=2)) == 2


def test_course_by_slug_with_content_counts(make_scraper):
    scraper, client = make_scraper(
        {"course-landing-components/567828": dump(INCENTIVES), "courses/": dump(COURSE)}
    )
    course = scraper.course("https://www.udemy.com/course/complete-python-bootcamp/")
    assert course.course_id == 567828 and course.coding_exercises == 19 and course.country == "us"
    assert "courses/complete-python-bootcamp/" in client.calls[0][0]
    assert client.calls[0][1] == {"proxy_country": "us"}
    # The slug is now known: the curriculum needs no extra lookup.
    client.routes["course-landing-components/567828"] = [dump(CURRICULUM)]
    assert len(scraper.curriculum("complete-python-bootcamp").items) == 4
    assert len(client.calls) == 3


def test_course_content_counts_are_optional(make_scraper, caplog):
    scraper, client = make_scraper(
        {"course-landing-components/": dump({"detail": "x"}), "courses/": dump(COURSE)}
    )
    with caplog.at_level(logging.WARNING):
        course = scraper.course(567828)
    assert course.articles is None and "no content counts" in caplog.text
    assert len(scraper.course(567828, extras=False).title) > 0


def test_unknown_course(make_scraper):
    scraper, _ = make_scraper({"courses/": TargetNotFoundError("404")})
    with pytest.raises(NotFoundError):
        scraper.course("no-such-course")


def test_slug_is_resolved_once(make_scraper):
    scraper, client = make_scraper(
        {"reviews": dump(reviews_answer([1])), "courses/": dump({"_class": "course", "id": 42})}
    )
    scraper.reviews("some-course")
    scraper.reviews("some-course", page=2)
    assert len(client.urls("fields%5Bcourse%5D=title")) == 1
    assert all("courses/42/reviews" in u for u in client.urls("reviews"))


def test_reviews_filters_and_paging(make_scraper):
    scraper, client = make_scraper(
        {
            "page=2": dump(reviews_answer([3, 4])),
            "reviews": dump(reviews_answer([1, 2], has_next=True)),
        }
    )
    reviews = list(scraper.iter_reviews(567828, pages=None, stars=1, with_text=True))
    assert [r.review_id for r in reviews] == [1, 3]
    assert all("rating=1" in u and "page_size=100" in u for u in client.urls("reviews"))
    assert len(list(scraper.iter_reviews(567828, pages=None, limit=1))) == 1
    with pytest.raises(InputError):
        scraper.reviews(567828, stars=6)


def test_prices_for_several_countries_in_batches(make_scraper):
    ids = list(range(1, 26))

    def answer(url, kwargs):
        batch = ids[20:24] if "course_ids=21" in url else ids[:20]  # course 25 has no price
        currency = "INR" if kwargs["proxy_country"] == "in" else "USD"
        return dump(pricing_answer({i: (9.99, 19.99) for i in batch}, currency=currency))

    scraper, client = make_scraper({"pricing": answer})
    quotes = scraper.prices(ids, countries=["us", "IN"])
    assert len(client.calls) == 4
    assert [kw["proxy_country"] for _, kw in client.calls] == ["us", "us", "in", "in"]
    assert [q.course_id for q in quotes[:24]] == ids[:24]
    assert {(q.country, q.currency) for q in quotes} == {("us", "USD"), ("in", "INR")}
    with pytest.raises(InputError):
        scraper.prices(ids, countries=["usa"])


def test_country_priced_as_a_us_visitor_is_asked_again(make_scraper):
    usd = dump(pricing_answer({1: (29.99, 199.99)}))
    eur = dump(pricing_answer({1: (104.99, 104.99)}, currency="EUR"))
    scraper, client = make_scraper({"pricing": [usd, eur]})
    (quote,) = scraper.prices([1], countries=["de"])
    assert (quote.currency, quote.price, len(client.calls)) == ("EUR", 104.99, 2)


def test_prices_for_another_market_are_asked_again(make_scraper, caplog):
    ron = dump(pricing_answer({1: (80.99, 80.99)}, currency="RON"))
    usd = dump(pricing_answer({1: (29.99, 199.99)}))
    scraper, client = make_scraper({"pricing": [ron, usd]})
    assert scraper.prices([1])[0].currency == "USD" and len(client.calls) == 2
    scraper, client = make_scraper({"pricing": ron})
    with caplog.at_level(logging.WARNING):
        assert scraper.prices([1], countries=["br"])[0].currency == "RON"
    assert len(client.calls) == LOCAL_PRICE_TRIES
    assert "br prices kept coming back in RON" in caplog.text


def test_course_price_is_checked_for_the_market(make_scraper):
    eur = dict(COURSE, discount=None, price_detail={"amount": 104.99, "currency": "EUR"})
    scraper, client = make_scraper({"courses/": [dump(COURSE), dump(eur)]}, country="de")
    course = scraper.course(567828, extras=False)
    assert (course.currency, course.price, len(client.calls)) == ("EUR", 104.99, 2)


def test_usd_answers_are_kept_when_they_persist(make_scraper):
    scraper, client = make_scraper({"pricing": dump(pricing_answer({1: (9.99, 9.99)}))})
    assert scraper.prices([1], countries=["ar"])[0].currency == "USD"
    assert len(client.calls) == LOCAL_PRICE_TRIES
    scraper.prices([1], countries=["us"])
    assert len(client.calls) == LOCAL_PRICE_TRIES + 1


def test_watch_reports_changes_after_the_first_run(make_scraper, tmp_path):
    state = str(tmp_path / "prices.json")
    scraper, client = make_scraper({"pricing": dump(pricing_answer({1: (19.99, 19.99)}))})
    assert scraper.watch([1], state_path=state) == []
    client.routes["pricing"] = [dump(pricing_answer({1: (9.99, 19.99), 2: (5.0, 5.0)}))]
    changes = scraper.watch([1, 2], state_path=state)
    assert [(c.course_id, c.kind) for c in changes] == [(1, "deal_started"), (2, "new")]
    assert changes[0].old_price == 19.99 and changes[0].new_price == 9.99


def test_instructor_with_courses(make_scraper):
    scraper, client = make_scraper(
        {
            "page=2": dump(taught_answer([3])),
            "taught-profile-courses": dump(taught_answer([1, 2], has_next=True)),
            "/user/joseportilla/": INSTRUCTOR_HTML,
        }
    )
    profile = scraper.instructor("https://www.udemy.com/user/joseportilla/")
    assert profile.name == "Jose Portilla"
    assert [c.course_id for c in profile.courses] == [1, 2, 3]
    assert "users/9685726/taught-profile-courses" in client.calls[1][0]
    limited = scraper.instructor("joseportilla", limit=1)
    assert len(limited.courses) == 1
    assert scraper.instructor("joseportilla", courses=False).courses == []


def test_bad_country_is_refused(make_scraper):
    with pytest.raises(InputError):
        make_scraper({}, country="United States")
