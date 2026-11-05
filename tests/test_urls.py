from urllib.parse import parse_qsl, urlsplit

import pytest

from udemy_scraper import (
    InputError,
    SearchQuery,
    parse_course_ref,
    parse_instructor_ref,
    parse_search_url,
)
from udemy_scraper.urls import api_url


def params(url: str) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def test_search_url_has_udemy_parameters():
    query = SearchQuery(
        "  machine   learning ",
        sort="rating",
        languages=("EN", "es"),
        levels=("beginner", "all-levels"),
        min_rating=4.5,
        price="paid",
        durations=("1-3h", "17h+"),
        features=("coding-exercises",),
        captions=("en",),
    )
    got = params(query.url(page=3))
    assert ("q", "machine learning") in got
    assert ("p", "3") in got
    assert ("sort", "highest-rated") in got
    assert [v for k, v in got if k == "lang"] == ["en", "es"]
    assert [v for k, v in got if k == "instructional_level"] == ["beginner", "all"]
    assert ("ratings", "4.5") in got
    assert ("price", "price-paid") in got
    assert [v for k, v in got if k == "duration"] == ["short", "extraLong"]
    assert ("features", "has_coding_exercises") in got
    assert ("closed_captions", "en") in got
    # English page labels, whatever country the request comes from.
    assert ("locale", "en_US") in got
    assert query.filter_count == 7


def test_first_page_and_default_sort_are_left_out():
    got = dict(params(SearchQuery("python", sort="relevance").url()))
    assert "p" not in got and "sort" not in got
    assert got["q"] == "python" and got["src"] == "ukw"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sort": "cheapest"},
        {"levels": ("pro",)},
        {"min_rating": 4.2},
        {"price": "discounted"},
        {"languages": ("english",)},
        {"durations": ("2h",)},
        {"features": ("labs",)},
    ],
)
def test_bad_filters_are_refused(kwargs):
    with pytest.raises(InputError):
        SearchQuery("python", **kwargs)


def test_empty_query_and_page_zero_are_refused():
    with pytest.raises(InputError):
        SearchQuery("   ")
    with pytest.raises(InputError):
        SearchQuery("python").url(page=0)


def test_parse_search_url_round_trip():
    url = (
        "https://www.udemy.com/courses/search/?q=python&src=ukw&p=2&sort=highest-rated"
        "&ratings=4.5&lang=en&lang=es&instructional_level=beginner&duration=extraLong"
        "&features=has_coding_exercises&price=price-free&subs_filter_type=subs_only"
    )
    query = parse_search_url(url)
    assert query.query == "python"
    assert query.sort == "rating"
    assert query.min_rating == 4.5
    assert query.languages == ("en", "es")
    assert query.levels == ("beginner",)
    assert query.durations == ("17h+",)
    assert query.features == ("coding-exercises",)
    assert query.price == "free"
    assert query.extra == (("subs_filter_type", "subs_only"),)
    assert ("subs_filter_type", "subs_only") in params(query.url())


@pytest.mark.parametrize(
    "url",
    ["https://www.example.com/courses/search/?q=x", "https://www.udemy.com/courses/search/?p=2"],
)
def test_parse_search_url_refuses_other_urls(url):
    with pytest.raises(InputError):
        parse_search_url(url)


@pytest.mark.parametrize(
    "ref, expected",
    [
        ("567828", "567828"),
        (567828, "567828"),
        ("complete-python-bootcamp", "complete-python-bootcamp"),
        (
            "https://www.udemy.com/course/complete-python-bootcamp/?couponCode=X",
            "complete-python-bootcamp",
        ),
        ("https://www.udemy.com/course/100-days-of-code/learn/lecture/1", "100-days-of-code"),
        ("/course/the-web-developer-bootcamp/", "the-web-developer-bootcamp"),
    ],
)
def test_parse_course_ref(ref, expected):
    assert parse_course_ref(ref) == expected


@pytest.mark.parametrize(
    "ref", ["https://www.udemy.com/user/joseportilla/", "https://example.com/course/x/", "a b"]
)
def test_parse_course_ref_refuses_other_input(ref):
    with pytest.raises(InputError):
        parse_course_ref(ref)


def test_parse_instructor_ref():
    assert parse_instructor_ref("https://www.udemy.com/user/joseportilla/") == "joseportilla"
    assert parse_instructor_ref("joseportilla") == "joseportilla"
    with pytest.raises(InputError):
        parse_instructor_ref("https://www.udemy.com/course/x/")


def test_api_url_keeps_field_lists_readable():
    url = api_url("courses/567828", {"fields[course]": "title,url", "page": None})
    assert url == "https://www.udemy.com/api-2.0/courses/567828/?fields%5Bcourse%5D=title,url"
