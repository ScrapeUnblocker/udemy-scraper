"""Errors raised by the scraper."""

from __future__ import annotations


class UdemyError(Exception):
    """Base class for scraper errors."""


class NotFoundError(UdemyError):
    """Udemy has no course or instructor with that id or slug (HTTP 404)."""


class ParseError(UdemyError):
    """A response was not the Udemy data the scraper expected."""


class InputError(UdemyError, ValueError):
    """A course, instructor, search URL, sort order or filter could not be used."""
