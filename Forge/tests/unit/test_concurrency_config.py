from __future__ import annotations

import pytest

from app.api.tasks import _parse_concurrency_limit


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, 3),
        ("", 3),
        ("   ", 3),
        ("3", 3),
        ("12", 12),
        ("invalid", 3),
        ("0", 3),
        ("-1", 3),
    ],
)
def test_parse_concurrency_limit_uses_safe_default_for_invalid_values(
    raw_value: str | None, expected: int
) -> None:
    assert _parse_concurrency_limit(raw_value) == expected


def test_parse_concurrency_limit_clamps_oversized_worker_count() -> None:
    assert _parse_concurrency_limit("100000") == 32


@pytest.mark.parametrize(
    ("default", "maximum"),
    [(0, 3), (-1, 3), (3, 0), (4, 3), (True, 3), (3, False)],
)
def test_parse_concurrency_limit_rejects_invalid_internal_bounds(
    default: int, maximum: int
) -> None:
    with pytest.raises(ValueError, match="positive ordered integers"):
        _parse_concurrency_limit("3", default=default, maximum=maximum)  # type: ignore[arg-type]
