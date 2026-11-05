"""Command-line interface for ``udemy-scraper``.

Commands: ``search``, ``browse``, ``course``, ``curriculum``, ``reviews``, ``prices``,
``watch``, ``instructor``.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .errors import InputError, NotFoundError, UdemyError
from .export import FORMATS, write
from .scraper import UdemyScraper
from .urls import DURATIONS, FEATURES, LEVELS, PRICES, RATINGS, SORTS, SearchQuery, parse_search_url

log = logging.getLogger("udemy_scraper")

_EXTENSIONS = {".csv": "csv", ".jsonl": "jsonl", ".json": "json", ".txt": "table"}


def _split(values: Sequence[str] | None) -> list[str]:
    """Repeatable options that also accept comma-separated values."""
    return [part.strip() for value in values or () for part in value.split(",") if part.strip()]


def _add_common(parser: argparse.ArgumentParser, *, default_format: str = "table") -> None:
    parser.add_argument(
        "-f",
        "--format",
        choices=FORMATS,
        help=f"output format (default: from the --output extension, else {default_format})",
    )
    parser.set_defaults(default_format=default_format)
    parser.add_argument("-o", "--output", help="write to this file instead of stdout")
    parser.add_argument(
        "--retries", type=int, default=3, help="extra attempts per request on transient errors"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log progress to stderr")


def _add_country(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--country",
        default="us",
        help="two-letter country to browse from; sets prices and currency (default: us)",
    )


def _add_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sort", choices=list(SORTS), help="sort order (default: relevance)")
    parser.add_argument(
        "--lang",
        action="append",
        metavar="CODE",
        help="course language, e.g. en or es (repeatable or comma-separated)",
    )
    parser.add_argument(
        "--level", action="append", choices=list(LEVELS), help="course level (repeatable)"
    )
    parser.add_argument(
        "--min-rating", type=float, choices=list(RATINGS), help="only courses rated at least this"
    )
    parser.add_argument("--price", choices=list(PRICES), help="only free or only paid courses")
    parser.add_argument(
        "--duration", action="append", choices=list(DURATIONS), help="video length (repeatable)"
    )
    parser.add_argument(
        "--feature", action="append", choices=list(FEATURES), help="course feature (repeatable)"
    )
    parser.add_argument(
        "--captions", action="append", metavar="CODE", help="subtitle language, e.g. en"
    )


def _add_pages(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pages", type=int, default=1, help="result pages to collect (24 courses each)"
    )
    parser.add_argument(
        "--all", action="store_true", help="every page Udemy offers (one browser request each)"
    )
    parser.add_argument("--limit", type=int, help="stop after this many courses")


def _add_refs(parser: argparse.ArgumentParser, what: str = "courses") -> None:
    parser.add_argument("courses", nargs="*", help=f"{what}: ids, slugs or udemy.com course URLs")
    parser.add_argument("--from-file", help="read course ids, slugs or URLs from a file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udemy-scraper",
        description=(
            "Scrape Udemy course search, course details, curriculum, reviews, prices and "
            "instructors via the ScrapeUnblocker API."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="course search results (several searches are merged)")
    p.add_argument("queries", nargs="+", help="search terms, e.g. 'machine learning'")
    _add_filters(p)
    _add_pages(p)
    _add_country(p)
    _add_common(p)

    p = sub.add_parser("browse", help="results of a udemy.com search URL (its filters are kept)")
    p.add_argument("url", help="e.g. https://www.udemy.com/courses/search/?q=python&ratings=4.5")
    _add_pages(p)
    _add_country(p)
    _add_common(p)

    p = sub.add_parser("course", help="course details: ratings, students, content, deal, ...")
    _add_refs(p)
    p.add_argument(
        "--no-extras", action="store_true", help="skip the content counts (one request less)"
    )
    _add_country(p)
    _add_common(p, default_format="json")

    p = sub.add_parser("curriculum", help="every section and lecture of a course")
    p.add_argument("course", help="course id, slug or URL")
    _add_country(p)
    _add_common(p)

    p = sub.add_parser("reviews", help="course reviews, newest first")
    p.add_argument("course", help="course id, slug or URL")
    p.add_argument("--stars", type=int, choices=(1, 2, 3, 4, 5), help="only this star bucket")
    p.add_argument("--with-text", action="store_true", help="skip rating-only reviews")
    p.add_argument("--pages", type=int, default=1, help="review pages (100 reviews each)")
    p.add_argument("--all", action="store_true", help="every page")
    p.add_argument("--limit", type=int, help="stop after this many reviews")
    _add_country(p)
    _add_common(p)

    p = sub.add_parser("prices", help="current and list prices, for one or many countries")
    _add_refs(p)
    p.add_argument(
        "--countries", action="append", help="countries to compare, e.g. us,gb,de,in (default: us)"
    )
    _add_common(p)

    p = sub.add_parser("watch", help="deals and price changes since the last run")
    _add_refs(p)
    p.add_argument("--state", default="udemy-prices.json", help="file that keeps the prices")
    p.add_argument("--countries", action="append", help="countries to watch (default: us)")
    _add_common(p)

    p = sub.add_parser("instructor", help="instructor profile with stats, bio, links and courses")
    p.add_argument(
        "instructor", help="profile slug or URL, e.g. https://www.udemy.com/user/<slug>/"
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--no-courses", action="store_true", help="profile only (one request)")
    group.add_argument("--courses-only", action="store_true", help="output only the courses")
    p.add_argument("--limit", type=int, help="at most this many courses")
    _add_country(p)
    _add_common(p, default_format="json")
    return parser


def _format(args: argparse.Namespace) -> str:
    if args.format:
        return args.format
    if args.output:
        ext = os.path.splitext(args.output)[1].lower()
        if ext in _EXTENSIONS:
            return _EXTENSIONS[ext]
    return args.default_format


def _refs(args: argparse.Namespace) -> list[str]:
    refs = list(args.courses)
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as handle:
            refs += [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    if not refs:
        raise ValueError("give course ids, slugs or URLs, or --from-file")
    return refs


def _query(args: argparse.Namespace, text: str) -> SearchQuery:
    return SearchQuery(
        text,
        sort=args.sort,
        languages=tuple(_split(args.lang)),
        levels=tuple(args.level or ()),
        min_rating=args.min_rating,
        price=args.price,
        durations=tuple(args.duration or ()),
        features=tuple(args.feature or ()),
        captions=tuple(_split(args.captions)),
    )


def _collect(scraper: UdemyScraper, queries: list[SearchQuery], args: argparse.Namespace) -> Any:
    pages = None if args.all else args.pages
    seen: set[Any] = set()
    found = []
    for query in queries:
        for result in scraper.iter_pages(query, pages=pages):
            if result.page == 1:
                if result.no_results:
                    print(f"no results for {query.query!r}", file=sys.stderr)
                else:
                    print(
                        f"{query.query!r}: {result.total_results or 0:,} results, "
                        f"{result.page_count or 0} pages",
                        file=sys.stderr,
                    )
            for course in result.courses:
                key = course.course_id or course.url
                if key in seen:
                    continue
                seen.add(key)
                found.append(course)
                if args.limit and len(found) >= args.limit:
                    return found
    return found


def _scraper(args: argparse.Namespace, country: str | None = "us") -> UdemyScraper:
    return UdemyScraper(country=country, max_retries=args.retries)


def _run(args: argparse.Namespace) -> int:
    fmt = _format(args)
    cmd = args.command

    if cmd == "search":
        queries = [_query(args, text) for text in args.queries]
        courses = _collect(_scraper(args, args.country), queries, args)
        print(f"{len(courses)} courses", file=sys.stderr)
        write(courses, fmt, args.output)
        return 0

    if cmd == "browse":
        courses = _collect(_scraper(args, args.country), [parse_search_url(args.url)], args)
        print(f"{len(courses)} courses", file=sys.stderr)
        write(courses, fmt, args.output)
        return 0

    if cmd == "course":
        scraper = _scraper(args, args.country)
        details = scraper.courses(_refs(args), extras=not args.no_extras)
        write(details[0] if len(details) == 1 and fmt == "json" else details, fmt, args.output)
        return 0

    if cmd == "curriculum":
        curriculum = _scraper(args, args.country).curriculum(args.course)
        print(
            f"{len(curriculum.sections)} sections, {len(curriculum.items)} items, "
            f"{curriculum.total_duration or '?'} in total",
            file=sys.stderr,
        )
        write(curriculum, fmt, args.output)
        return 0

    if cmd == "reviews":
        pages = None if args.all else args.pages
        reviews = list(
            _scraper(args, args.country).iter_reviews(
                args.course,
                pages=pages,
                limit=args.limit,
                stars=args.stars,
                with_text=args.with_text,
            )
        )
        print(f"{len(reviews)} reviews", file=sys.stderr)
        write(reviews, fmt, args.output)
        return 0

    if cmd == "prices":
        countries = _split(args.countries) or ["us"]
        scraper = _scraper(args, countries[0])
        write(scraper.prices(_refs(args), countries=countries), fmt, args.output)
        return 0

    if cmd == "watch":
        countries = _split(args.countries) or ["us"]
        scraper = _scraper(args, countries[0])
        refs = _refs(args)
        first_run = not os.path.exists(args.state)
        changes = scraper.watch(refs, state_path=args.state, countries=countries)
        if first_run:
            print(f"first run: prices saved to {args.state}", file=sys.stderr)
        else:
            print(f"{len(changes)} changes", file=sys.stderr)
        write(changes, fmt, args.output)
        return 0

    if cmd == "instructor":
        scraper = _scraper(args, args.country)
        profile = scraper.instructor(args.instructor, courses=not args.no_courses, limit=args.limit)
        if args.courses_only:
            write(profile.courses, fmt, args.output)
        else:
            write(profile, fmt, args.output)
        return 0

    raise AssertionError(f"unhandled command {cmd}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        return _run(args)
    except NotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
    except InputError as exc:
        parser.error(str(exc))
    except UdemyError as exc:
        print(f"error: {exc}", file=sys.stderr)
    except ValueError as exc:
        parser.error(str(exc))
    except Exception as exc:  # SDK errors: bad key, no credit, network
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
