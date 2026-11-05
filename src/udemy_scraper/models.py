"""Records returned by the scraper: dataclasses with ``to_dict``, ``to_row`` and table layouts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _num(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _id(value: Any) -> str:
    return "-" if value is None else str(value)


def _price(value: float | None, currency: str | None = None, *, free: bool = False) -> str:
    if free:
        return "Free"
    if value is None:
        return "-"
    return f"{value:,.2f} {currency}" if currency else f"{value:,.2f}"


def _date(value: str | None) -> str:
    return value[:10] if value else "-"


@dataclass
class CourseCard:
    """One course on a search results page."""

    position: int
    course_id: int | None
    title: str
    url: str
    slug: str | None = None
    headline: str | None = None
    instructors: str | None = None
    rating: float | None = None
    num_ratings: int | None = None
    hours: float | None = None
    lectures: int | None = None
    questions: int | None = None
    level: str | None = None
    badges: list[str] = field(default_factory=list)
    is_free: bool = False
    price: float | None = None
    list_price: float | None = None
    discount_percent: int | None = None
    price_text: str | None = None
    list_price_text: str | None = None
    image: str | None = None
    page: int | None = None

    TABLE_HEADER = ("ID", "PRICE", "WAS", "RATING", "RATINGS", "HOURS", "LEVEL", "TITLE")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    def table_row(self) -> tuple[str, ...]:
        return (
            _id(self.course_id),
            "Free" if self.is_free else (self.price_text or "-"),
            self.list_price_text or "-",
            _num(self.rating, 1),
            _num(self.num_ratings),
            _num(self.hours, 1),
            self.level or "-",
            self.title,
        )


@dataclass
class SearchPage:
    """One page of course search results."""

    query: str
    page: int
    url: str
    courses: list[CourseCard] = field(default_factory=list)
    total_results: int | None = None
    page_count: int | None = None
    filters_applied: int | None = None
    no_results: bool = False

    @property
    def has_next(self) -> bool:
        return bool(self.courses) and self.page < (self.page_count or 0)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["has_next"] = self.has_next
        return data


@dataclass
class CourseDetails:
    """Everything the course page shows: ratings, students, content, deal, requirements, ..."""

    course_id: int
    title: str
    url: str | None
    slug: str | None = None
    headline: str | None = None
    description: str | None = None
    instructors: list[dict[str, Any]] = field(default_factory=list)
    category: str | None = None
    subcategory: str | None = None
    topic: str | None = None
    level: str | None = None
    language: str | None = None
    locale: str | None = None
    rating: float | None = None
    rating_recent: float | None = None
    num_ratings: int | None = None
    rating_distribution: dict[str, int] = field(default_factory=dict)
    students: int | None = None
    lectures: int | None = None
    quizzes: int | None = None
    practice_tests: int | None = None
    coding_exercises: int | None = None
    articles: int | None = None
    resources: int | None = None
    video_seconds: int | None = None
    content_info: str | None = None
    created: str | None = None
    published: str | None = None
    last_updated: str | None = None
    has_certificate: bool | None = None
    has_lifetime_access: bool | None = None
    has_captions: bool | None = None
    caption_languages: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    audience: list[str] = field(default_factory=list)
    is_paid: bool | None = None
    is_practice_test_course: bool | None = None
    country: str | None = None
    currency: str | None = None
    price: float | None = None
    list_price: float | None = None
    discount_percent: int | None = None
    deal_ends_at: str | None = None
    coupon_code: str | None = None
    badges: list[str] = field(default_factory=list)
    image: str | None = None

    TABLE_HEADER = ("ID", "PRICE", "LIST", "RATING", "RATINGS", "STUDENTS", "UPDATED", "TITLE")

    @property
    def is_free(self) -> bool:
        return self.is_paid is False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        row = self.to_dict()
        row["instructors"] = [i.get("name") for i in self.instructors]
        distribution = row.pop("rating_distribution")
        for stars in ("1", "2", "3", "4", "5"):
            row[f"ratings_{stars}_star"] = distribution.get(stars)
        return row

    def table_row(self) -> tuple[str, ...]:
        return (
            str(self.course_id),
            _price(self.price, self.currency, free=self.is_free),
            _price(self.list_price, self.currency, free=self.is_free),
            _num(self.rating, 2),
            _num(self.num_ratings),
            _num(self.students),
            _date(self.last_updated),
            self.title,
        )


@dataclass
class Lecture:
    """One curriculum item: a video or article lecture, a quiz, an exercise, a practice test."""

    section_index: int
    section_title: str
    index: int | None
    item_id: int | None
    title: str
    type: str | None = None
    kind: str | None = None
    duration: str | None = None
    duration_seconds: int | None = None
    preview: bool = False
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Section:
    index: int
    title: str
    lecture_count: int | None = None
    duration: str | None = None
    duration_seconds: int | None = None
    items: list[Lecture] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Curriculum:
    """A course's sections and every item in them."""

    course_id: int
    sections: list[Section] = field(default_factory=list)
    lectures: int | None = None
    total_duration: str | None = None
    total_seconds: int | None = None
    is_practice_test_course: bool | None = None

    TABLE_HEADER = ("SECTION", "#", "TYPE", "LENGTH", "PREVIEW", "TITLE")

    @property
    def items(self) -> list[Lecture]:
        return [item for section in self.sections for item in section.items]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def csv_rows(self) -> list[dict[str, Any]]:
        return [{"course_id": self.course_id, **item.to_dict()} for item in self.items]

    def table_rows(self) -> list[tuple[str, ...]]:
        return [
            (
                f"{item.section_index}. {item.section_title}",
                _num(item.index),
                item.kind or item.type or "-",
                item.duration or "-",
                "yes" if item.preview else "",
                item.title,
            )
            for item in self.items
        ]


@dataclass
class Review:
    course_id: int
    review_id: int
    rating: float | None
    content: str | None = None
    created: str | None = None
    modified: str | None = None
    reviewer: str | None = None
    response: str | None = None
    response_created: str | None = None

    TABLE_HEADER = ("DATE", "STARS", "REVIEWER", "REVIEW")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    def table_row(self) -> tuple[str, ...]:
        text = " ".join((self.content or "").split()) or "(rating only)"
        return (_date(self.created), _num(self.rating, 1), self.reviewer or "-", text)


@dataclass
class ReviewPage:
    course_id: int
    page: int
    total: int | None = None
    has_next: bool = False
    reviews: list[Review] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriceQuote:
    """A course's price for visitors from one country."""

    course_id: int
    country: str | None
    currency: str | None
    price: float | None
    list_price: float | None = None
    discount_percent: int | None = None
    is_free: bool = False

    TABLE_HEADER = ("COURSE", "COUNTRY", "PRICE", "LIST", "OFF")

    @property
    def on_sale(self) -> bool:
        return bool(self.discount_percent)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    def table_row(self) -> tuple[str, ...]:
        return (
            str(self.course_id),
            (self.country or "-").upper(),
            _price(self.price, self.currency, free=self.is_free),
            _price(self.list_price, self.currency, free=self.is_free),
            f"{self.discount_percent}%" if self.discount_percent else "-",
        )


@dataclass
class InstructorCourse:
    """One course on an instructor's profile."""

    course_id: int
    title: str
    url: str | None = None
    headline: str | None = None
    rating: float | None = None
    num_ratings: int | None = None
    students: int | None = None
    level: str | None = None
    content_info: str | None = None
    is_paid: bool | None = None
    currency: str | None = None
    list_price: float | None = None
    published: str | None = None
    last_updated: str | None = None
    image: str | None = None

    TABLE_HEADER = ("ID", "RATING", "RATINGS", "STUDENTS", "LENGTH", "UPDATED", "TITLE")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    def table_row(self) -> tuple[str, ...]:
        return (
            str(self.course_id),
            _num(self.rating, 2),
            _num(self.num_ratings),
            _num(self.students),
            self.content_info or "-",
            _date(self.last_updated),
            self.title,
        )


@dataclass
class Instructor:
    """An instructor profile with its public stats and (optionally) every course."""

    instructor_id: int | None
    slug: str
    name: str | None
    url: str
    title: str | None = None
    students: int | None = None
    reviews: int | None = None
    courses_count: int | None = None
    is_partner: bool = False
    about: str | None = None
    image: str | None = None
    links: dict[str, str] = field(default_factory=dict)
    courses: list[InstructorCourse] = field(default_factory=list)

    TABLE_HEADER = ("ID", "NAME", "STUDENTS", "REVIEWS", "COURSES", "TITLE")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        row = self.to_dict()
        row.pop("courses")
        links = row.pop("links")
        for name, value in links.items():
            row[f"link_{name}"] = value
        return row

    def table_row(self) -> tuple[str, ...]:
        return (
            _id(self.instructor_id),
            self.name or "-",
            _num(self.students),
            _num(self.reviews),
            _num(self.courses_count),
            self.title or "-",
        )


@dataclass
class Change:
    """A price change found by :meth:`UdemyScraper.watch`."""

    course_id: int
    country: str | None
    kind: str
    currency: str | None = None
    old_price: float | None = None
    new_price: float | None = None
    old_currency: str | None = None
    list_price: float | None = None
    discount_percent: int | None = None

    TABLE_HEADER = ("COURSE", "COUNTRY", "CHANGE", "OLD", "NEW", "LIST")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        return self.to_dict()

    def table_row(self) -> tuple[str, ...]:
        return (
            str(self.course_id),
            (self.country or "-").upper(),
            self.kind,
            _price(self.old_price, self.old_currency or self.currency),
            _price(self.new_price, self.currency),
            _price(self.list_price, self.currency),
        )
