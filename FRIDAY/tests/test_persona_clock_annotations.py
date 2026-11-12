"""The persona clock annotation must resolve outside the function body."""
import datetime
from typing import get_type_hints

from friday.persona.friday import _ist_hour


def test_clock_annotation_resolves_and_ist_behavior_is_unchanged():
    assert get_type_hints(_ist_hour)["now"] == datetime.datetime | None
    assert _ist_hour(datetime.datetime(2026, 11, 12, 20, 0, tzinfo=datetime.timezone.utc)) == 1
