"""Compare what the same Udemy courses cost in different countries.

Udemy prices every course per country (and runs deals per country), so the price a
visitor sees depends on where they browse from. One request prices up to 20 courses
for one country.

Run: python examples/price_comparison.py  (needs SCRAPEUNBLOCKER_KEY)
"""

from collections import defaultdict

from udemy_scraper import UdemyScraper

COURSES = [
    "https://www.udemy.com/course/complete-python-bootcamp/",
    "https://www.udemy.com/course/100-days-of-code/",
]
COUNTRIES = ["us", "gb", "de", "in", "br"]

udemy = UdemyScraper()
by_course = defaultdict(list)
for quote in udemy.prices(COURSES, countries=COUNTRIES):
    by_course[quote.course_id].append(quote)

for course_id, quotes in by_course.items():
    print(f"course {course_id}")
    for q in quotes:
        deal = f"  ({q.discount_percent}% off {q.list_price:,.2f})" if q.on_sale else ""
        print(f"  {q.country.upper()}  {q.price:>10,.2f} {q.currency}{deal}")
