"""Unit tests for the rules the brief grades on, plus the anti-hallucination guards."""

import math
from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from costwatch.explain import validate_explanation
from costwatch.metrics import weekly_route_costs
from costwatch.notes import INCREASE, NO_INCREASE, classify_effect_by_rules, load_notes, parse_note
from costwatch.retrieval import note_index
from costwatch.verdict import JUSTIFIED, UNEXPLAINED, Assessment, assess, flag_triggers


def shipments(rows):
    df = pd.DataFrame(rows, columns=["route", "route_type", "shipment_date", "q", "d", "cost"])
    df["shipment_date"] = pd.to_datetime(df["shipment_date"])
    df["shipment_id"] = range(len(df))
    df["freight_cost_inr"] = df["cost"]
    df["tonne_km"] = df["q"] * df["d"]
    df["week_of"] = (df["shipment_date"] - pd.to_timedelta(df["shipment_date"].dt.weekday, unit="D")).dt.date
    return df


# ---------- metrics ----------

def test_week_runs_monday_to_sunday():
    df = shipments([("A-B", "Short", "2024-01-07", 1, 1, 1),   # Sunday -> week of Mon 2024-01-01
                    ("A-B", "Short", "2024-01-08", 1, 1, 1)])  # Monday -> new week
    assert list(weekly_route_costs(df)["week_of"]) == [date(2024, 1, 1), date(2024, 1, 8)]


def test_cost_is_total_cost_over_total_tonne_km():
    df = shipments([("A-B", "Short", "2024-01-01", 10, 100, 1000),   # 1.0 per tkm
                    ("A-B", "Short", "2024-01-02", 10, 300, 9000)])  # 3.0 per tkm
    assert weekly_route_costs(df)["cost_per_tonne_km"].iloc[0] == pytest.approx(10000 / 4000)


def test_own_history_uses_only_prior_weeks_and_at_most_eight():
    rows = [("A-B", "Short", str(date(2024, 1, 1) + pd.Timedelta(weeks=i)), 1, 1, i + 1) for i in range(10)]
    w = weekly_route_costs(shipments(rows))
    assert math.isnan(w["own_history_avg"].iloc[0])           # first week: nothing before it
    assert w["own_history_avg"].iloc[3] == pytest.approx(2.0)  # weeks 1..3 -> mean(1,2,3)
    assert w["own_history_avg"].iloc[9] == pytest.approx(sum(range(2, 10)) / 8)  # weeks 2..9 only
    assert list(w["own_history_weeks"])[:3] == [0, 1, 2]


def test_no_look_ahead():
    base = [("A-B", "Short", "2024-01-01", 1, 1, 1), ("A-B", "Short", "2024-01-08", 1, 1, 2)]
    a = weekly_route_costs(shipments(base))
    b = weekly_route_costs(shipments(base + [("A-B", "Short", "2024-01-15", 1, 1, 999)]))
    assert a["own_history_avg"].iloc[1] == b["own_history_avg"].iloc[1]


def test_peer_average_excludes_self_and_other_route_types():
    df = shipments([("A-B", "Short", "2024-01-01", 1, 1, 1), ("C-D", "Short", "2024-01-01", 1, 1, 2),
                    ("E-F", "Short", "2024-01-01", 1, 1, 6), ("G-H", "Long", "2024-01-01", 1, 1, 100)])
    peer = weekly_route_costs(df).set_index("route")["peer_avg"]
    assert peer["A-B"] == pytest.approx(4.0)  # mean(2, 6); not itself, not the Long route
    assert math.isnan(peer["G-H"])             # no other Long route


# ---------- flag rule ----------

def test_flag_needs_a_rise():
    assert flag_triggers(12.0, 0.0) == ["own_history"]
    assert flag_triggers(1.0, 25.0) == ["similar_routes"]
    assert flag_triggers(-0.5, 40.0) == []       # far above peers but falling: not "rising"
    assert flag_triggers(float("nan"), 50.0) == []


# ---------- note reading ----------

@pytest.mark.parametrize("text,effect", [
    ("Costs were not significantly affected.", NO_INCREASE),
    ("Compliance costs were absorbed by transporters without a rate change.", NO_INCREASE),
    ("The route returned to normal conditions after repairs.", NO_INCREASE),
    ("Improved road conditions after resurfacing.", NO_INCREASE),
    ("A temporary surcharge was applied.", INCREASE),
    ("Flooding forced longer detours and higher trip costs.", INCREASE),
])
def test_rule_reader(text, effect):
    assert classify_effect_by_rules(text)[0] == effect


def test_note_windows():
    flood = parse_note("X", "2025-02-24", "A-B", "Flooding from Feb 24 to Mar 8, higher trip costs.")
    assert (flood.window_start, flood.window_end) == (date(2025, 2, 24), date(2025, 3, 8))
    assert flood.covers_week(date(2025, 3, 3)) and not flood.covers_week(date(2025, 3, 10))
    diesel = parse_note("Y", "2025-05-07", "All Routes", "Diesel prices rose starting this week by roughly 5-7%.")
    assert diesel.window_start == date(2025, 5, 5) and diesel.magnitude_pct == (5.0, 7.0)


def test_llm_disagreement_blocks_justification():
    note = parse_note("X", "2025-01-20", "A-B", "A festival surcharge was applied.")
    assert note.raises_cost
    assert not replace(note, llm_effect=NO_INCREASE).raises_cost


# ---------- verdicts on the real notes ----------

def row(route, week, own, peer):
    return pd.Series({"route": route, "route_type": "Medium", "week_of": week, "cost_per_tonne_km": 3.0,
                      "own_history_avg": 2.5, "own_history_weeks": 8, "peer_avg": 2.5,
                      "vs_own_history_pct": own, "vs_similar_pct": peer})


@pytest.fixture(scope="module")
def index():
    return note_index(load_notes())


def test_note_cited_only_inside_its_window(index):
    assert assess(row("Chennai-Bangalore", date(2025, 3, 3), 25, 30), index).note.note_id == "N001"
    later = assess(row("Chennai-Bangalore", date(2025, 3, 10), 25, 30), index)
    assert later.verdict == UNEXPLAINED and later.note is None


def test_note_for_other_route_is_never_cited(index):
    a = assess(row("Mumbai-Pune", date(2025, 1, 20), 25, 30), index)  # N002 is Ahmedabad-Mumbai
    assert a.verdict == UNEXPLAINED


def test_no_effect_notes_are_never_cited(index):
    a = assess(row("Mumbai-Pune", date(2025, 10, 27), 5, 28), index)  # N010 same week, "no rate change"
    assert a.verdict == UNEXPLAINED and [n.note_id for n, _ in a.rejected] == ["N010"]


def test_all_routes_note_cannot_explain_gap_vs_peers(index):
    assert assess(row("Mumbai-Delhi", date(2025, 5, 12), 11, 5), index).note.note_id == "N003"
    assert assess(row("Mumbai-Pune", date(2025, 5, 12), 6, 25), index).verdict == UNEXPLAINED


def test_rise_bigger_than_note_says_is_not_explained(index):
    assert assess(row("Mumbai-Delhi", date(2025, 5, 12), 30, 5), index).verdict == UNEXPLAINED


def test_moving_a_note_moves_the_verdict():
    notes = [replace(n, applies_to="Delhi-Jaipur") if n.note_id == "N002" else n for n in load_notes()]
    idx = note_index(notes)
    assert assess(row("Ahmedabad-Mumbai", date(2025, 1, 20), 29, 22), idx).verdict == UNEXPLAINED
    assert assess(row("Delhi-Jaipur", date(2025, 1, 20), 29, 22), idx).verdict == JUSTIFIED


# ---------- explanation validator ----------

@pytest.fixture
def justified(index):
    return assess(row("Chennai-Bangalore", date(2025, 3, 3), 25, 30), index)


ROUTES = ["Chennai-Bangalore", "Mumbai-Pune"]


def test_validator_accepts_faithful_paraphrase(justified: Assessment):
    text = "Flooding on the Chennai-Bangalore highway from February 24 to March 8 forced detours, raising trip costs."
    assert validate_explanation(text, justified, ROUTES) is None


@pytest.mark.parametrize("text", [
    "Flooding raised costs, as did N003.",                      # other note id
    "Flooding raised costs by 40% on this route.",              # number not in the note
    "Flooding raised costs, similar to Mumbai-Pune.",           # other route
    "This rise is unexplained.",                                # contradicts verdict
    "",
])
def test_validator_rejects_ungrounded_text(justified: Assessment, text):
    assert validate_explanation(text, justified, ROUTES) is not None
