"""Top-rated English Python courses for beginners, two result pages, saved as CSV.

Run: python examples/search_to_csv.py  (needs SCRAPEUNBLOCKER_KEY)
"""

from udemy_scraper import SearchQuery, UdemyScraper, to_csv_file

udemy = UdemyScraper()  # prices as seen from the US
query = SearchQuery(
    "python",
    sort="rating",
    languages=("en",),
    levels=("beginner",),
    min_rating=4.5,
)
courses = udemy.search_courses(query, pages=2)
to_csv_file(courses, "python-courses.csv")

print(f"{len(courses)} courses saved to python-courses.csv")
for course in courses[:10]:
    rating, ratings, price = course.rating or 0, course.num_ratings or 0, course.price_text or "-"
    print(f"{rating:.1f}  {ratings:>7,}  {price:>8}  {course.title}")
