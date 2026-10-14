"""Weekly cost per tonne-km per route, plus the two graded baselines.

Definitions (from the brief, verified against the sample output rows):
  * week_of            = Monday of the Monday-Sunday week containing shipment_date
  * cost_per_tonne_km  = sum(freight_cost) / sum(quantity_tonnes * distance_km) for the route-week
  * own_history_avg    = mean of the route's weekly cost over the HISTORY_WEEKS calendar weeks
                         strictly before this week (fewer if fewer exist; NaN for the first week)
  * peer_avg           = mean weekly cost, same week, over the *other* routes with the same route_type
"""

from datetime import timedelta

import pandas as pd

from . import config


def load_shipments(path=config.SHIPMENTS_CSV) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["shipment_date"])
    for col in ("origin", "destination", "route_type"):
        df[col] = df[col].str.strip()
    df["route"] = df["origin"] + "-" + df["destination"]
    df["week_of"] = (df["shipment_date"] - pd.to_timedelta(df["shipment_date"].dt.weekday, unit="D")).dt.date
    df["tonne_km"] = df["quantity_tonnes"] * df["distance_km"]
    return df


def weekly_route_costs(shipments: pd.DataFrame) -> pd.DataFrame:
    weekly = (
        shipments.groupby(["route", "route_type", "week_of"], as_index=False)
        .agg(shipments=("shipment_id", "size"),
             total_cost=("freight_cost_inr", "sum"),
             tonne_km=("tonne_km", "sum"))
        .sort_values(["route", "route_type", "week_of"], ignore_index=True)
    )
    weekly["cost_per_tonne_km"] = weekly["total_cost"] / weekly["tonne_km"]

    _add_own_history(weekly)
    _add_peer_average(weekly)

    weekly["vs_own_history_pct"] = (weekly["cost_per_tonne_km"] / weekly["own_history_avg"] - 1) * 100
    weekly["vs_similar_pct"] = (weekly["cost_per_tonne_km"] / weekly["peer_avg"] - 1) * 100
    return weekly


def _add_own_history(weekly: pd.DataFrame) -> None:
    """Trailing average over calendar weeks [w - 8, w - 1]; never looks at week w or later."""
    cost = {(r, t, w): c for r, t, w, c in
            weekly[["route", "route_type", "week_of", "cost_per_tonne_km"]].itertuples(index=False)}
    averages, counts = [], []
    for route, route_type, week in weekly[["route", "route_type", "week_of"]].itertuples(index=False):
        prior = [cost[(route, route_type, week - timedelta(weeks=k))]
                 for k in range(1, config.HISTORY_WEEKS + 1)
                 if (route, route_type, week - timedelta(weeks=k)) in cost]
        averages.append(sum(prior) / len(prior) if prior else float("nan"))
        counts.append(len(prior))
    weekly["own_history_avg"] = averages
    weekly["own_history_weeks"] = counts


def _add_peer_average(weekly: pd.DataFrame) -> None:
    """Mean of the other same-type routes' weekly cost in the same week (route excluded)."""
    by_type_week = weekly.groupby(["route_type", "week_of"])["cost_per_tonne_km"]
    total = by_type_week.transform("sum")
    count = by_type_week.transform("count")
    peers = count - 1
    weekly["peer_routes"] = peers
    weekly["peer_avg"] = ((total - weekly["cost_per_tonne_km"]) / peers).where(peers > 0)
