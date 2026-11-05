"""Udemy URLs, course and instructor references, and the search filter vocabulary.

The sort orders and filters are the ones udemy.com puts in its own search URLs
(``/courses/search/?q=python&sort=highest-rated&ratings=4.5&lang=en``), so a URL copied
from the browser and a :class:`SearchQuery` built in code mean the same search.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from .errors import InputError

BASE_URL = "https://www.udemy.com"
API_URL = f"{BASE_URL}/api-2.0"
SEARCH_URL = f"{BASE_URL}/courses/search/"

#: Courses on one search results page.
PAGE_SIZE = 24
#: Courses priced in one pricing request.
PRICING_BATCH = 20
#: Reviews in one request (the most Udemy returns).
REVIEW_PAGE_SIZE = 100
#: An instructor's courses in one request.
INSTRUCTOR_PAGE_SIZE = 50

#: ``--sort`` name -> Udemy's ``sort`` URL value (``None`` = Udemy's default, most relevant).
SORTS: dict[str, str | None] = {
    "relevance": None,
    "reviews": "most-reviewed",
    "rating": "highest-rated",
    "newest": "newest",
}
#: Course level -> ``instructional_level`` value.
LEVELS = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "expert": "expert",
    "all-levels": "all",
}
#: Price filter -> ``price`` value.
PRICES = {"free": "price-free", "paid": "price-paid"}
#: Video length bucket -> ``duration`` value.
DURATIONS = {
    "0-1h": "extraShort",
    "1-3h": "short",
    "3-6h": "medium",
    "6-17h": "long",
    "17h+": "extraLong",
}
#: Course feature -> ``features`` value.
FEATURES = {
    "coding-exercises": "has_coding_exercises",
    "practice-tests": "has_practice_test",
    "quizzes": "has_simple_quiz",
}
#: Minimum ratings Udemy offers as a filter.
RATINGS = (3.0, 3.5, 4.0, 4.5)
#: The ISO currency of each country, to spot prices Udemy gave for another market.
LOCAL_CURRENCIES = {
    "ae": "AED", "ar": "ARS", "at": "EUR", "au": "AUD", "bd": "BDT", "be": "EUR",
    "br": "BRL", "ca": "CAD", "ch": "CHF", "cl": "CLP", "cn": "CNY", "co": "COP",
    "cz": "CZK", "de": "EUR", "dk": "DKK", "ee": "EUR", "eg": "EGP", "es": "EUR",
    "fi": "EUR", "fr": "EUR", "gb": "GBP", "gr": "EUR", "hk": "HKD", "hr": "EUR",
    "hu": "HUF", "id": "IDR", "ie": "EUR", "il": "ILS", "in": "INR", "it": "EUR",
    "jp": "JPY", "ke": "KES", "kr": "KRW", "lt": "EUR", "lu": "EUR", "lv": "EUR",
    "mx": "MXN", "my": "MYR", "ng": "NGN", "nl": "EUR", "no": "NOK", "nz": "NZD",
    "pe": "PEN", "ph": "PHP", "pk": "PKR", "pl": "PLN", "pt": "EUR", "ro": "RON",
    "sa": "SAR", "se": "SEK", "sg": "SGD", "si": "EUR", "sk": "EUR", "th": "THB",
    "tr": "TRY", "tw": "TWD", "ua": "UAH", "us": "USD", "vn": "VND", "za": "ZAR",
}  # fmt: skip

#: Search URL parameters that are not filters (and are not kept from pasted URLs).
_NOT_FILTERS = {"q", "p", "src", "sort", "locale", "persist_locale", "kw", "rs", "ns"}

_LANG = re.compile(r"^[a-z]{2}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$", re.IGNORECASE)
_COURSE_PATH = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?course/([^/?#]+)", re.IGNORECASE)
_USER_PATH = re.compile(r"^/(?:[a-z]{2}(?:-[a-z]{2})?/)?user/([^/?#]+)", re.IGNORECASE)


def _reverse(mapping: dict[str, Any]) -> dict[Any, str]:
    return {v: k for k, v in mapping.items()}


def _choices(name: str, values: Iterable[str], mapping: dict[str, str]) -> tuple[str, ...]:
    out = []
    for value in values:
        key = str(value).strip().lower()
        if key not in mapping:
            raise InputError(f"unknown {name} {value!r}; choose from: {', '.join(mapping)}")
        if key not in out:
            out.append(key)
    return tuple(out)


def _languages(name: str, values: Iterable[str]) -> tuple[str, ...]:
    out = []
    for value in values:
        code = str(value).strip().lower()
        if not _LANG.match(code):
            raise InputError(f"{name} must be two-letter language codes such as en or es")
        if code not in out:
            out.append(code)
    return tuple(out)


@dataclass(frozen=True)
class SearchQuery:
    """A Udemy course search: the query, a sort order and any of Udemy's filters.

    Args:
        query: Search terms, e.g. ``"python"``.
        sort: A key of :data:`SORTS` (default: most relevant).
        languages: Course languages as two-letter codes (``"en"``, ``"es"``, ...).
        levels: Keys of :data:`LEVELS`.
        min_rating: One of :data:`RATINGS`.
        price: ``"free"`` or ``"paid"``.
        durations: Video length buckets, keys of :data:`DURATIONS`.
        features: Keys of :data:`FEATURES`.
        captions: Subtitle languages as two-letter codes.
        extra: Other ``(name, value)`` URL parameters to send as they are.
    """

    query: str
    sort: str | None = None
    languages: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    min_rating: float | None = None
    price: str | None = None
    durations: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    captions: tuple[str, ...] = ()
    extra: tuple[tuple[str, str], ...] = field(default=())

    def __post_init__(self) -> None:
        query = " ".join(str(self.query or "").split())
        if not query:
            raise InputError("give a search query")
        object.__setattr__(self, "query", query)
        if self.sort is not None and self.sort not in SORTS:
            raise InputError(f"unknown sort {self.sort!r}; choose from: {', '.join(SORTS)}")
        if self.sort == "relevance":
            object.__setattr__(self, "sort", None)
        object.__setattr__(self, "languages", _languages("languages", self.languages))
        object.__setattr__(self, "levels", _choices("level", self.levels, LEVELS))
        object.__setattr__(self, "durations", _choices("duration", self.durations, DURATIONS))
        object.__setattr__(self, "features", _choices("feature", self.features, FEATURES))
        object.__setattr__(self, "captions", _languages("captions", self.captions))
        object.__setattr__(self, "extra", tuple((str(k), str(v)) for k, v in self.extra))
        if self.price is not None:
            price = str(self.price).lower()
            if price not in PRICES:
                raise InputError(f"price must be one of: {', '.join(PRICES)}")
            object.__setattr__(self, "price", price)
        if self.min_rating is not None:
            rating = float(self.min_rating)
            if rating not in RATINGS:
                options = ", ".join(str(r) for r in RATINGS)
                raise InputError(f"min_rating must be one of: {options}")
            object.__setattr__(self, "min_rating", rating)

    def filter_params(self) -> list[tuple[str, str]]:
        """The filter parameters of the search URL (no query, page or sort)."""
        params: list[tuple[str, str]] = []
        params += [("lang", code) for code in self.languages]
        params += [("instructional_level", LEVELS[level]) for level in self.levels]
        if self.min_rating is not None:
            params.append(("ratings", f"{self.min_rating:.1f}"))
        if self.price:
            params.append(("price", PRICES[self.price]))
        params += [("duration", DURATIONS[d]) for d in self.durations]
        params += [("features", FEATURES[f]) for f in self.features]
        params += [("closed_captions", code) for code in self.captions]
        params += list(self.extra)
        return params

    @property
    def filter_count(self) -> int:
        """How many different filters the search uses (Udemy counts them as "selections")."""
        return len({name for name, _ in self.filter_params()})

    def url(self, page: int = 1) -> str:
        """The udemy.com search URL for one results page, with English page labels."""
        if page < 1:
            raise InputError("pages start at 1")
        params: list[tuple[str, str]] = [("q", self.query), ("src", "ukw")]
        if page > 1:
            params.append(("p", str(page)))
        sort = SORTS.get(self.sort or "relevance")
        if sort:
            params.append(("sort", sort))
        params += self.filter_params()
        params += [("persist_locale", ""), ("locale", "en_US")]
        return f"{SEARCH_URL}?{urlencode(params)}"


def parse_search_url(url: str) -> SearchQuery:
    """A :class:`SearchQuery` from a udemy.com search URL copied from the browser."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if not host.endswith("udemy.com") or not parts.path.rstrip("/").endswith("/courses/search"):
        raise InputError(f"not a udemy.com course search URL: {url}")
    values: dict[str, list[str]] = {}
    for name, value in parse_qsl(parts.query, keep_blank_values=False):
        values.setdefault(name, []).append(value)
    if not values.get("q"):
        raise InputError("the search URL has no q= query")
    sorts = _reverse(SORTS)
    levels = _reverse(LEVELS)
    durations = _reverse(DURATIONS)
    features = _reverse(FEATURES)
    prices = _reverse(PRICES)
    known = {"lang", "instructional_level", "ratings", "price", "duration", "features"}
    known.add("closed_captions")
    extra = [
        (name, value)
        for name, items in values.items()
        if name not in known and name not in _NOT_FILTERS
        for value in items
    ]
    try:
        rating = float(values["ratings"][0]) if values.get("ratings") else None
    except ValueError:
        raise InputError(f"bad ratings value in {url}") from None
    return SearchQuery(
        query=values["q"][0],
        sort=sorts.get(values["sort"][0]) if values.get("sort") else None,
        languages=tuple(values.get("lang", ())),
        levels=tuple(levels.get(v, v) for v in values.get("instructional_level", ())),
        min_rating=rating,
        price=prices.get(values["price"][0], values["price"][0]) if values.get("price") else None,
        durations=tuple(durations.get(v, v) for v in values.get("duration", ())),
        features=tuple(features.get(v, v) for v in values.get("features", ())),
        captions=tuple(values.get("closed_captions", ())),
        extra=tuple(extra),
    )


def parse_course_ref(ref: Any) -> str:
    """A course id (digits) or slug from an id, a slug or any udemy.com course URL.

    >>> parse_course_ref("https://www.udemy.com/course/complete-python-bootcamp/?couponCode=X")
    'complete-python-bootcamp'
    """
    text = str(ref).strip()
    if text.isdigit():
        return text
    if "/" in text:
        parts = urlsplit(text if "://" in text else f"https://www.udemy.com{text}")
        match = _COURSE_PATH.match(parts.path)
        if not match or not (parts.hostname or "").lower().endswith("udemy.com"):
            raise InputError(f"not a udemy.com course URL: {ref}")
        text = match.group(1)
    if not _SLUG.match(text):
        raise InputError(f"not a Udemy course id, slug or URL: {ref!r}")
    return text


def parse_instructor_ref(ref: Any) -> str:
    """An instructor's profile slug from the slug or a udemy.com/user/... URL."""
    text = str(ref).strip()
    if "/" in text:
        parts = urlsplit(text if "://" in text else f"https://www.udemy.com{text}")
        match = _USER_PATH.match(parts.path)
        if not match or not (parts.hostname or "").lower().endswith("udemy.com"):
            raise InputError(f"not a udemy.com instructor URL: {ref}")
        text = match.group(1)
    if not _SLUG.match(text):
        raise InputError(f"not a Udemy instructor slug or URL: {ref!r}")
    return text


def course_url(slug: str) -> str:
    return f"{BASE_URL}/course/{slug}/"


def instructor_url(slug: str) -> str:
    return f"{BASE_URL}/user/{slug}/"


def absolute(path: str | None) -> str | None:
    if not path:
        return None
    return path if path.startswith("http") else f"{BASE_URL}{path}"


def api_url(path: str, params: dict[str, Any] | None = None) -> str:
    """A Udemy JSON endpoint URL; ``None`` parameters are left out."""
    query = {k: v for k, v in (params or {}).items() if v is not None}
    url = f"{API_URL}/{path.strip('/')}/"
    return f"{url}?{urlencode(query, safe=',@')}" if query else url
