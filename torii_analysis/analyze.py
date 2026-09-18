"""Turn raw Torii JSON exports into analysis tables.

Field names in Torii's API vary a bit by account/plan (e.g. spend may come
back as `annualSpend`, `spend`, or `totalCost`). `_first` picks whichever of
a set of candidate keys is present on a record instead of hardcoding one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).parent / "data" / "raw"

SPEND_KEYS = ("annualSpend", "totalSpend", "spend", "totalCost", "cost", "annualCost", "amount")
LICENSE_TOTAL_KEYS = ("licenses", "totalLicenses", "seats", "totalSeats", "licenseCount")
LICENSE_ACTIVE_KEYS = ("activeLicenses", "activeUsers", "activeSeats", "usedLicenses")
CATEGORY_KEYS = ("category", "appCategory", "type")
STATE_KEYS = ("state", "status")
NAME_KEYS = ("name", "appName")
RENEWAL_KEYS = ("renewalDate", "endDate", "expirationDate")


def _first(record: dict, keys: tuple[str, ...], default=None):
    for k in keys:
        if k in record and record[k] not in (None, ""):
            return record[k]
    return default


def _load(name: str) -> Any:
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run fetch.py first")
    return json.loads(path.read_text())


def load_apps_df() -> pd.DataFrame:
    apps = _load("apps")
    rows = []
    for a in apps:
        rows.append(
            {
                "id": a.get("id"),
                "name": _first(a, NAME_KEYS, "Unknown"),
                "category": _first(a, CATEGORY_KEYS, "Uncategorized"),
                "state": _first(a, STATE_KEYS, "unknown"),
                "spend": _first(a, SPEND_KEYS, 0) or 0,
                "licenses_total": _first(a, LICENSE_TOTAL_KEYS, None),
                "licenses_active": _first(a, LICENSE_ACTIVE_KEYS, None),
                "renewal_date": _first(a, RENEWAL_KEYS, None),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["spend"] = pd.to_numeric(df["spend"], errors="coerce").fillna(0)
    return df


def load_users_df() -> pd.DataFrame:
    users = _load("users")
    return pd.DataFrame(users)


def spend_analysis(apps_df: pd.DataFrame) -> dict:
    if apps_df.empty:
        return {"total_spend": 0, "by_app": pd.DataFrame(), "by_category": pd.DataFrame()}
    total = float(apps_df["spend"].sum())
    by_app = apps_df[["name", "category", "spend"]].sort_values("spend", ascending=False)
    by_app = by_app[by_app["spend"] > 0]
    by_category = (
        apps_df.groupby("category", as_index=False)["spend"].sum().sort_values("spend", ascending=False)
    )
    return {"total_spend": total, "by_app": by_app, "by_category": by_category}


def license_utilization(apps_df: pd.DataFrame) -> pd.DataFrame:
    df = apps_df.dropna(subset=["licenses_total"]).copy()
    if df.empty:
        return df
    df["licenses_total"] = pd.to_numeric(df["licenses_total"], errors="coerce")
    df["licenses_active"] = pd.to_numeric(df["licenses_active"], errors="coerce")
    df = df.dropna(subset=["licenses_total"])
    df = df[df["licenses_total"] > 0]
    df["licenses_active"] = df["licenses_active"].fillna(0)
    df["unused_licenses"] = (df["licenses_total"] - df["licenses_active"]).clip(lower=0)
    df["utilization_pct"] = (df["licenses_active"] / df["licenses_total"] * 100).round(1)
    df["cost_per_license"] = (df["spend"] / df["licenses_total"]).where(df["licenses_total"] > 0)
    df["wasted_spend"] = (df["unused_licenses"] * df["cost_per_license"]).fillna(0)
    return df.sort_values("wasted_spend", ascending=False)


def shadow_it(apps_df: pd.DataFrame) -> pd.DataFrame:
    """Apps discovered (e.g. via SSO/expense logs) but not yet reviewed/managed."""
    if apps_df.empty:
        return apps_df
    unmanaged_states = {"discovered", "not_reviewed", "unmanaged", "not managed"}
    mask = apps_df["state"].astype(str).str.lower().isin(unmanaged_states)
    return apps_df[mask].sort_values("spend", ascending=False)


def inventory_summary(apps_df: pd.DataFrame) -> dict:
    if apps_df.empty:
        return {"total_apps": 0, "by_state": pd.DataFrame(), "by_category": pd.DataFrame()}
    return {
        "total_apps": len(apps_df),
        "by_state": apps_df.groupby("state", as_index=False).size().sort_values("size", ascending=False),
        "by_category": apps_df.groupby("category", as_index=False).size().sort_values("size", ascending=False),
    }


def run_all() -> dict:
    apps_df = load_apps_df()
    return {
        "apps_df": apps_df,
        "spend": spend_analysis(apps_df),
        "utilization": license_utilization(apps_df),
        "shadow_it": shadow_it(apps_df),
        "inventory": inventory_summary(apps_df),
    }


if __name__ == "__main__":
    results = run_all()
    print("Total spend:", results["spend"]["total_spend"])
    print("Apps flagged as unmanaged/shadow IT:", len(results["shadow_it"]))
    print("Apps with license data:", len(results["utilization"]))
