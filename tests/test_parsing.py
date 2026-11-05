import json

import pytest
from conftest import (
    COURSE,
    CURRICULUM,
    INCENTIVES,
    INSTRUCTOR_HTML,
    NO_RESULTS_HTML,
    pricing_answer,
    reviews_answer,
    search_html,
    taught_answer,
)

from udemy_scraper import (
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
from udemy_scraper.parsing import duration_seconds, html_to_text, parse_amount, parse_int


def test_search_cards(search_page):
    page = parse_search(search_page, query="python", page=1)
    assert page.total_results == 1237
    assert page.page_count == 52
    assert page.filters_applied == 2
    assert page.has_next
    # The two carousel cards are not search results.
    assert [c.course_id for c in page.courses] == [1565838, 53600, 7339855]
    first = page.courses[0]
    assert first.title == "The Complete JavaScript Course"
    assert first.url == "https://www.udemy.com/course/the-complete-javascript-course/"
    assert first.slug == "the-complete-javascript-course"
    assert first.headline == "Learn it step by step"
    assert first.instructors == "Jane Doe"
    assert (first.rating, first.num_ratings, first.hours, first.lectures) == (4.7, 1234, 10.5, 120)
    assert first.level == "Beginner"
    assert first.badges == ["Bestseller"]
    assert (first.price, first.list_price, first.discount_percent) == (11.99, 49.99, 76)
    assert (first.price_text, first.list_price_text) == ("$11.99", "$49.99")
    assert first.image.endswith("/480x270/1565838_ab12_3.jpg")
    assert first.position == 1 and first.page == 1


def test_free_and_practice_test_cards(search_page):
    _, free, quiz = parse_search(search_page).courses
    assert free.is_free and free.price == 0.0 and free.list_price is None
    assert free.discount_percent is None
    assert quiz.questions == 1200 and quiz.lectures is None
    # Not rated yet: Udemy shows a 0.0 placeholder.
    assert quiz.rating is None and quiz.num_ratings is None
    assert quiz.instructors == "Dr. Angela Yu, Developer and Lead Instructor"


def test_no_results_page():
    page = parse_search(NO_RESULTS_HTML, query="zzqx")
    assert page.no_results and page.total_results == 0 and not page.courses
    assert not page.has_next


def test_page_past_the_end_is_empty():
    page = parse_search(search_html(total="10,000", pages=(1, 415, 416, 417)), page=500)
    assert page.courses == [] and page.page_count == 417 and not page.has_next


def test_single_page_without_pagination():
    html = search_html(
        '<div class="content-grid-item-module--item--MDYzd"></div>', pages=(), total="3"
    )
    assert parse_search(html, page=1).page_count is None


def test_non_search_page_is_a_bad_answer():
    with pytest.raises(ValueError):
        parse_search("<html><body>Just a moment...</body></html>")


def test_course_details():
    course = parse_course(COURSE, country="us")
    assert course.course_id == 567828
    assert course.slug == "complete-python-bootcamp"
    assert course.url == "https://www.udemy.com/course/complete-python-bootcamp/"
    assert course.headline == "Learn Python like a Professional Start from the basics"
    assert course.description == "Become a Python Programmer today!\n- Games\n- Apps"
    assert course.instructors[0]["url"] == "https://www.udemy.com/user/joseportilla/"
    assert course.rating_distribution["5"] == 311674
    assert (course.category, course.subcategory, course.topic) == (
        "Development",
        "Programming Languages",
        "Python",
    )
    assert course.language == "English" and course.locale == "en_US"
    assert course.objectives == ["Use Python to solve tasks.", "Build games."]
    assert course.requirements and course.audience
    assert (course.currency, course.price, course.list_price) == ("USD", 29.99, 199.99)
    assert course.discount_percent == 85
    assert course.deal_ends_at == "2026-11-05T08:00:00Z"
    assert course.coupon_code == "MT261103G1"
    assert course.badges == ["Bestseller"]
    row = course.to_row()
    assert row["ratings_1_star"] == 2731 and row["instructors"] == ["Jose Portilla"]


def test_course_without_a_deal_and_free_course():
    plain = dict(COURSE, discount=None)
    course = parse_course(plain)
    assert (course.price, course.list_price, course.discount_percent) == (199.99, 199.99, None)
    assert course.deal_ends_at is None and course.coupon_code is None
    free = parse_course(dict(COURSE, is_paid=False, discount=None, price_detail=None))
    assert free.is_free and free.price == 0.0 and free.list_price is None and free.currency is None


def test_course_answer_must_be_a_course():
    with pytest.raises(ValueError):
        parse_course({"detail": "Not found."})


def test_incentives_add_content_counts():
    course = apply_incentives(parse_course(COURSE), INCENTIVES)
    assert (course.articles, course.coding_exercises, course.resources) == (27, 19, 3)
    assert course.has_lifetime_access is True
    with pytest.raises(ValueError):
        apply_incentives(parse_course(COURSE), {"detail": "x"})


def test_curriculum():
    curriculum = parse_curriculum(CURRICULUM, 567828)
    assert [s.title for s in curriculum.sections] == ["Course Overview", "Python Basics"]
    assert curriculum.total_seconds == 80607 and curriculum.lectures == 170
    video, article, exercise, quiz = curriculum.items
    assert (video.kind, video.type, video.duration_seconds, video.preview) == (
        "video",
        "lecture",
        399,
        True,
    )
    assert video.description == "The Complete Python Bootcamp."
    assert article.kind == "article" and article.description is None
    assert exercise.type == "coding_exercise" and exercise.duration_seconds is None
    assert quiz.type == "quiz" and quiz.duration == "5 questions"
    assert curriculum.sections[1].duration_seconds == 3723
    rows = curriculum.csv_rows()
    assert len(rows) == 4 and rows[0]["course_id"] == 567828


def test_reviews():
    page = parse_reviews(reviews_answer([11, 12], has_next=True), 567828, page=1)
    assert page.total == 2731 and page.has_next
    first, second = page.reviews
    assert first.content == "Review number 11 with text"
    assert first.rating == 1.5
    assert first.reviewer == "Abdul Q."
    assert first.response == "Thanks for the feedback!"
    assert second.content is None and second.response is None


def test_pricing():
    quotes = parse_pricing(pricing_answer({567828: (29.99, 199.99), 4579230: (0.0, 0.0)}), "us")
    paid, free = quotes
    assert (paid.course_id, paid.currency, paid.price, paid.list_price) == (
        567828,
        "USD",
        29.99,
        199.99,
    )
    assert paid.discount_percent == 85 and paid.on_sale and paid.country == "us"
    assert free.is_free and free.discount_percent is None
    with pytest.raises(ValueError):
        parse_pricing({"detail": "x"})


def test_instructor_profile():
    profile = parse_instructor(INSTRUCTOR_HTML, "joseportilla")
    assert profile.instructor_id == 9685726
    assert profile.name == "Jose Portilla"
    assert (profile.students, profile.reviews, profile.courses_count) == (4665846, 1371148, 86)
    assert profile.is_partner
    assert profile.about == "Jose has a BS and MS in Mechanical Engineering from Santa Clara."
    assert set(profile.links) == {"twitter", "linkedin", "personal_website"}
    assert profile.url == "https://www.udemy.com/user/joseportilla/"
    with pytest.raises(ValueError):
        parse_instructor("<html><body>Page not found</body></html>", "x")


def test_instructor_courses():
    total, has_next, courses = parse_instructor_courses(taught_answer([1, 2], has_next=True))
    assert total == 85 and has_next and [c.course_id for c in courses] == [1, 2]
    assert courses[0].list_price == 99.99 and courses[0].level == "Expert"


def test_load_json_plain_and_browser_view():
    assert load_json(json.dumps({"a": 1})) == {"a": 1}
    assert load_json('<html><body><pre>{"a": "x &amp; y"}</pre></body></html>') == {"a": "x & y"}
    with pytest.raises(ValueError):
        load_json("<html><body>blocked</body></html>")


@pytest.mark.parametrize(
    "text, expected", [("$1,299.99", 1299.99), ("₹459", 459.0), ("Free", 0.0), (None, None)]
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_small_helpers():
    assert duration_seconds("06:39") == 399
    assert duration_seconds("1:02:03") == 3723
    assert duration_seconds("5 questions") is None
    assert parse_int("86,564 ratings") == 86564
    assert html_to_text("a &amp; b") == "a & b"
    assert html_to_text("<p>One<br>Two</p>") == "One\nTwo"
