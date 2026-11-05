import json

import pytest
from conftest import FakeClient, card, dump, pricing_answer, search_html

from udemy_scraper import UdemyScraper, cli


@pytest.fixture
def fake_scraper(monkeypatch):
    """Make the CLI build scrapers on a fake client; returns the clients it made."""
    clients = []

    def install(routes):
        def build(args, country="us"):
            client = FakeClient(routes)
            clients.append(client)
            return UdemyScraper(client=client, country=country, sleep=lambda s: None)

        monkeypatch.setattr(cli, "_scraper", build)
        return clients

    return install


def test_parser_reads_search_filters():
    args = cli.build_parser().parse_args(
        [
            "search",
            "python",
            "data science",
            "--sort",
            "rating",
            "--lang",
            "en,es",
            "--level",
            "beginner",
            "--min-rating",
            "4.5",
            "--price",
            "paid",
            "--duration",
            "1-3h",
            "--feature",
            "coding-exercises",
            "--pages",
            "3",
        ]
    )
    query = cli._query(args, args.queries[1])
    assert query.query == "data science" and query.languages == ("en", "es")
    assert query.min_rating == 4.5 and query.levels == ("beginner",) and args.pages == 3


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "python", "--min-rating", "4.2"],
        ["search", "python", "--level", "pro"],
        ["reviews", "567828", "--stars", "6"],
        ["instructor", "x", "--no-courses", "--courses-only"],
    ],
)
def test_parser_refuses_bad_options(argv):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(argv)


def test_format_follows_the_output_extension():
    parse = cli.build_parser().parse_args
    assert cli._format(parse(["prices", "1", "-o", "out.csv"])) == "csv"
    assert cli._format(parse(["prices", "1", "-o", "out.jsonl"])) == "jsonl"
    assert cli._format(parse(["prices", "1"])) == "table"
    assert cli._format(parse(["course", "1"])) == "json"
    assert cli._format(parse(["course", "1", "-f", "csv"])) == "csv"


def test_search_command(fake_scraper, capsys):
    clients = fake_scraper(
        {"/courses/search/": search_html(card(1, "a", "A"), card(2, "b", "B"), pages=())}
    )
    assert cli.main(["search", "python", "--country", "gb", "-f", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [c["course_id"] for c in out] == [1, 2]
    assert clients[0].calls[0][1]["proxy_country"] == "gb"


def test_prices_command_with_csv_file(fake_scraper, tmp_path, capsys):
    fake_scraper({"pricing": dump(pricing_answer({1: (9.99, 19.99)}))})
    refs = tmp_path / "courses.txt"
    refs.write_text("# my courses\n1\n", encoding="utf-8")
    out = tmp_path / "prices.csv"
    argv = ["prices", "--from-file", str(refs), "--countries", "us,de", "-o", str(out)]
    assert cli.main(argv) == 0
    text = out.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("course_id,country,currency,price")
    assert len(text.splitlines()) == 3


def test_bad_input_exits_with_usage(fake_scraper):
    fake_scraper({})
    with pytest.raises(SystemExit) as exc:
        cli.main(["prices", "1", "--countries", "usa"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit):
        cli.main(["prices"])


def test_sdk_errors_are_reported(fake_scraper, capsys):
    fake_scraper({"pricing": RuntimeError("Invalid API key")})
    assert cli.main(["prices", "1"]) == 1
    assert "Invalid API key" in capsys.readouterr().err
