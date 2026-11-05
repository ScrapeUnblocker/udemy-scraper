"""Turn Udemy's pages and JSON answers into records.

* Search results come from the rendered search page: every course card in the results
  grid (cards in the carousels Udemy mixes into the results are skipped), the result
  count, the page count and how many filters Udemy applied.
* Course details, the curriculum, reviews, prices and instructor courses come from the
  JSON endpoints udemy.com itself calls.
* An instructor profile comes from the JSON udemy.com embeds in the profile page.

Every ``parse_*`` function raises ``ValueError`` when the input is not the expected
Udemy data, which the scraper treats as a bad answer and fetches once more.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from .models import (
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
from .urls import absolute, instructor_url

#: Course fields read from the course endpoint.
COURSE_FIELDS = (
    "title,headline,description,url,is_paid,price_detail,discount,visible_instructors,"
    "num_subscribers,avg_rating,avg_rating_recent,num_reviews,rating_distribution,"
    "num_published_lectures,num_published_quizzes,num_published_practice_tests,"
    "content_info,content_length_video,created,published_time,last_update_date,"
    "instructional_level_simple,locale,has_certificate,has_closed_caption,caption_languages,"
    "what_you_will_learn_data,requirements_data,who_should_attend_data,primary_category,"
    "primary_subcategory,context_info,is_practice_test_course,badges,"
    "bestseller_badge_content,image_480x270"
)
#: Course fields read for an instructor's course list.
INSTRUCTOR_COURSE_FIELDS = (
    "title,url,headline,avg_rating,num_reviews,num_subscribers,instructional_level_simple,"
    "content_info,is_paid,price_detail,published_time,last_update_date,image_480x270"
)
#: Fields of a price answer.
PRICING_FIELDS = "price,list_price,price_detail"

LEVEL_NAMES = ("Beginner", "Intermediate", "Expert", "All Levels")

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_IMAGE_ID = re.compile(r"/course/\d+x\d+/(\d+)_")
_SLUG = re.compile(r"/course/([^/?#]+)")
_CLOCK = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")
_TOTAL = re.compile(r"\(([\d,]+)\s+results?\)")
_SELECTIONS = re.compile(r"Selections applied:\s*(\d+)")
_TAGS = (
    ("num_ratings", re.compile(r"^([\d,]+) ratings?$")),
    ("hours", re.compile(r"^([\d.]+) total hours?$")),
    ("minutes", re.compile(r"^([\d.]+) total mins?$")),
    ("lectures", re.compile(r"^([\d,]+) lectures?$")),
    ("questions", re.compile(r"^([\d,]+) questions?$")),
)
_BLOCKS = ("p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "pre")


# -- small helpers ---------------------------------------------------------------------


def load_json(body: Any) -> Any:
    """Decode a JSON answer (plain, or wrapped in the browser's ``<pre>`` view)."""
    text = body.strip() if isinstance(body, str) else str(body).strip()
    if text.startswith("<"):
        match = re.search(r"<pre[^>]*>(.*?)</pre>", text, re.S | re.I)
        if not match:
            raise ValueError("expected JSON, got an HTML page")
        text = htmllib.unescape(match.group(1)).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"answer is not JSON ({exc})") from None


def parse_int(value: Any) -> int | None:
    """``"86,564 ratings"`` -> 86564."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    match = _NUMBER.search(str(value))
    return int(float(match.group(0).replace(",", ""))) if match else None


def parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER.search(str(value))
    return float(match.group(0).replace(",", "")) if match else None


def parse_amount(text: str | None) -> float | None:
    """The number in a displayed price: ``"$1,299.99"`` -> 1299.99, ``"Free"`` -> 0.0."""
    if not text:
        return None
    if text.strip().lower() == "free":
        return 0.0
    return parse_float(text)


def duration_seconds(text: str | None) -> int | None:
    """``"06:39"`` -> 399, ``"1:02:03"`` -> 3723 (anything else -> ``None``)."""
    match = _CLOCK.match((text or "").strip())
    if not match:
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def html_to_text(markup: str | None) -> str | None:
    """Readable text from a bit of HTML: one line per paragraph, ``- `` before list items."""
    if not markup:
        return None
    if "<" not in markup:
        text = htmllib.unescape(markup)
        return " ".join(text.split()) or None
    soup = BeautifulSoup(markup, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for item in soup.find_all("li"):
        item.insert(0, "- ")
    for block in soup.find_all(_BLOCKS):
        block.append("\n")
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line) or None


def _classes(tag: Tag) -> list[str]:
    value = tag.get("class") or []
    return value.split() if isinstance(value, str) else list(value)


def _has_class(tag: Tag, prefix: str) -> bool:
    """CSS-module class names end in a build hash (``card--Lgh-9``): match the prefix."""
    return any(name.startswith(prefix) for name in _classes(tag))


def _text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    return " ".join(tag.get_text(" ").split()) or None


def _visible_text(tag: Tag | None) -> str | None:
    """Text without the screen-reader-only labels ("Current price", "Original Price")."""
    if tag is None:
        return None
    parts = []
    for piece in tag.find_all(string=True):
        parent = piece.parent
        hidden = False
        while parent is not None and parent is not tag:
            if "ud-sr-only" in _classes(parent):
                hidden = True
                break
            parent = parent.parent
        if not hidden:
            parts.append(str(piece))
    return " ".join("".join(parts).split()) or None


def _by_purpose(root: Tag, purpose: str) -> Tag | None:
    return root.find(attrs={"data-purpose": purpose})


def _amount(price: Any) -> float | None:
    if isinstance(price, dict):
        return parse_float(price.get("amount"))
    return None


def _percent_off(price: float | None, list_price: float | None) -> int | None:
    if price is None or not list_price or list_price <= price:
        return None
    return round((1 - price / list_price) * 100)


# -- search results --------------------------------------------------------------------


def _in_carousel(card: Tag) -> bool:
    """Udemy mixes carousels ("Hot and Fresh Courses", ...) into the results grid."""
    for parent in card.parents:
        if not isinstance(parent, Tag):
            continue
        if _has_class(parent, "search--unit-injection") or _has_class(parent, "carousel-module--"):
            return True
    return False


def _page_count(soup: BeautifulSoup) -> int | None:
    numbers = []
    for tag in soup.find_all(["a", "span", "button"]):
        if _has_class(tag, "pagination-module--page"):
            number = parse_int(_text(tag))
            if number:
                numbers.append(number)
    return max(numbers) if numbers else None


def _filters_applied(soup: BeautifulSoup) -> int:
    for piece in soup.find_all(string=_SELECTIONS):
        match = _SELECTIONS.search(str(piece))
        if match:
            return int(match.group(1))
    return 0


def _image(card: Tag) -> tuple[str | None, int | None]:
    img = card.find("img")
    if img is None:
        return None, None
    src = img.get("src") or ""
    best = src
    for entry in (img.get("srcset") or "").split(","):
        url = entry.strip().split(" ")[0]
        if "/480x270/" in url:
            best = url
    match = _IMAGE_ID.search(best) or _IMAGE_ID.search(src)
    return (best or None), (int(match.group(1)) if match else None)


def parse_card(card: Tag, position: int, page: int | None = None) -> CourseCard:
    """One course card of the results grid."""
    link = card.find("a", href=_SLUG)
    if link is None:
        raise ValueError("course card without a course link")
    href = str(link["href"]).split("?")[0]
    slug_match = _SLUG.search(href)
    image, course_id = _image(card)
    result = CourseCard(
        position=position,
        course_id=course_id,
        title=_text(link) or "",
        url=absolute(href) or href,
        slug=slug_match.group(1) if slug_match else None,
        headline=_text(_by_purpose(card, "safely-set-inner-html:course-card:course-headline")),
        # As shown on the card: display names can contain commas themselves.
        instructors=_text(
            _by_purpose(card, "safely-set-inner-html:course-card:visible-instructors")
        ),
        image=image,
        page=page,
    )
    tag_list = next((ul for ul in card.find_all("ul") if _has_class(ul, "tag-list-module--")), None)
    rating = None
    for item in tag_list.find_all("li") if tag_list is not None else ():
        number = _by_purpose(item, "rating-number")
        if number is not None:
            rating = parse_float(_text(number))
            continue
        text = _visible_text(item)
        if not text:
            continue
        if item.find(lambda t: _has_class(t, "ribbon-module--ribbon")):
            result.badges.append(text)
            continue
        if text in LEVEL_NAMES:
            result.level = text
            continue
        for name, pattern in _TAGS:
            match = pattern.match(text)
            if match:
                if name == "hours":
                    result.hours = float(match.group(1))
                elif name == "minutes":
                    result.hours = round(float(match.group(1)) / 60, 2)
                else:
                    setattr(result, name, parse_int(match.group(1)))
                break
        else:
            result.badges.append(text)
    # Courses nobody has rated yet show a 0.0 placeholder rating.
    result.rating = rating if result.num_ratings else None
    price_text = _visible_text(_by_purpose(card, "course-price-text"))
    list_text = _visible_text(_by_purpose(card, "course-old-price-text"))
    result.is_free = (price_text or "").lower() == "free"
    result.price_text = price_text
    result.list_price_text = list_text
    result.price = parse_amount(price_text)
    result.list_price = parse_amount(list_text)
    result.discount_percent = _percent_off(result.price, result.list_price)
    return result


def parse_search(html: str, *, query: str = "", page: int = 1, url: str = "") -> SearchPage:
    """One rendered search results page (an empty page past the last one is fine)."""
    soup = BeautifulSoup(html, "html.parser")
    no_results = _by_purpose(soup, "safely-set-inner-html:search:no-results-for-query")
    header = _by_purpose(soup, "safely-set-inner-html:search:query")
    if no_results is None and header is None:
        raise ValueError("not a Udemy search results page")
    result = SearchPage(query=query, page=page, url=url)
    if no_results is not None:
        result.no_results = True
        result.total_results = 0
        result.page_count = 0
        return result
    match = _TOTAL.search(_text(header) or "")
    result.total_results = parse_int(match.group(1)) if match else None
    cards = [
        c
        for c in soup.find_all("section")
        if _has_class(c, "vertical-card-module--card") and not _in_carousel(c)
    ]
    for card in cards:
        result.courses.append(parse_card(card, len(result.courses) + 1, page))
    result.page_count = _page_count(soup) or (page if result.courses else None)
    result.filters_applied = _filters_applied(soup)
    return result


# -- course details --------------------------------------------------------------------


def _items(block: Any) -> list[str]:
    if isinstance(block, dict):
        block = block.get("items")
    return [str(x).strip() for x in block or [] if str(x).strip()]


def _badges(data: dict[str, Any]) -> list[str]:
    names = []
    for badge in [*(data.get("badges") or []), data.get("bestseller_badge_content")]:
        if isinstance(badge, dict):
            name = badge.get("badge_text") or badge.get("name") or badge.get("title")
        else:
            name = badge
        if name and str(name) not in names:
            names.append(str(name))
    return names


def _slug(url: str | None) -> str | None:
    match = _SLUG.search(url or "")
    return match.group(1) if match else None


def parse_course(data: Any, *, country: str | None = None) -> CourseDetails:
    """The course endpoint's answer (asked for :data:`COURSE_FIELDS`)."""
    if not isinstance(data, dict) or data.get("_class") != "course" or "id" not in data:
        raise ValueError("not a Udemy course answer")
    discount = data.get("discount") or {}
    price_detail = data.get("price_detail") or {}
    list_price = _amount(discount.get("list_price")) or _amount(price_detail)
    price = _amount(discount.get("price"))
    if price is None:
        price = list_price
    currency = (discount.get("price") or {}).get("currency") or price_detail.get("currency")
    is_paid = data.get("is_paid")
    if is_paid is False:
        price, list_price = 0.0, None
    percent = None
    if discount.get("has_discount_saving"):
        percent = parse_int(discount.get("discount_percent")) or _percent_off(price, list_price)
    campaign = discount.get("campaign") or {}
    coupon = None
    if discount.get("is_public") and campaign.get("show_code"):
        coupon = discount.get("code") or campaign.get("code")
    locale = data.get("locale") or {}
    context = data.get("context_info") or {}
    instructors = [
        {
            "id": person.get("id"),
            "name": person.get("display_name") or person.get("title"),
            "job_title": person.get("job_title") or None,
            "url": absolute(person.get("url")),
        }
        for person in data.get("visible_instructors") or []
        if isinstance(person, dict)
    ]
    distribution = {
        str(row.get("rating")): int(row.get("count") or 0)
        for row in data.get("rating_distribution") or []
        if isinstance(row, dict) and row.get("rating") is not None
    }
    return CourseDetails(
        course_id=int(data["id"]),
        title=str(data.get("title") or ""),
        url=absolute(data.get("url")),
        slug=_slug(data.get("url")),
        headline=" ".join(str(data.get("headline") or "").split()) or None,
        description=html_to_text(data.get("description")),
        instructors=instructors,
        category=(data.get("primary_category") or {}).get("title"),
        subcategory=(data.get("primary_subcategory") or {}).get("title"),
        topic=(context.get("label") or {}).get("display_name"),
        level=data.get("instructional_level_simple"),
        language=locale.get("simple_english_title") or locale.get("english_title"),
        locale=locale.get("locale"),
        rating=parse_float(data.get("avg_rating")),
        rating_recent=parse_float(data.get("avg_rating_recent")),
        num_ratings=parse_int(data.get("num_reviews")),
        rating_distribution=distribution,
        students=parse_int(data.get("num_subscribers")),
        lectures=parse_int(data.get("num_published_lectures")),
        quizzes=parse_int(data.get("num_published_quizzes")),
        practice_tests=parse_int(data.get("num_published_practice_tests")),
        video_seconds=parse_int(data.get("content_length_video")),
        content_info=data.get("content_info"),
        created=data.get("created"),
        published=data.get("published_time"),
        last_updated=data.get("last_update_date"),
        has_certificate=data.get("has_certificate"),
        has_captions=data.get("has_closed_caption"),
        caption_languages=[str(x) for x in data.get("caption_languages") or []],
        objectives=_items(data.get("what_you_will_learn_data")),
        requirements=_items(data.get("requirements_data")),
        audience=_items(data.get("who_should_attend_data")),
        is_paid=is_paid,
        is_practice_test_course=data.get("is_practice_test_course"),
        country=country,
        currency=currency if is_paid is not False else None,
        price=price,
        list_price=list_price,
        discount_percent=percent,
        deal_ends_at=campaign.get("end_time") if percent else None,
        coupon_code=coupon if percent else None,
        badges=_badges(data),
        image=data.get("image_480x270"),
    )


def apply_incentives(details: CourseDetails, data: Any) -> CourseDetails:
    """Add the "This course includes" counts (articles, exercises, resources, ...)."""
    incentives = data.get("incentives") if isinstance(data, dict) else None
    if not isinstance(incentives, dict):
        raise ValueError("not a Udemy course components answer")
    details.articles = parse_int(incentives.get("num_articles"))
    details.coding_exercises = parse_int(incentives.get("num_coding_exercises"))
    details.resources = parse_int(incentives.get("num_additional_resources"))
    details.has_lifetime_access = incentives.get("has_lifetime_access")
    if details.quizzes is None:
        details.quizzes = parse_int(incentives.get("num_quizzes"))
    if details.practice_tests is None:
        details.practice_tests = parse_int(incentives.get("num_practice_tests"))
    if details.has_certificate is None:
        details.has_certificate = incentives.get("has_certificate")
    return details


# -- curriculum ------------------------------------------------------------------------


def _item_type(item: dict[str, Any]) -> str | None:
    if item.get("is_coding_exercise"):
        return "coding_exercise"
    if item.get("is_practice_test"):
        return "practice_test"
    return item.get("item_type")


def parse_curriculum(data: Any, course_id: int) -> Curriculum:
    """The ``curriculum_context`` course component."""
    context = None
    if isinstance(data, dict):
        context = (data.get("curriculum_context") or {}).get("data")
    if not isinstance(context, dict) or not isinstance(context.get("sections"), list):
        raise ValueError("not a Udemy curriculum answer")
    sections = []
    for number, raw in enumerate(context["sections"], 1):
        index = parse_int(raw.get("index")) or number
        title = " ".join(str(raw.get("title") or "").split())
        section = Section(
            index=index,
            title=title,
            lecture_count=parse_int(raw.get("lecture_count")),
            duration=raw.get("content_length_text"),
            duration_seconds=parse_int(raw.get("content_length")),
        )
        for item in raw.get("items") or []:
            icon = re.search(r"udi-([a-z0-9-]+)", str(item.get("icon_class") or ""))
            summary = item.get("content_summary") or None
            section.items.append(
                Lecture(
                    section_index=index,
                    section_title=title,
                    index=parse_int(item.get("object_index")),
                    item_id=parse_int(item.get("id")),
                    title=" ".join(str(item.get("title") or "").split()),
                    type=_item_type(item),
                    kind=icon.group(1) if icon else None,
                    duration=summary,
                    duration_seconds=duration_seconds(summary),
                    preview=bool(item.get("can_be_previewed")),
                    description=html_to_text(item.get("description")),
                )
            )
        sections.append(section)
    return Curriculum(
        course_id=course_id,
        sections=sections,
        lectures=parse_int(context.get("num_of_published_lectures")),
        total_duration=context.get("estimated_content_length_text"),
        total_seconds=parse_int(context.get("estimated_content_length_in_seconds")),
        is_practice_test_course=context.get("is_for_practice_test_course"),
    )


# -- reviews ---------------------------------------------------------------------------


def parse_reviews(data: Any, course_id: int, page: int = 1) -> ReviewPage:
    """One page of the course reviews endpoint (newest first)."""
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("not a Udemy reviews answer")
    reviews = []
    for raw in data["results"]:
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        user = raw.get("user") or {}
        response = raw.get("response") if isinstance(raw.get("response"), dict) else {}
        reviews.append(
            Review(
                course_id=course_id,
                review_id=int(raw["id"]),
                rating=parse_float(raw.get("rating")),
                content=html_to_text(raw.get("content")),
                created=raw.get("created"),
                modified=raw.get("modified"),
                # The short name Udemy shows next to a review ("Nicholas R.").
                reviewer=user.get("name") or None,
                response=html_to_text(response.get("content")),
                response_created=response.get("created"),
            )
        )
    return ReviewPage(
        course_id=course_id,
        page=page,
        total=parse_int(data.get("count")),
        has_next=bool(data.get("next")),
        reviews=reviews,
    )


# -- prices ----------------------------------------------------------------------------


def parse_pricing(data: Any, country: str | None = None) -> list[PriceQuote]:
    """The pricing endpoint's answer: one quote per course, in the visitor's currency."""
    courses = data.get("courses") if isinstance(data, dict) else None
    if not isinstance(courses, dict):
        raise ValueError("not a Udemy pricing answer")
    quotes = []
    for course_id, raw in courses.items():
        if not isinstance(raw, dict) or not str(course_id).isdigit():
            continue
        price = _amount(raw.get("price"))
        list_price = _amount(raw.get("list_price")) or _amount(raw.get("price_detail"))
        if list_price is None:
            list_price = price
        currency = None
        for key in ("price", "list_price", "price_detail"):
            if isinstance(raw.get(key), dict) and raw[key].get("currency"):
                currency = raw[key]["currency"]
                break
        quotes.append(
            PriceQuote(
                course_id=int(course_id),
                country=country,
                currency=currency,
                price=price,
                list_price=list_price,
                discount_percent=_percent_off(price, list_price),
                is_free=price == 0 and not list_price,
            )
        )
    return quotes


# -- instructors -----------------------------------------------------------------------


def parse_instructor(html: str, slug: str) -> Instructor:
    """An instructor profile page (the JSON it embeds, plus the partner ribbon)."""
    soup = BeautifulSoup(html, "html.parser")
    block = soup.find(attrs={"data-module-id": "user-profile/instructor"})
    if block is None:
        raise ValueError("not a Udemy instructor profile page")
    try:
        args = json.loads(block.get("data-module-args") or "{}")
    except json.JSONDecodeError:
        raise ValueError("unreadable instructor profile data") from None
    links = {
        name: str(value)
        for name, value in (args.get("social_links") or {}).items()
        if isinstance(value, str) and value.strip()
    }
    return Instructor(
        instructor_id=parse_int(args.get("instructor_id")),
        slug=slug,
        name=args.get("name"),
        url=instructor_url(slug),
        title=args.get("title") or None,
        students=parse_int(args.get("num_students")),
        reviews=parse_int(args.get("num_reviews")),
        courses_count=parse_int(args.get("num_courses")),
        is_partner="Udemy Instructor Partner" in (_text(block) or ""),
        about=html_to_text(args.get("description")),
        image=args.get("image"),
        links=links,
    )


def parse_instructor_courses(data: Any) -> tuple[int | None, bool, list[InstructorCourse]]:
    """One page of an instructor's courses: ``(total, has_next, courses)``."""
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError("not a Udemy instructor courses answer")
    courses = []
    for raw in data["results"]:
        if not isinstance(raw, dict) or raw.get("id") is None:
            continue
        price_detail = raw.get("price_detail") or {}
        courses.append(
            InstructorCourse(
                course_id=int(raw["id"]),
                title=str(raw.get("title") or ""),
                url=absolute(raw.get("url")),
                headline=" ".join(str(raw.get("headline") or "").split()) or None,
                rating=parse_float(raw.get("avg_rating")),
                num_ratings=parse_int(raw.get("num_reviews")),
                students=parse_int(raw.get("num_subscribers")),
                level=raw.get("instructional_level_simple"),
                content_info=raw.get("content_info"),
                is_paid=raw.get("is_paid"),
                currency=price_detail.get("currency"),
                list_price=_amount(price_detail),
                published=raw.get("published_time"),
                last_updated=raw.get("last_update_date"),
                image=raw.get("image_480x270"),
            )
        )
    return parse_int(data.get("count")), bool(data.get("next")), courses
