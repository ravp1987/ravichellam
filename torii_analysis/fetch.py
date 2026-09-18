"""Pull raw data from Torii and cache it as JSON under data/raw/.

Field discovery: Torii's schema (exact field names for spend, licenses,
seats, etc.) can vary by account/plan, so instead of hardcoding guesses we
call the resource's /fields endpoint when available and select fields by
keyword. If /fields isn't available for a resource, we fall back to
requesting no `fields` param, which Torii returns as a sensible default set.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from client import ToriiClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("torii.fetch")

DATA_DIR = Path(__file__).parent / "data" / "raw"

SPEND_KEYWORDS = ("spend", "cost", "price", "amount", "annual", "expense")
LICENSE_KEYWORDS = ("license", "seat", "plan")
USAGE_KEYWORDS = ("active", "lastActivity", "usage", "login")
CORE_APP_FIELDS = ("id", "name", "category", "status", "state", "owner")


def _select_fields(all_fields: list[str] | None, keyword_groups: tuple[tuple[str, ...], ...]) -> list[str]:
    if not all_fields:
        return []
    selected: list[str] = []
    lowered = {f: f.lower() for f in all_fields}
    for f, fl in lowered.items():
        if any(any(kw in fl for kw in group) for group in keyword_groups):
            selected.append(f)
    return selected


def fetch_apps(client: ToriiClient) -> list[dict]:
    all_fields = client.fields("apps")
    fields = list(CORE_APP_FIELDS)
    fields += _select_fields(all_fields, (SPEND_KEYWORDS, LICENSE_KEYWORDS, USAGE_KEYWORDS))
    # de-dupe while preserving order, and only keep fields that actually exist
    if all_fields:
        valid = set(all_fields) | set(CORE_APP_FIELDS)
        fields = [f for i, f in enumerate(fields) if f in valid and f not in fields[:i]]
        params = {"fields": ",".join(fields)}
    else:
        params = None
    apps = list(client.get_all_pages("apps", params=params))
    log.info("Fetched %d apps (fields=%s)", len(apps), params.get("fields") if params else "default")
    return apps


def fetch_users(client: ToriiClient) -> list[dict]:
    users = list(client.get_all_pages("users"))
    log.info("Fetched %d users", len(users))
    return users


def fetch_contracts(client: ToriiClient) -> list[dict]:
    contracts = list(client.get_all_pages("contracts"))
    log.info("Fetched %d contracts", len(contracts))
    return contracts


def fetch_app_users(client: ToriiClient, app_id) -> list[dict]:
    """Per-app user/license assignments, used for utilization analysis."""
    users = list(client.get_all_pages(f"apps/{app_id}/users"))
    return users


def save(name: str, data) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def fetch_all(include_per_app_users: bool = True) -> dict[str, Path]:
    client = ToriiClient()
    out: dict[str, Path] = {}

    org = client.org()
    if org is not None:
        out["org"] = save("org", org)

    apps = fetch_apps(client)
    out["apps"] = save("apps", apps)

    users = fetch_users(client)
    out["users"] = save("users", users)

    contracts = fetch_contracts(client)
    out["contracts"] = save("contracts", contracts)

    if include_per_app_users:
        app_users: dict[str, list[dict]] = {}
        for app in apps:
            app_id = app.get("id")
            if app_id is None:
                continue
            try:
                app_users[str(app_id)] = fetch_app_users(client, app_id)
            except Exception as exc:  # keep going; per-app endpoint may not exist for every app type
                log.warning("Could not fetch users for app %s: %s", app_id, exc)
        out["app_users"] = save("app_users", app_users)

    return out


if __name__ == "__main__":
    paths = fetch_all()
    for name, path in paths.items():
        print(f"{name}: {path}")
