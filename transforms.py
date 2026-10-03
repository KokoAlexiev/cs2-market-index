"""Bronze to silver transformation, pulled out as a tested function.

Same cleaning as databricks/bronze_to_silver.ipynb, written in pandas so the tests
can run in CI without a Spark cluster. Takes the raw sales columns and returns the
silver frame: typed columns, wear and StatTrak taken out of the item name, a
data-quality flag on every row, and exact duplicates removed.
"""
import pandas as pd

WEARS = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
_WEAR_RE = r"\((" + "|".join(WEARS) + r")\)$"


def to_silver(bronze: pd.DataFrame) -> pd.DataFrame:
    df = bronze.copy()
    df["sale_ts"] = pd.to_datetime(df["ts"], utc=True)
    df["sale_date"] = df["sale_ts"].dt.date
    for col in ["price", "markup_pct", "buff_price", "csfloat_price"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["stattrak"] = df["item"].str.contains("StatTrak", regex=False)
    df["wear"] = df["item"].str.extract(_WEAR_RE, expand=False).fillna("")
    df["dq_missing_buff"] = df["buff_price"].isna()
    df["dq_missing_csfloat"] = df["csfloat_price"].isna()
    df["dq_extreme_markup"] = (df["markup_pct"] > 100) | (df["markup_pct"] < -50)
    df = df.drop_duplicates(subset=["ts", "item", "price"]).drop(columns=["ts"])
    return df.reset_index(drop=True)
