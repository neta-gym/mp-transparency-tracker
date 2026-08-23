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


def local_photo_path(member_id: int | None) -> str | None:
    """Return the filesystem path of the local photo for a member ID, if present."""
    if not member_id:
        return None
    path = os.path.join(settings.mp_photos_dir, f"{int(member_id)}.jpg")
    return path if os.path.isfile(path) else None


def resolve_photo_url(current_url: str | None, member_id: int | None) -> str | None:
    """Pick the best photo URL for an MP.

    Prefers the locally mirrored Sansad photo (reliable, no third-party
    hotlinking); falls back to whatever remote URL the record already has.
    """
    if member_id and local_photo_path(member_id):
        return f"{settings.mp_photos_url_prefix.rstrip('/')}/{int(member_id)}.jpg"
    return (current_url or None) if current_url and current_url.startswith("http") else None
