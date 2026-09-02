"""Deterministic resolution of MP profile photo URLs.

Photos are public-domain images served by the Sansad member portal and
mirrored locally under the dashboard's public assets as
``{sansad_member_id}.jpg`` (see ``dashboard/public/mp-photos``).

Resolution order (no network calls, fully reproducible):

1. Local mirror file matching ``sansad_member_id`` → root-relative URL.
   The dashboard prefixes its configured base path at render time, so a
   plain ``/mp-photos/...`` path stays safe under GitHub Pages subpaths.
2. Any remote photo URL already present on the record (e.g. MyNeta).
3. ``None`` — the UI falls back to an initial-letter avatar.
"""

from __future__ import annotations

import os

from ..config import settings


def local_photo_path(member_id: int | None, house: str | None = None) -> str | None:
    """Return the filesystem path of the local photo for a member ID, if present.

    Rajya Sabha portraits live in the ``rs/`` subdirectory keyed by the RS
    member number; Lok Sabha portraits sit at the mirror root keyed by the
    LS member number. Member IDs are not unique across the two houses, so
    the house disambiguates the file.
    """
    if not member_id:
        return None
    subdir = "rs" if house == "rajya_sabha" else ""
    path = os.path.join(settings.mp_photos_dir, subdir, f"{int(member_id)}.jpg")
    return path if os.path.isfile(path) else None


def resolve_photo_url(
    current_url: str | None, member_id: int | None, house: str | None = None
) -> str | None:
    """Pick the best photo URL for an MP.

    Prefers the locally mirrored Sansad photo (reliable, no third-party
    hotlinking); falls back to whatever remote URL the record already has.
    A root-relative local path from an earlier pass (e.g. ``/mp-photos/rs/...``)
    is kept as-is.
    """
    if member_id and local_photo_path(member_id, house):
        subdir = "rs/" if house == "rajya_sabha" else ""
        return f"{settings.mp_photos_url_prefix.rstrip('/')}/{subdir}{int(member_id)}.jpg"
    if current_url and (current_url.startswith("http") or current_url.startswith("/")):
        return current_url
    return None
