"""A course's rating breakdown plus its latest critical reviews (1 and 2 stars, with text).

Run: python examples/review_digest.py [course id, slug or URL]  (needs SCRAPEUNBLOCKER_KEY)
"""

import sys

from udemy_scraper import UdemyScraper

ref = sys.argv[1] if len(sys.argv) > 1 else "complete-python-bootcamp"
udemy = UdemyScraper()

course = udemy.course(ref, extras=False)
total = sum(course.rating_distribution.values()) or 1
print(course.title)
print(f"{course.rating or 0:.2f} average from {course.num_ratings or 0:,} ratings")
for stars in ("5", "4", "3", "2", "1"):
    count = course.rating_distribution.get(stars, 0)
    print(f"  {stars} stars  {count / total:6.1%}  {'#' * round(40 * count / total)}")

for stars in (1, 2):
    print(f"\nLatest {stars}-star reviews with text:")
    for review in udemy.iter_reviews(course.course_id, stars=stars, with_text=True, limit=5):
        text = " ".join(review.content.split())
        print(f"  {review.created[:10]}  {review.rating}  {text[:110]}")
