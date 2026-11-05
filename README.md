# Udemy Scraper

[![CI](https://github.com/ScrapeUnblocker/udemy-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/udemy-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape [Udemy](https://www.udemy.com) courses into clean JSON or CSV: course search with
Udemy's own sort orders and filters, full course details, the complete curriculum, reviews,
regional prices across countries, a deal and price watcher, and instructor profiles.**
For every course in the search results you get the course id, title, URL, headline,
instructors, rating and rating count, total hours, lecture count (or question count for
practice tests), level, badges ("Bestseller", "Highest Rated", "New"), current price,
original price and percent off. Open a course to get its students, average and recent
rating, the 1-5 star rating distribution, category, subcategory and topic, language,
what you'll learn, requirements, target audience, caption languages, lecture, quiz,
article, coding exercise and resource counts, video length, created, published and
last-updated dates, the current deal with list price, discount, end time and the public
coupon code, and every instructor with their job title.

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
Udemy's search page is rendered in a real browser by the `getPageSource` API with
browser steps, and everything else comes from the JSON endpoints udemy.com calls itself,
fetched through the same API from the country you choose. You don't need a Udemy
account, cookies, proxies, a headless browser or retry logic of your own.

## Features

- **Course search with Udemy's filters.** Any query, sorted by relevance, most reviewed,
  highest rated or newest, filtered by language, level, minimum rating, free or paid,
  video length, features (coding exercises, practice tests, quizzes) and subtitles.
  24 courses per page, as many pages as you ask for (up to Udemy's page count), several
  queries merged without duplicates. Paste any udemy.com search URL and its filters are
  kept. Udemy's own "Selections applied" count is checked, so a filter Udemy ignored is
  reported instead of silently returning unfiltered results.
- **Course details** by id, slug or URL: rating distribution, students, content counts,
  learning objectives, requirements, audience, captions, dates, instructors, and the
  current price with deal information.
- **Curriculum**: every section with its length, and every item in it (video, article,
  quiz, coding exercise, practice test) with duration, free-preview flag and description.
- **Reviews**, newest first, 100 per request: filter by star bucket, skip rating-only
  reviews, includes the instructor's response.
- **Regional prices**: what the same courses cost in the US, UK, Germany, India, Japan,
  ... in local currency, up to 20 courses per request and country. Answers that Udemy
  priced for a different market are detected and asked for again.
- **Deal and price watcher**: run it daily; it reports deals that started or ended, price
  drops and increases, list price changes and courses that became free or paid.
- **Instructor profiles**: total learners, reviews, course count, partner badge, bio,
  links and every public course with rating, students and length.
- **JSON, JSON Lines, CSV (Excel-friendly) or a terminal table**, from a CLI or a Python
  library. Typed dataclasses, retries with backoff, offline tests.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/udemy-scraper.git
cd udemy-scraper
pip install .            # or: pip install -r requirements.txt
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and put it in the environment (the official SDK reads `SCRAPEUNBLOCKER_KEY`):

```bash
cp .env.example .env     # then edit .env, or:
export SCRAPEUNBLOCKER_KEY=your_key_here
```

## CLI usage

```bash
# Top-rated English Python courses rated 4.5+, two pages, as a table
udemy-scraper search python --sort rating --lang en --min-rating 4.5 --pages 2

# Free beginner courses for two searches, merged and de-duplicated, as CSV
udemy-scraper search "excel" "power bi" --price free --level beginner -o free-courses.csv

# Short courses (1-3 hours) with coding exercises, newest first
udemy-scraper search javascript --duration 1-3h --feature coding-exercises --sort newest

# Any udemy.com search URL, filters and sort included
udemy-scraper browse "https://www.udemy.com/courses/search/?q=react&ratings=4.5&sort=newest"

# Course details (id, slug or URL) as JSON, or many courses as CSV
udemy-scraper course https://www.udemy.com/course/complete-python-bootcamp/
udemy-scraper course 567828 100-days-of-code --from-file more-courses.txt -o courses.csv

# Every section and lecture
udemy-scraper curriculum 100-days-of-code
udemy-scraper curriculum 567828 -o curriculum.csv

# Reviews: the latest 1-star reviews that have text, or 5 pages of everything
udemy-scraper reviews complete-python-bootcamp --stars 1 --with-text --limit 50
udemy-scraper reviews 567828 --pages 5 -o reviews.csv

# What the same courses cost in five countries
udemy-scraper prices 567828 2776760 --countries us,gb,de,in,jp

# Deals and price changes since the last run (run it daily from cron)
udemy-scraper watch 567828 2776760 --state udemy-prices.json --countries us,in

# Instructor profile with every course, or only the courses as a table
udemy-scraper instructor https://www.udemy.com/user/joseportilla/
udemy-scraper instructor joseportilla --courses-only -f table
```

Every command takes `-f json|jsonl|csv|table` (default: from the `-o` file extension,
else a table, or JSON for `course` and `instructor`), `-o FILE`, `--retries N` and `-v`.
`--country` (default `us`; `--countries us,gb,...` for `prices` and `watch`) sets where
requests come from, and so the prices and currency.

### Search filters

| Option | Values | Udemy filter |
| --- | --- | --- |
| `--sort` | `relevance`, `reviews`, `rating`, `newest` | Most Relevant, Most Reviewed, Highest Rated, Newest |
| `--lang` | two-letter codes: `en`, `es`, `pt`, `de`, ... | Language |
| `--level` | `beginner`, `intermediate`, `expert`, `all-levels` | Level |
| `--min-rating` | `3.0`, `3.5`, `4.0`, `4.5` | Ratings |
| `--price` | `free`, `paid` | Price |
| `--duration` | `0-1h`, `1-3h`, `3-6h`, `6-17h`, `17h+` | Video Duration |
| `--feature` | `coding-exercises`, `practice-tests`, `quizzes` | Features |
| `--captions` | two-letter codes | Subtitles |

`--lang`, `--level`, `--duration`, `--feature` and `--captions` can be repeated to combine
options, as on udemy.com (`--lang` and `--captions` also take `en,es`).

## Library usage

```python
from udemy_scraper import SearchQuery, UdemyScraper

udemy = UdemyScraper()  # reads SCRAPEUNBLOCKER_KEY; prices as seen from the US

# One page of search results, or many pages and queries without duplicates
page = udemy.search("python", sort="rating", min_rating=4.5, languages=["en"])
print(page.total_results, page.page_count, page.filters_applied)
for course in page.courses[:5]:
    print(course.course_id, course.price, course.rating, course.num_ratings, course.title)

query = SearchQuery("data science", levels=("beginner",), durations=("1-3h", "3-6h"))
courses = udemy.search_courses([query, "machine learning"], pages=3, limit=100)

# Course details, curriculum and reviews (id, slug or URL)
course = udemy.course("https://www.udemy.com/course/complete-python-bootcamp/")
print(course.students, course.rating_distribution, course.price, course.deal_ends_at)
lectures = udemy.curriculum(course.course_id).items
critical = list(udemy.iter_reviews(course.course_id, stars=1, with_text=True, limit=20))

# Regional prices, a daily watcher and instructors
quotes = udemy.prices([course.course_id], countries=["us", "gb", "de", "in"])
changes = udemy.watch([course.course_id], state_path="udemy-prices.json")
teacher = udemy.instructor("https://www.udemy.com/user/joseportilla/", limit=10)

# Prices as seen from another country
udemy_in = UdemyScraper(country="in")
```

Every record is a dataclass with `to_dict()`; `udemy_scraper.write(records, "csv", path)`
writes JSON, JSON Lines, CSV or a table.

### Examples

- [`examples/search_to_csv.py`](examples/search_to_csv.py) - top-rated beginner Python
  courses, two pages, to CSV
- [`examples/price_comparison.py`](examples/price_comparison.py) - the same courses
  priced in five countries
- [`examples/review_digest.py`](examples/review_digest.py) - rating breakdown and the
  latest 1- and 2-star reviews of a course

## Example output

`udemy-scraper search python --sort rating --lang en --min-rating 4.5`:

```text
'python': 6,849 results, 286 pages
ID       PRICE   WAS     RATING  RATINGS  HOURS  LEVEL         TITLE
6618483  $11.99  $19.99  5.0     361      10.0   All Levels    DeepSeek AI and Coding Projects: From Prompts to Automation
6557521  $11.99  $19.99  5.0     166      4.5    All Levels    CO₂ Emissions Forecasting with Shallow Neural Nets in Python
6616079  $11.99  $19.99  5.0     131      2.5    All Levels    Economic Dispatch for Natural Gas-Electricity Networks
7312633  $11.99  $49.99  5.0     110      6.5    All Levels    AI Agents Bootcamp: Agentic Automation with Python & n8n
6049539  $11.99  $49.99  5.0     59       40.5   All Levels    Master Classification with Pandas and Python [2026]
```

`udemy-scraper prices 567828 2776760 --countries us,gb,de,in,jp`:

```text
COURSE   COUNTRY  PRICE          LIST           OFF
567828   US       29.99 USD      199.99 USD     85%
2776760  US       17.99 USD      129.99 USD     86%
567828   GB       34.99 GBP      34.99 GBP      -
2776760  GB       34.99 GBP      34.99 GBP      -
567828   DE       104.99 EUR     104.99 EUR     -
2776760  DE       129.99 EUR     129.99 EUR     -
567828   IN       459.00 INR     3,199.00 INR   86%
2776760  IN       459.00 INR     3,199.00 INR   86%
567828   JP       27,800.00 JPY  27,800.00 JPY  -
2776760  JP       27,800.00 JPY  27,800.00 JPY  -
```

`udemy-scraper course complete-python-bootcamp` (shortened):

```json
{
  "course_id": 567828,
  "title": "The Complete Python Bootcamp From Zero to Hero in Python",
  "url": "https://www.udemy.com/course/complete-python-bootcamp/",
  "instructors": [
    {
      "id": 9685726,
      "name": "Jose Portilla",
      "job_title": "Head of Data Science at Pierian Training",
      "url": "https://www.udemy.com/user/joseportilla/"
    }
  ],
  "category": "Development",
  "subcategory": "Programming Languages",
  "topic": "Python",
  "level": "All Levels",
  "language": "English",
  "rating": 4.5962863,
  "num_ratings": 567824,
  "rating_distribution": {"1": 2731, "2": 4983, "3": 43225, "4": 205198, "5": 311674},
  "students": 2207522,
  "lectures": 170,
  "quizzes": 27,
  "coding_exercises": 19,
  "articles": 27,
  "video_seconds": 79800,
  "content_info": "22.5 total hours",
  "last_updated": "2025-08-07",
  "has_certificate": true,
  "requirements": ["Access to a computer with an internet connection."],
  "country": "us",
  "currency": "USD",
  "price": 29.99,
  "list_price": 199.99,
  "discount_percent": 85,
  "deal_ends_at": "2026-11-05T08:00:00Z"
}
```

`udemy-scraper curriculum 100-days-of-code` (a few rows):

```text
102 sections, 664 items, 56:49:47 in total
SECTION                                                                #  TYPE             LENGTH      PREVIEW  TITLE
1. Day 1 - Beginner - Working with Variables in Python to Manage Data  1  video            03:27       yes      What you're going to get from this course
1. Day 1 - Beginner - Working with Variables in Python to Manage Data  2  video            02:53                START HERE
1. Day 1 - Beginner - Working with Variables in Python to Manage Data  5  article          02:01                DO NOT SKIP - Download and Setup PyCharm for Learning
1. Day 1 - Beginner - Working with Variables in Python to Manage Data  1  coding-exercise  1 question           Printing Practice
```

## How it works

- **Search** asks `getPageSource` to open udemy.com's search page in a browser and wait
  until the course prices have rendered (or Udemy's "no results" message appears). The
  course cards of the results grid are parsed from the page; the carousels Udemy mixes
  into the results ("Hot and Fresh Courses", ...) are skipped. The page count comes from
  Udemy's pagination, so multi-page runs stop at the last page. Pages are requested with
  English labels whatever the country, so the parser always reads the same words.
- **Course details, curriculum, reviews, prices and instructor courses** come from the
  JSON endpoints udemy.com itself uses, fetched with plain `getPageSource` calls. A course
  slug is turned into its numeric id once and cached.
- **Prices depend on the country.** Udemy prices each course per country and places a
  visitor with its own IP lookup. Requests go through the `--country` you choose (`us` by
  default). When an answer comes back in a currency that is not the country's own (for
  example US prices for a request from Germany), it is asked for again, up to three times.
  Udemy prices some countries in USD, so a country can still come back in USD: the
  `currency` column always says what you got.
- **Reliability**: throttled, blocked and timed-out requests are retried with doubling
  backoff (`--retries`). An answer without the expected data is fetched once more and then
  raises `ParseError`; an unknown course or instructor raises `NotFoundError`.

Good to know:

- A search page is rendered in a browser, so it takes longer than the JSON calls (often
  half a minute). Course, review and price calls usually answer in a few seconds.
- Udemy shows at most 10,000 results for a search, and the review count of very popular
  courses is capped at 10,000 too.
- Star buckets: `--stars 1` also returns 1.5-star reviews (Udemy files half stars under
  the lower bucket).
- `coupon_code` is the public code of the sitewide deal Udemy currently applies to the
  course (it is shown only while a deal is running).
- The `instructors` field of a search result is the text shown on the card; course
  details have the structured list.

## Project layout

```text
udemy-scraper/
├── src/udemy_scraper/
│   ├── __init__.py      # public API and __version__
│   ├── scraper.py       # UdemyScraper: fetch + retries, search, course, curriculum, reviews, prices, watch
│   ├── parsing.py       # rendered search page and JSON answers -> records
│   ├── urls.py          # search URLs and filters, course and instructor refs, endpoints
│   ├── models.py        # dataclasses with to_dict / to_row / table layouts
│   ├── monitor.py       # price snapshots and change detection
│   ├── export.py        # JSON / JSONL / CSV / table output
│   └── cli.py           # udemy-scraper command
├── examples/            # search export, regional prices, review digest
├── tests/               # offline tests with a mocked client (no API credit used)
├── pyproject.toml
├── Makefile
└── .github/workflows/ci.yml
```

## Development

```bash
pip install -e ".[dev]"
make lint      # ruff check + ruff format --check
make test      # pytest, offline
make format    # ruff format
```

The tests use small pages and answers built from the real structure of Udemy's markup and
JSON and a fake client, so they run without an API key or network access.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [ScrapeUnblocker documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
- [Python SDK on PyPI](https://pypi.org/project/scrapeunblocker/)

## License

[MIT](LICENSE) - Copyright (c) 2026 ScrapeUnblocker. This project is not affiliated with or
endorsed by Udemy, Inc. Respect Udemy's terms of use.
