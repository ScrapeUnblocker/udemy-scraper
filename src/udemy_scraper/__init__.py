"""Scrape Udemy courses, curriculum, reviews, prices and instructors via the ScrapeUnblocker API.

>>> from udemy_scraper import UdemyScraper
>>> udemy = UdemyScraper()  # reads SCRAPEUNBLOCKER_KEY; prices as seen from the US
>>> page = udemy.search("python", sort="rating", min_rating=4.5, languages=["en"])
>>> [(c.course_id, c.title, c.price, c.rating, c.num_ratings) for c in page.courses[:5]]
>>> course = udemy.course("https://www.udemy.com/course/complete-python-bootcamp/")
>>> course.students, course.rating_distribution, course.price, course.deal_ends_at
>>> lectures = udemy.curriculum(course.course_id).items
>>> one_star = list(udemy.iter_reviews(course.course_id, stars=1, with_text=True))
>>> quotes = udemy.prices([course.course_id], countries=["us", "gb", "de", "in"])
>>> changes = udemy.watch([course.course_id], state_path="udemy-prices.json")
>>> teacher = udemy.instructor("https://www.udemy.com/user/joseportilla/")

See https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos
"""

from __future__ import annotations

__version__ = "0.1.0"

from .errors import InputError, NotFoundError, ParseError, UdemyError
from .export import render, to_csv_file, write
from .models import (
    Change,
    CourseCard,
    CourseDetails,
    Curriculum,
    Instructor,
    InstructorCourse,
    Lecture,
    PriceQuote,
    Review,
    ReviewPage,
    SearchPage,
    Section,
)
from .monitor import diff, snapshot
from .parsing import (
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
from .scraper import UdemyScraper
from .urls import (
    DURATIONS,
    FEATURES,
    LEVELS,
    PRICES,
    RATINGS,
    SORTS,
    SearchQuery,
    parse_course_ref,
    parse_instructor_ref,
    parse_search_url,
)

__all__ = [
    "DURATIONS",
    "FEATURES",
    "LEVELS",
    "PRICES",
    "RATINGS",
    "SORTS",
    "Change",
    "CourseCard",
    "CourseDetails",
    "Curriculum",
    "InputError",
    "Instructor",
    "InstructorCourse",
    "Lecture",
    "NotFoundError",
    "ParseError",
    "PriceQuote",
    "Review",
    "ReviewPage",
    "SearchPage",
    "SearchQuery",
    "Section",
    "UdemyError",
    "UdemyScraper",
    "__version__",
    "apply_incentives",
    "diff",
    "load_json",
    "parse_course",
    "parse_course_ref",
    "parse_curriculum",
    "parse_instructor",
    "parse_instructor_courses",
    "parse_instructor_ref",
    "parse_pricing",
    "parse_reviews",
    "parse_search",
    "parse_search_url",
    "render",
    "snapshot",
    "to_csv_file",
    "write",
]
