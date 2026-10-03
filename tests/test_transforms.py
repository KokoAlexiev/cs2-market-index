"""Basic data-validation tests for the bronze to silver transformation.

Runs on a small built-in sample, so it needs no data file and no Spark cluster.
Checks the things the pipeline is supposed to guarantee: duplicates gone, types
cast, wear and StatTrak parsed, and the data-quality flags set correctly.
"""
import pandas as pd

from transforms import to_silver


def _bronze():
    # ts, item, price, markup_pct, buff_price, csfloat_price
    return pd.DataFrame(
        [
            ["2026-05-01T00:00:00Z", "AK-47 | Redline (Field-Tested)", "100", "5", "90", "92"],
            ["2026-05-01T00:00:00Z", "AK-47 | Redline (Field-Tested)", "100", "5", "90", "92"],  # exact duplicate
            ["2026-05-02T00:00:00Z", "StatTrak™ AWP | Asiimov (Factory New)", "500", "8", "450", "455"],
            ["2026-05-03T00:00:00Z", "Glock-18 | Water Elemental (Minimal Wear)", "40", "150", None, "35"],  # extreme markup + missing buff
        ],
        columns=["ts", "item", "price", "markup_pct", "buff_price", "csfloat_price"],
    )


def test_duplicates_removed():
    out = to_silver(_bronze())
    assert len(out) == 3  # one exact duplicate dropped from four input rows


def test_types_cast():
    out = to_silver(_bronze())
    assert out["price"].dtype.kind == "f"  # numeric, not string
    assert str(out["sale_ts"].dtype).startswith("datetime64")


def test_stattrak_flag():
    out = to_silver(_bronze())
    assert bool(out.loc[out["item"].str.contains("AWP"), "stattrak"].iloc[0]) is True
    assert bool(out.loc[out["item"].str.contains("AK-47"), "stattrak"].iloc[0]) is False


def test_wear_extracted():
    out = to_silver(_bronze())
    assert out.loc[out["item"].str.contains("AK-47"), "wear"].iloc[0] == "Field-Tested"
    assert out.loc[out["item"].str.contains("AWP"), "wear"].iloc[0] == "Factory New"


def test_dq_flags():
    out = to_silver(_bronze())
    glock = out[out["item"].str.contains("Glock")].iloc[0]
    assert bool(glock["dq_missing_buff"]) is True
    assert bool(glock["dq_missing_csfloat"]) is False
    assert bool(glock["dq_extreme_markup"]) is True  # markup 150 is above the 100 cap
    ak = out[out["item"].str.contains("AK-47")].iloc[0]
    assert bool(ak["dq_missing_buff"]) is False
    assert bool(ak["dq_extreme_markup"]) is False
