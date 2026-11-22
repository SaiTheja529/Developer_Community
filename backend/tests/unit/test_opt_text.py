"""Regression: OptText must accept an explicit null (it used to raise TypeError -> HTTP 500)."""

import pytest
from pydantic import BaseModel, ValidationError

from app.common.validation import OptText


class Body(BaseModel):
    note: OptText(5) = None


def test_explicit_null_is_accepted():
    assert Body.model_validate({"note": None}).note is None


def test_blank_becomes_none():
    assert Body.model_validate({"note": "   "}).note is None


def test_max_length_still_enforced():
    with pytest.raises(ValidationError):
        Body.model_validate({"note": "too long"})
