"""Constituency context fetcher — provides development indicators for context."""

from __future__ import annotations

from ..models.schemas import MPProfile, ConstituencyContext
from ..utils.logger import get_logger

log = get_logger(__name__)

# Static Census 2011 data for Delhi constituencies
# Source: Election Commission delimitation + Census 2011 district data
_DELHI_CONSTITUENCIES: dict[str, ConstituencyContext] = {
    "new delhi": ConstituencyContext(
        population=2_290_000,
        literacy_rate=88.0,
        urban_percentage=100.0,
        district="New Delhi",
    ),
    "east delhi": ConstituencyContext(
        population=2_500_000,
        literacy_rate=85.0,
        urban_percentage=100.0,
        district="East Delhi",
    ),
    "west delhi": ConstituencyContext(
        population=2_800_000,
        literacy_rate=83.0,
        urban_percentage=100.0,
        district="West Delhi",
    ),
    "north east delhi": ConstituencyContext(
        population=2_600_000,
        literacy_rate=82.0,
        urban_percentage=100.0,
        district="North East Delhi",
    ),
    "north west delhi": ConstituencyContext(
        population=2_700_000,
        literacy_rate=84.0,
        urban_percentage=100.0,
        district="North West Delhi",
    ),
    "south delhi": ConstituencyContext(
        population=2_400_000,
        literacy_rate=89.0,
        urban_percentage=100.0,
        district="South Delhi",
    ),
    "chandni chowk": ConstituencyContext(
        population=2_300_000,
        literacy_rate=81.0,
        urban_percentage=100.0,
        district="Central Delhi",
    ),
}


class ConstituencyFetcher:
    """Provides constituency-level development context."""

    def fetch_context(self, mp: MPProfile) -> ConstituencyContext:
        """Get constituency context for an MP. Uses static data."""
        key = mp.constituency.strip().lower()

        # Direct match
        if key in _DELHI_CONSTITUENCIES:
            return _DELHI_CONSTITUENCIES[key]

        # Fuzzy match — check if constituency name is contained
        for name, ctx in _DELHI_CONSTITUENCIES.items():
            if name in key or key in name:
                return ctx

        log.debug("No constituency context for %s (%s)", mp.constituency, mp.state)
        return ConstituencyContext()
