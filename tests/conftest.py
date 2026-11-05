"""Shared fixtures: a fake ScrapeUnblocker client and small Udemy answers.

The answers are trimmed copies of what udemy.com really returns (same markup, class
names with build hashes, data-purpose attributes and JSON keys), so the tests run
offline without an API key.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from udemy_scraper import UdemyScraper

# -- fake SDK ----------------------------------------------------------------------------


class BlockedError(Exception):
    """Named like the SDK error, so the scraper treats it as transient."""


class TargetNotFoundError(Exception):
    pass


class StepFailedError(Exception):
    def __init__(self, message: str, html: str | None = None):
        super().__init__(message)
        self.html = html


class FakeClient:
    """``get_page_source`` answering from ``routes``: {url substring: answer}.

    An answer is a body string, an exception to raise, a function of ``(url, kwargs)``
    returning one of those, or a list of them used in turn (the last one repeats).
    Every call is recorded in ``calls``.
    """

    def __init__(self, routes: dict[str, Any]):
        self.routes = {k: (list(v) if isinstance(v, list) else [v]) for k, v in routes.items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_page_source(self, url: str, **kwargs: Any) -> str:
        self.calls.append((url, kwargs))
        for key, answers in self.routes.items():
            if key in url:
                answer = answers.pop(0) if len(answers) > 1 else answers[0]
                if callable(answer):
                    answer = answer(url, kwargs)
                if isinstance(answer, BaseException):
                    raise answer
                return answer
        raise AssertionError(f"unexpected URL {url}")

    def urls(self, part: str = "") -> list[str]:
        return [url for url, _ in self.calls if part in url]


@pytest.fixture
def make_scraper():
    def make(routes: dict[str, Any], **kwargs: Any) -> tuple[UdemyScraper, FakeClient]:
        client = FakeClient(routes)
        kwargs.setdefault("sleep", lambda seconds: None)
        return UdemyScraper(client=client, **kwargs), client

    return make


# -- search pages ------------------------------------------------------------------------


def card(
    course_id: int,
    slug: str,
    title: str,
    *,
    price: str = "$11.99",
    old_price: str | None = "$49.99",
    rating: str = "4.7",
    tags: tuple[str, ...] = ("1,234 ratings", "10.5 total hours", "120 lectures", "Beginner"),
    ribbon: str | None = None,
    headline: str = "Learn it step by step",
    instructors: str = "Jane Doe",
) -> str:
    """One course card, as the rendered search page has it."""
    ribbon_li = (
        f'<li><div class="tag-module--tag--4CWOQ tag-module--ribbon-tag--RLOp7">'
        f'<span class="ribbon-module--ribbon--vVul- ud-heading-xs"> {ribbon} </span></div></li>'
        if ribbon
        else ""
    )
    rating_li = (
        '<li><div class="tag-module--tag--4CWOQ tag-module--rating--pX-4W">'
        '<span class="star-rating-module--star-wrapper--i1cJH">'
        f'<span class="ud-sr-only"> Rating: {rating} out of 5 </span>'
        f'<span aria-hidden="true" class="ud-heading-xs" data-purpose="rating-number"> {rating} '
        "</span></span></div></li>"
    )
    tag_lis = "".join(f'<li><div class="tag-module--tag--4CWOQ"> {t} </div></li>' for t in tags)
    old = (
        '<div class="base-price-text-module--original-price--C6BJt" '
        'data-purpose="original-price-container"><div data-purpose="course-old-price-text">'
        f'<span class="ud-sr-only"> Original Price </span><span><s><span> {old_price} </span>'
        "</s></span></div></div>"
        if old_price
        else ""
    )
    image = f"https://img-c.udemycdn.com/course/240x135/{course_id}_ab12_3.jpg"
    srcset = f"{image} 240w, https://img-c.udemycdn.com/course/480x270/{course_id}_ab12_3.jpg 480w"
    return f"""
<div class="content-grid-item-module--item--MDYzd"><div class="popper-module--popper--mM5Ie">
<link as="document" href="/course/{slug}/" rel="prefetch"/>
<section class="vertical-card-module--card--Lgh-9 course-product-card--card--vJXkx">
  <img alt="" class="card-media-image-module--image---SB4-" src="{image}" srcset="{srcset}"/>
  <h2 class="ud-heading-lg card-title-module--title--bv1rZ">
    <a class="ud-link-neutral" href="/course/{slug}/?couponCode=X" target="_blank">
      <div class="card-title-module--clipped--DPJnT"> {title} </div></a></h2>
  <div class="card-description-module--description--5tzNB">
    <span data-purpose="safely-set-inner-html:course-card:course-headline"> {headline} </span></div>
  <div class="card-authors-module--authors--zIW0Y"><span class="ud-sr-only"> Instructor: </span>
    <span data-purpose="safely-set-inner-html:course-card:visible-instructors">
    {instructors} </span>
  </div>
  <ul class="tag-list-module--list--x5G-5">{ribbon_li}{rating_li}{tag_lis}</ul>
  <div class="base-price-text-module--container--Sfv-5" data-purpose="price-text-container">
    <div class="base-price-text-module--price-part---xQlz" data-purpose="course-price-text">
      <span class="ud-sr-only"> Current price </span><span><span> {price} </span></span></div>
    {old}
  </div>
</section></div></div>"""


def carousel(*cards: str) -> str:
    """A unit Udemy mixes into the results ("Hot and Fresh Courses")."""
    items = "".join(f'<div class="carousel-module--scroll-item--QZoS6">{c}</div>' for c in cards)
    return (
        '<div class="content-grid-item-module--item--MDYzd">'
        '<div class="search--unit-injection--kq4MV">'
        '<h2 class="ud-heading-xl recommendations--title--25Gqy"> Hot and Fresh Courses </h2>'
        f'<div class="carousel-module--container--VJYQ5">{items}</div></div></div>'
    )


def search_html(
    *body: str,
    query: str = "python",
    total: str = "1,237",
    pages: tuple[int, ...] = (1, 2, 3, 52),
    applied: int | None = None,
) -> str:
    selections = (
        f'<span class="ud-sr-only">Selections applied: {applied}</span> {applied}'
        if applied is not None
        else ""
    )
    links = "".join(
        f'<a aria-label="Page {n}" class="pagination-module--page--tnAlF" href="?p={n}">{n}</a>'
        for n in pages
    )
    return f"""<!DOCTYPE html><html lang="en-us"><head><title>Search results | Udemy</title></head>
<body><main>
<header class="search-results-header--container--7uFRN">
  <span data-purpose="safely-set-inner-html:search:query">Results for
  <span>"{query}"</span> <span class="search-results-header--count--KQNTy">({total} results)</span>
  </span></header>
<button type="button"><strong>All filters</strong>{selections}</button>
<div class="course-list--container--3zXPS"><div class="content-area-module--container--kxfKF">
<div class="content-grid-module--grid--YMPin">{"".join(body)}</div></div></div>
<nav class="pagination-module--container---ftUR">{links}</nav>
</main></body></html>"""


NO_RESULTS_HTML = """<!DOCTYPE html><html lang="en-us"><body>
<main class="ud-container no-results-module--no-results--LK4pd">
<h1 class="ud-heading-xl" data-purpose="safely-set-inner-html:search:no-results-for-query">
Sorry, we couldn't find any results for <q>zzqx</q></h1></main></body></html>"""


@pytest.fixture
def search_page() -> str:
    return search_html(
        card(
            1565838,
            "the-complete-javascript-course",
            "The Complete JavaScript Course",
            ribbon="Bestseller",
        ),
        card(
            53600,
            "useful-excel-for-beginners",
            "Useful Excel for Beginners",
            price="Free",
            old_price=None,
            rating="4.5",
            tags=("86,564 ratings", "9.5 total hours", "89 lectures", "All Levels"),
        ),
        carousel(
            card(7259437, "50-days-of-python", "50 Days of Python"),
            card(7372739, "python-programming-course", "PYTHON: Python Programming Course"),
        ),
        card(
            7339855,
            "python-programming-quiz",
            "Python Programming Quiz: Test Your Python",
            rating="0.0",
            tags=("1,200 questions", "All Levels"),
            ribbon="New",
            instructors="Dr. Angela Yu, Developer and Lead Instructor",
        ),
        applied=2,
    )


# -- JSON answers -------------------------------------------------------------------------


def dump(data: Any) -> str:
    return json.dumps(data, indent=1)


COURSE = {
    "_class": "course",
    "id": 567828,
    "title": "The Complete Python Bootcamp From Zero to Hero in Python",
    "url": "/course/complete-python-bootcamp/",
    "is_paid": True,
    "price_detail": {"amount": 199.99, "currency": "USD", "price_string": "$199.99"},
    "discount": {
        "price": {"amount": 29.99, "currency": "USD", "price_string": "$29.99"},
        "list_price": {"amount": 199.99, "currency": "USD", "price_string": "$199.99"},
        "has_discount_saving": True,
        "discount_percent": 85,
        "campaign": {
            "code": "MT261103G1",
            "end_time": "2026-11-05T08:00:00Z",
            "is_public": True,
            "show_code": True,
            "campaign_type": "deal",
        },
        "code": "MT261103G1",
        "is_public": True,
    },
    "visible_instructors": [
        {
            "_class": "user",
            "id": 9685726,
            "title": "Jose Portilla",
            "display_name": "Jose Portilla",
            "job_title": "Head of Data Science at Pierian Training",
            "url": "/user/joseportilla/",
        }
    ],
    "headline": "Learn Python like a Professional  Start from the basics",
    "description": "<p><strong>Become a Python Programmer</strong> today!</p><ul><li>Games</li>"
    "<li>Apps</li></ul>",
    "num_subscribers": 2207522,
    "avg_rating": 4.5962863,
    "avg_rating_recent": 4.6157317,
    "num_reviews": 567824,
    "rating_distribution": [
        {"rating": 1, "count": 2731},
        {"rating": 2, "count": 4983},
        {"rating": 3, "count": 43225},
        {"rating": 4, "count": 205198},
        {"rating": 5, "count": 311674},
    ],
    "num_published_lectures": 170,
    "num_published_quizzes": 27,
    "num_published_practice_tests": 0,
    "content_info": "22.5 total hours",
    "content_length_video": 79800,
    "created": "2015-07-29T00:12:23Z",
    "published_time": "2015-10-12T21:42:53Z",
    "last_update_date": "2025-08-07",
    "instructional_level_simple": "All Levels",
    "locale": {"locale": "en_US", "simple_english_title": "English"},
    "has_certificate": True,
    "has_closed_caption": True,
    "caption_languages": ["English [Auto]", "Spanish [Auto]"],
    "what_you_will_learn_data": {"items": ["Use Python to solve tasks.", "Build games."]},
    "requirements_data": {"items": ["Access to a computer with an internet connection."]},
    "who_should_attend_data": {"items": ["Beginners who have never programmed before."]},
    "primary_category": {"id": 288, "title": "Development"},
    "primary_subcategory": {"id": 12, "title": "Programming Languages"},
    "context_info": {"label": {"display_name": "Python"}},
    "is_practice_test_course": False,
    "badges": [],
    "bestseller_badge_content": {"badge_text": "Bestseller"},
    "image_480x270": "https://img-c.udemycdn.com/course/480x270/567828_67d0.jpg",
}

INCENTIVES = {
    "incentives": {
        "num_articles": 27,
        "num_quizzes": 27,
        "num_practice_tests": 0,
        "num_coding_exercises": 19,
        "num_additional_resources": 3,
        "has_lifetime_access": True,
        "has_certificate": True,
    }
}

CURRICULUM = {
    "curriculum_context": {
        "data": {
            "sections": [
                {
                    "content_length_text": "19:14",
                    "content_length": 1154.5,
                    "index": 1,
                    "lecture_count": 2,
                    "title": "Course Overview",
                    "items": [
                        {
                            "can_be_previewed": True,
                            "content_summary": "06:39",
                            "description": "<p>The Complete Python Bootcamp.</p>",
                            "id": 3421822,
                            "icon_class": "udi udi-video",
                            "is_coding_exercise": False,
                            "is_practice_test": False,
                            "title": "Course Introduction",
                            "object_index": 1,
                            "item_type": "lecture",
                        },
                        {
                            "can_be_previewed": False,
                            "content_summary": "00:44",
                            "description": "",
                            "id": 20205526,
                            "icon_class": "udi udi-article",
                            "is_coding_exercise": False,
                            "is_practice_test": False,
                            "title": "Auto-Welcome Message",
                            "object_index": 2,
                            "item_type": "lecture",
                        },
                    ],
                },
                {
                    "content_length_text": "1:02:03",
                    "content_length": 3723,
                    "index": 2,
                    "lecture_count": 1,
                    "title": "Python Basics",
                    "items": [
                        {
                            "can_be_previewed": False,
                            "content_summary": "1 question",
                            "id": 5551,
                            "icon_class": "udi udi-coding-exercise",
                            "is_coding_exercise": True,
                            "is_practice_test": False,
                            "title": "Printing Practice",
                            "object_index": 1,
                            "item_type": "quiz",
                        },
                        {
                            "can_be_previewed": False,
                            "content_summary": "5 questions",
                            "id": 5552,
                            "icon_class": "udi udi-quiz",
                            "title": "Basics Quiz",
                            "object_index": 2,
                            "item_type": "quiz",
                        },
                    ],
                },
            ],
            "estimated_content_length_text": "22:23:27",
            "estimated_content_length_in_seconds": 80607,
            "is_for_practice_test_course": False,
            "num_of_published_lectures": 170,
        }
    }
}


def reviews_answer(ids: list[int], *, has_next: bool = False, count: int = 2731) -> dict:
    results = []
    for n, review_id in enumerate(ids):
        results.append(
            {
                "_class": "course_review",
                "id": review_id,
                "content": "" if n % 2 else f"Review number {review_id} with <b>text</b>",
                "rating": 1.5 if n == 0 else 1.0,
                "created": "2026-10-30T09:22:09-07:00",
                "modified": "2026-11-01T15:15:35-08:00",
                "user": {"_class": "user", "title": "Abdul Q. Full", "name": "Abdul Q."},
                "response": (
                    {
                        "content": "<p>Thanks for the feedback!</p>",
                        "created": "2026-10-31T10:00:00Z",
                    }
                    if n == 0
                    else None
                ),
            }
        )
    return {
        "count": count,
        "next": "https://www.udemy.com/api-2.0/courses/567828/reviews/?page=2"
        if has_next
        else None,
        "previous": None,
        "results": results,
    }


def pricing_answer(prices: dict[int, tuple[float, float]], currency: str = "USD") -> dict:
    courses = {}
    for course_id, (price, list_price) in prices.items():
        courses[str(course_id)] = {
            "_class": "pricing_result",
            "price": {"amount": price, "currency": currency},
            "list_price": {"amount": list_price, "currency": currency},
            "price_detail": {"amount": list_price, "currency": currency} if list_price else None,
        }
    return {"courses": courses}


INSTRUCTOR_ARGS = {
    "instructor_id": 9685726,
    "name": "Jose Portilla",
    "title": "Head of Data Science at Pierian Training",
    "description": "<p>Jose has a BS and MS in Mechanical Engineering&nbsp;from Santa Clara.</p>",
    "image": "https://img-c.udemycdn.com/user/200_H/9685726_67e7_4.jpg",
    "social_links": {
        "twitter": "https://twitter.com/JoseMPortilla",
        "facebook": "",
        "linkedin": "https://linkedin.com/in/jmportilla",
        "personal_website": "https://www.pieriantraining.com",
    },
    "num_courses": 86,
    "num_students": 4665846,
    "num_reviews": 1371148,
}

INSTRUCTOR_HTML = f"""<!DOCTYPE html><html lang="en-us"><body>
<div class="ud-app-loader" data-module-args='{json.dumps(INSTRUCTOR_ARGS)}'
 data-module-id="user-profile/instructor">
<h1 class="ud-heading-xxl title-area-module--instructor-name--qQ-5Q"> Jose Portilla </h1>
<span class="ribbon-module--ribbon--vVul- ud-heading-xs">
<span> Udemy Instructor Partner </span></span>
</div></body></html>"""


def taught_answer(ids: list[int], *, has_next: bool = False) -> dict:
    return {
        "count": 85,
        "next": "https://www.udemy.com/api-2.0/users/9685726/taught-profile-courses/?page=2"
        if has_next
        else None,
        "results": [
            {
                "_class": "course",
                "id": course_id,
                "title": f"Course {course_id}",
                "url": f"/course/course-{course_id}/",
                "headline": "A course",
                "avg_rating": 4.6,
                "num_reviews": 1311,
                "num_subscribers": 13803,
                "instructional_level_simple": "Expert",
                "content_info": "26.5 total hours",
                "is_paid": True,
                "price_detail": {"amount": 99.99, "currency": "USD"},
                "published_time": "2021-07-08T14:25:15Z",
                "last_update_date": "2023-04-12",
            }
            for course_id in ids
        ],
    }
