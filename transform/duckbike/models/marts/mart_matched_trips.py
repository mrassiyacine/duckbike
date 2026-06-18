import pandas as pd


def model(dbt, session):
    dbt.config(materialized="table")

    edges = dbt.ref("int_trip_candidates").df().sort_values("cost", kind="stable")

    used_o, used_d = set(), set()
    keep_o, keep_d = [], []
    for o, d in zip(edges["origin_id"].to_numpy(), edges["dest_id"].to_numpy()):
        if o in used_o or d in used_d:
            continue
        used_o.add(o)
        used_d.add(d)
        keep_o.append(o)
        keep_d.append(d)

    matched = pd.DataFrame(
        {
            "origin_id": pd.Series(keep_o, dtype=edges["origin_id"].dtype),
            "dest_id": pd.Series(keep_d, dtype=edges["dest_id"].dtype),
        }
    )

    m = matched.merge(edges, on=["origin_id", "dest_id"], how="left")
    trips = pd.DataFrame(
        {
            "origin_id": m["origin_id"],
            "origin_bike_id": m["origin_bike_id"],
            "dest_bike_id": m["dest_bike_id"],
            "start_time": m["start_time"],
            "end_time": m["end_time"],
            "start_lat": m["start_lat"],
            "start_lon": m["start_lon"],
            "end_lat": m["end_lat"],
            "end_lon": m["end_lon"],
            "dist_km": m["dist_km"],
            "match_type": "User Trip",
        }
    )

    sessions = dbt.ref("int_recent_sessions").df()
    pk = sessions[~sessions["sid"].isin(used_o)]
    pickups = pd.DataFrame(
        {
            "origin_id": pk["sid"].to_numpy(),
            "origin_bike_id": pk["bike_id"].to_numpy(),
            "dest_bike_id": None,
            "start_time": pk["last_seen"].to_numpy(),
            "end_time": pd.NaT,
            "start_lat": pk["last_lat"].to_numpy(),
            "start_lon": pk["last_lon"].to_numpy(),
            "end_lat": float("nan"),
            "end_lon": float("nan"),
            "dist_km": float("nan"),
            "match_type": "Operator Pickup",
        }
    )

    return pd.concat([trips, pickups], ignore_index=True)
