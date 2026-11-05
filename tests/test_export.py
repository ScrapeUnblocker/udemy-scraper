import csv
import io
import json

from conftest import COURSE, CURRICULUM

from udemy_scraper import parse_course, parse_curriculum, parse_search, render, write


def test_csv_of_search_results(search_page):
    courses = parse_search(search_page).courses
    rows = list(csv.DictReader(io.StringIO(render(courses, "csv"))))
    assert len(rows) == 3
    assert rows[0]["course_id"] == "1565838"
    assert rows[0]["badges"] == "Bestseller"
    assert rows[2]["instructors"] == "Dr. Angela Yu, Developer and Lead Instructor"


def test_curriculum_csv_has_one_row_per_item():
    text = render(parse_curriculum(CURRICULUM, 567828), "csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["title"] for r in rows][:2] == ["Course Introduction", "Auto-Welcome Message"]
    assert rows[0]["section_title"] == "Course Overview"


def test_course_csv_flattens_the_rating_distribution():
    rows = list(csv.DictReader(io.StringIO(render([parse_course(COURSE)], "csv"))))
    assert rows[0]["ratings_5_star"] == "311674"
    assert rows[0]["instructors"] == "Jose Portilla"


def test_table_and_jsonl(search_page):
    courses = parse_search(search_page).courses
    table = render(courses, "table").splitlines()
    assert table[0].split()[:3] == ["ID", "PRICE", "WAS"]
    assert "Free" in table[2]
    lines = render(courses, "jsonl").splitlines()
    assert json.loads(lines[0])["title"] == "The Complete JavaScript Course"
    assert render([], "table") == "(no results)\n"


def test_write_csv_file_with_bom(tmp_path, search_page):
    path = tmp_path / "courses.csv"
    write(parse_search(search_page).courses, "csv", str(path))
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
