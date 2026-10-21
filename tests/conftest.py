from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import pytest

from occasio.core.knowledge import Knowledge, load_knowledge
from occasio.core.models import EventProfile

TODAY = date(2026, 1, 5)  # a Monday; fixed so every date-based rule is reproducible

ProfileFactory = Callable[..., EventProfile]


@pytest.fixture
def today() -> date:
    return TODAY


@pytest.fixture
def knowledge() -> Knowledge:
    return load_knowledge()


@pytest.fixture
def make_profile() -> ProfileFactory:
    def factory(**overrides: Any) -> EventProfile:
        weeks = overrides.pop("weeks_out", None)
        data: dict[str, Any] = {
            "event_type": "birthday",
            "event_date": TODAY + timedelta(weeks=30),
            "guest_count": 40,
            "budget_minor": 200_000_00,
            "currency": "INR",
            "location": "Kochi, Kerala",
            "setting": "indoor",
        }
        if weeks is not None:
            data["event_date"] = TODAY + timedelta(weeks=weeks)
        data.update(overrides)
        return EventProfile.model_validate(data)

    return factory
