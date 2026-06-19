import pandas as pd

DAY_TYPES = ["All days", "Weekday", "Weekend"]


def slice_by_day_type(
    df: pd.DataFrame,
    day_type: str,
    keys: list[str],
    weight_col: str,
    weighted_cols: list[str],
    first_cols: list[str],
) -> pd.DataFrame:
    """Resolve a weekday/weekend-split frame to the chosen day-type view.

    keys          columns that define the rolled-up grain (e.g. h3_index, hour_paris)
    weight_col    per-row observation count used to weight the rollup
    weighted_cols rate/average columns recombined as a weighted mean over weight_col
    first_cols    columns constant within `keys` (carried through unchanged)
    """
    if day_type == "Weekday":
        return df[~df["is_weekend"]].copy()
    if day_type == "Weekend":
        return df[df["is_weekend"]].copy()

    tmp = df.copy()
    for col in weighted_cols:
        tmp[col] = tmp[col] * tmp[weight_col]
    agg = {col: "sum" for col in weighted_cols}
    agg[weight_col] = "sum"
    agg.update({col: "first" for col in first_cols})
    out = tmp.groupby(keys, as_index=False).agg(agg)
    for col in weighted_cols:
        out[col] = out[col] / out[weight_col]
    return out
