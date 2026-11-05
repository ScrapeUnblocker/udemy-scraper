"""Scrape Udemy through the ScrapeUnblocker ``getPageSource`` API.

:class:`UdemyScraper` uses the official ``scrapeunblocker`` SDK for every request:

* **Search** loads udemy.com's own search page in a real browser (``getPageSource`` with
  browser steps: wait until the course prices render) and reads the course cards.
* **Courses, curriculum, reviews, prices and instructor courses** come from the JSON
  endpoints udemy.com calls from the browser, fetched with plain ``getPageSource``.
* **Instructor profiles** come from the JSON embedded in the profile page.

Requests are routed through one country (``us`` by default), so prices and currencies are
the ones a visitor from that country sees. Throttled, blocked and timed-out requests are
retried with doubling backoff; an answer without the expected data is fetched once more,
then raises :class:`ParseError`; an unknown course or instructor raises
:class:`NotFoundError`.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterable, Iterator
from typing import Any, Callable

from .errors import InputError, NotFoundError, ParseError
from .models import (
    Change,
    CourseCard,
    CourseDetails,
    Curriculum,
    Instructor,
    InstructorCourse,
    PriceQuote,
    Review,
    ReviewPage,
    SearchPage,
)
from .monitor import diff, load_state, save_state, snapshot
from .parsing import (
    COURSE_FIELDS,
    INSTRUCTOR_COURSE_FIELDS,
    PRICING_FIELDS,
    apply_incentives,
    load_json,
    parse_course,
    parse_curriculum,
    parse_instructor,
    parse_instructor_courses,
    parse_pricing,
    parse_reviews,
    parse_search,
)
from .urls import (
    INSTRUCTOR_PAGE_SIZE,
    LOCAL_CURRENCIES,
    PRICING_BATCH,
    REVIEW_PAGE_SIZE,
    SearchQuery,
    api_url,
    instructor_url,
    parse_course_ref,
    parse_instructor_ref,
)

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "TransportError",
    "ConnectionError",
)
_NOT_FOUND_NAMES = ("TargetNotFoundError",)
_SAME = object()

#: Browser steps for a search page: wait until the course prices (or Udemy's
#: "Sorry, we couldn't find any results" message) render, then a moment longer
#: so the prices of every card are in.
SEARCH_STEPS = [
    {
        "action": "wait_for",
        "selector": (
            "[data-purpose='course-price-text'], "
            "[data-purpose='safely-set-inner-html:search:no-results-for-query']"
        ),
        "timeout_ms": 30000,
    },
    {"action": "wait", "value": 2000},
]
#: Review fields asked for (the default ones plus the instructor's response).
REVIEW_FIELDS = "@default,response,created,modified,rating,content,user"
#: Requests for one answer when the prices come back for another market (see ``prices``).
LOCAL_PRICE_TRIES = 3

_COUNTRY = re.compile(r"^[a-z]{2}$")

log = logging.getLogger(__name__)


def _is_named(error: BaseException, *names: str) -> bool:
    return any(cls.__name__ in names for cls in type(error).__mro__)


def _country(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    code = str(value).strip().lower()
    if not _COUNTRY.match(code):
        raise InputError(f"countries are two-letter codes such as us, gb or de, not {value!r}")
    return code


def _market_mismatch(currencies: set[str], country: str | None) -> str | None:
    """The currency that shows prices were given for another market than ``country``.

    ``None`` when the prices are in the country's own currency (or the country is
    not in :data:`LOCAL_CURRENCIES`). Answers in USD count as a mismatch for other
    countries, as Udemy falls back to US prices for visitors it cannot place.
    """
    local = LOCAL_CURRENCIES.get(country or "")
    if not local or not currencies:
        return None
    other = currencies - {local, "USD"}
    if other:
        return ", ".join(sorted(other))
    if local != "USD" and currencies == {"USD"}:
        return "USD"
    return None


def _quote_currencies(quotes: list[PriceQuote]) -> set[str]:
    return {q.currency for q in quotes if q.currency and not q.is_free}


def _course_id(data: Any) -> int:
    if not isinstance(data, dict) or data.get("_class") != "course" or "id" not in data:
        raise ValueError("not a Udemy course answer")
    return int(data["id"])


class _BadAnswer(Exception):
    """An answer without the expected data (fetched once more)."""


class UdemyScraper:
    """Udemy course search, course details, curriculum, reviews, prices and instructors.

    Args:
        api_key: Your ScrapeUnblocker API key. Defaults to the
            ``SCRAPEUNBLOCKER_KEY`` environment variable (read by the SDK).
        client: A ready ``scrapeunblocker.Client`` (or anything with a compatible
            ``get_page_source``); handy for tests.
        country: Country to route requests through (two-letter code). Udemy prices
            courses per country, so this sets the prices and currency you get.
            ``None`` lets ScrapeUnblocker choose.
        max_retries: Extra attempts for a request that fails transiently.
        backoff: Seconds before the first retry; doubles on each retry.
        timeout: Seconds to wait for one API response.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any = None,
        country: str | None = "us",
        max_retries: int = 3,
        backoff: float = 2.0,
        timeout: float = 180.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if client is None:
            from scrapeunblocker import Client

            client = Client(api_key=api_key, timeout=timeout)
        self.client = client
        self.country = _country(country)
        self.max_retries = max_retries
        self.backoff = backoff
        self.sleep = sleep
        self._ids: dict[str, int] = {}
        #: Number of API requests made so far.
        self.requests = 0

    # -- fetching ----------------------------------------------------------------------

    def _get(self, url: str, *, steps: list[dict[str, Any]] | None, country: str | None) -> str:
        kwargs: dict[str, Any] = {}
        if country:
            kwargs["proxy_country"] = country
        if steps:
            kwargs["steps"] = steps
        self.requests += 1
        try:
            body = self.client.get_page_source(url, **kwargs)
        except Exception as exc:
            if _is_named(exc, *_NOT_FOUND_NAMES):
                raise NotFoundError(f"Udemy answered 404 for {url}") from exc
            html = getattr(exc, "html", None)
            if steps and _is_named(exc, "StepFailedError") and html:
                # The wait gave up (no course cards, e.g. past the last page): the page
                # as it was then still says which case it is.
                return str(html)
            raise
        return body if isinstance(body, str) else str(body)

    def fetch(
        self,
        url: str,
        parse: Callable[[str], Any],
        *,
        steps: list[dict[str, Any]] | None = None,
        country: Any = _SAME,
    ) -> Any:
        """Fetch ``url`` and return ``parse(body)``.

        Transient SDK errors are retried with doubling backoff. If ``parse`` raises
        ``ValueError`` the URL is fetched once more, then :class:`ParseError` is raised.
        A 404 from Udemy raises :class:`NotFoundError`.
        """
        route = self.country if country is _SAME else _country(country)
        attempt = 0
        bad_answers = 0
        while True:
            try:
                body = self._get(url, steps=steps, country=route)
                try:
                    return parse(body)
                except ValueError as exc:
                    bad_answers += 1
                    if bad_answers > 1:
                        raise ParseError(f"{exc} ({url})") from None
                    raise _BadAnswer(str(exc)) from None
            except (NotFoundError, ParseError):
                raise
            except Exception as exc:
                retryable = isinstance(exc, _BadAnswer) or _is_named(exc, *_TRANSIENT_NAMES)
                if not retryable or attempt >= self.max_retries:
                    if isinstance(exc, _BadAnswer):
                        raise ParseError(f"{exc} ({url})") from None
                    raise
                reason = str(exc) if isinstance(exc, _BadAnswer) else type(exc).__name__
                log.info("retrying after %s", reason)
                self.sleep(self.backoff * (2**attempt))
                attempt += 1

    def _json(self, url: str, parse: Callable[[Any], Any], *, country: Any = _SAME) -> Any:
        return self.fetch(url, lambda body: parse(load_json(body)), country=country)

    def _local(
        self,
        fetch: Callable[[], Any],
        currencies: Callable[[Any], set[str]],
        country: str | None,
        what: str,
    ) -> Any:
        """``fetch()`` again while its prices are for another market than ``country``."""
        for attempt in range(1, LOCAL_PRICE_TRIES + 1):
            answer = fetch()
            currency = _market_mismatch(currencies(answer), country)
            if not currency:
                return answer
            if attempt == LOCAL_PRICE_TRIES:
                if currency != "USD":  # Udemy prices some countries in USD
                    log.warning("%s: %s prices kept coming back in %s", what, country, currency)
                return answer
            log.info("%s: %s prices came back in %s; asking again", what, country, currency)
        raise AssertionError("unreachable")

    # -- search ------------------------------------------------------------------------

    def search(
        self,
        query: str | SearchQuery,
        *,
        page: int = 1,
        sort: str | None = None,
        languages: Iterable[str] = (),
        levels: Iterable[str] = (),
        min_rating: float | None = None,
        price: str | None = None,
        durations: Iterable[str] = (),
        features: Iterable[str] = (),
        captions: Iterable[str] = (),
    ) -> SearchPage:
        """One page of course search results (24 courses), as udemy.com shows them.

        ``query`` is the search terms or a ready :class:`SearchQuery` (then the other
        filter arguments are ignored). See :class:`SearchQuery` for the filters.
        """
        if isinstance(query, SearchQuery):
            search = query
        else:
            search = SearchQuery(
                query,
                sort=sort,
                languages=tuple(languages),
                levels=tuple(levels),
                min_rating=min_rating,
                price=price,
                durations=tuple(durations),
                features=tuple(features),
                captions=tuple(captions),
            )
        url = search.url(page)

        def parse(html: str) -> SearchPage:
            return parse_search(html, query=search.query, page=page, url=url)

        result = self.fetch(url, parse, steps=SEARCH_STEPS)
        wanted = search.filter_count
        if wanted and result.courses and (result.filters_applied or 0) < wanted:
            log.warning(
                "Udemy reports %d applied filters for a search with %d; check the filter values",
                result.filters_applied or 0,
                wanted,
            )
        return result

    def iter_pages(
        self, query: str | SearchQuery, *, pages: int | None = 1, start: int = 1
    ) -> Iterator[SearchPage]:
        """Successive result pages from ``start`` until ``pages`` pages or the last page."""
        page = start
        while pages is None or page < start + pages:
            result = self.search(query, page=page)
            yield result
            if not result.has_next:
                return
            page += 1

    def search_courses(
        self,
        queries: str | SearchQuery | Iterable[str | SearchQuery],
        *,
        pages: int | None = 1,
        limit: int | None = None,
    ) -> list[CourseCard]:
        """Courses from several pages (and several searches), without duplicates."""
        if isinstance(queries, (str, SearchQuery)):
            queries = [queries]
        seen: set[Any] = set()
        found: list[CourseCard] = []
        for query in queries:
            for result in self.iter_pages(query, pages=pages):
                for course in result.courses:
                    key = course.course_id or course.url
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append(course)
                    if limit and len(found) >= limit:
                        return found
        return found

    # -- courses -----------------------------------------------------------------------

    def course_id(self, ref: Any) -> int:
        """The numeric id of a course id, slug or URL (a slug costs one request, once)."""
        key = parse_course_ref(ref)
        if key.isdigit():
            return int(key)
        if key not in self._ids:
            url = api_url(f"courses/{key}", {"fields[course]": "title"})
            self._ids[key] = self._json(url, _course_id)
        return self._ids[key]

    def course(self, ref: Any, *, extras: bool = True) -> CourseDetails:
        """Course details by id, slug or URL.

        ``extras`` adds the "This course includes" counts (articles, coding exercises,
        downloadable resources, lifetime access) with one more request. The price is
        checked for the right market like in :meth:`prices`.
        """
        key = parse_course_ref(ref)
        url = api_url(f"courses/{key}", {"fields[course]": COURSE_FIELDS})
        details: CourseDetails = self._local(
            lambda: self._json(url, lambda d: parse_course(d, country=self.country)),
            lambda d: {d.currency} if d.currency and d.is_paid else set(),
            self.country,
            f"course {key}",
        )
        if details.slug:
            self._ids[details.slug] = details.course_id
        if extras:
            url = api_url(
                f"course-landing-components/{details.course_id}/me", {"components": "incentives"}
            )
            try:
                self._json(url, lambda d: apply_incentives(details, d))
            except ParseError as exc:
                log.warning("course %s: no content counts (%s)", details.course_id, exc)
        return details

    def courses(self, refs: Iterable[Any], *, extras: bool = True) -> list[CourseDetails]:
        return [self.course(ref, extras=extras) for ref in refs]

    def curriculum(self, ref: Any) -> Curriculum:
        """Every section and item (video, article, quiz, exercise) of a course."""
        course_id = self.course_id(ref)
        url = api_url(
            f"course-landing-components/{course_id}/me", {"components": "curriculum_context"}
        )
        return self._json(url, lambda d: parse_curriculum(d, course_id))

    # -- reviews -----------------------------------------------------------------------

    def reviews(
        self,
        ref: Any,
        *,
        page: int = 1,
        stars: int | None = None,
        page_size: int = REVIEW_PAGE_SIZE,
    ) -> ReviewPage:
        """One page of a course's reviews, newest first.

        ``stars`` keeps one star bucket (1-5); Udemy files half stars under the lower
        bucket, so ``stars=1`` also returns 1.5-star reviews.
        """
        if stars is not None and stars not in (1, 2, 3, 4, 5):
            raise InputError("stars must be 1, 2, 3, 4 or 5")
        if page < 1:
            raise InputError("pages start at 1")
        if not 1 <= page_size <= REVIEW_PAGE_SIZE:
            raise InputError(f"page_size must be 1-{REVIEW_PAGE_SIZE}")
        course_id = self.course_id(ref)
        params = {
            "page": page,
            "page_size": page_size,
            "rating": stars,
            "fields[course_review]": REVIEW_FIELDS,
        }
        url = api_url(f"courses/{course_id}/reviews", params)
        return self._json(url, lambda d: parse_reviews(d, course_id, page))

    def iter_reviews(
        self,
        ref: Any,
        *,
        pages: int | None = 1,
        limit: int | None = None,
        stars: int | None = None,
        with_text: bool = False,
    ) -> Iterator[Review]:
        """Reviews across pages (100 per page). ``with_text`` skips rating-only reviews."""
        page = 1
        count = 0
        while pages is None or page <= pages:
            result = self.reviews(ref, page=page, stars=stars)
            for review in result.reviews:
                if with_text and not review.content:
                    continue
                yield review
                count += 1
                if limit and count >= limit:
                    return
            if not result.has_next or not result.reviews:
                return
            page += 1

    # -- prices ------------------------------------------------------------------------

    def prices(
        self, refs: Iterable[Any], *, countries: Iterable[str | None] | None = None
    ) -> list[PriceQuote]:
        """Current and list price of many courses, for one or several countries.

        One request prices up to 20 courses for one country; ``countries`` defaults to
        the scraper's country. Prices are in the currency Udemy shows that country.

        Udemy places each visitor with its own IP lookup, and now and then prices a
        request routed through one country as a visitor from another (in USD, or in
        another country's currency). An answer that is not in the country's own
        currency (:data:`LOCAL_CURRENCIES`) is asked for again, up to
        :data:`LOCAL_PRICE_TRIES` times in all. An answer that stays in USD is kept, as
        Udemy prices some countries in USD; one that stays in a third currency is kept
        with a warning.
        """
        ids = list(dict.fromkeys(self.course_id(ref) for ref in refs))
        if not ids:
            raise InputError("give at least one course")
        routes = [_country(c) for c in countries] if countries else [self.country]
        quotes: list[PriceQuote] = []
        for country in dict.fromkeys(routes):
            for start in range(0, len(ids), PRICING_BATCH):
                batch = ids[start : start + PRICING_BATCH]
                params = {
                    "course_ids": ",".join(str(i) for i in batch),
                    "fields[pricing_result]": PRICING_FIELDS,
                }

                def parse(data: Any, country: str | None = country) -> list[PriceQuote]:
                    return parse_pricing(data, country)

                url = api_url("pricing", params)
                answer = self._local(
                    lambda url=url, parse=parse, country=country: self._json(
                        url, parse, country=country
                    ),
                    _quote_currencies,
                    country,
                    "prices",
                )
                found = {q.course_id: q for q in answer}
                missing = [i for i in batch if i not in found]
                if missing:
                    log.warning("no price for course(s) %s", ", ".join(map(str, missing)))
                quotes.extend(found[i] for i in batch if i in found)
        return quotes

    def watch(
        self,
        refs: Iterable[Any],
        *,
        state_path: str,
        countries: Iterable[str | None] | None = None,
    ) -> list[Change]:
        """Price changes since the last run (the first run only saves the prices).

        Reports deals that started or ended, price drops and increases, list price
        changes, and courses that became free or paid. The state is a JSON file.
        """
        quotes = self.prices(refs, countries=countries)
        before = load_state(state_path)
        now = snapshot(quotes)
        changes = diff(before, now) if before is not None else []
        save_state(state_path, {**(before or {}), **now})
        return changes

    # -- instructors -------------------------------------------------------------------

    def instructor(self, ref: Any, *, courses: bool = True, limit: int | None = None) -> Instructor:
        """An instructor profile (slug or URL) with learners, reviews, bio and links.

        ``courses`` also lists the instructor's courses (50 per request), up to ``limit``.
        """
        slug = parse_instructor_ref(ref)
        profile: Instructor = self.fetch(
            instructor_url(slug), lambda html: parse_instructor(html, slug)
        )
        if courses and profile.instructor_id:
            profile.courses = self.instructor_courses(profile.instructor_id, limit=limit)
        return profile

    def instructor_courses(
        self, instructor_id: int, *, limit: int | None = None
    ) -> list[InstructorCourse]:
        """Every public course of an instructor (by numeric id)."""
        found: list[InstructorCourse] = []
        page = 1
        while True:
            params = {
                "page": page,
                "page_size": INSTRUCTOR_PAGE_SIZE,
                "fields[course]": INSTRUCTOR_COURSE_FIELDS,
            }
            url = api_url(f"users/{int(instructor_id)}/taught-profile-courses", params)
            _, has_next, batch = self._json(url, parse_instructor_courses)
            for course in batch:
                found.append(course)
                if limit and len(found) >= limit:
                    return found
            if not has_next or not batch:
                return found
            page += 1
