"""All tunable settings in one place. Every threshold here is explained in README.md."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPMENTS_CSV = ROOT / "shipment_records.csv"
NOTES_CSV = ROOT / "context_notes.csv"
SAMPLE_FORMAT_CSV = ROOT / "sample_output_format_v2.csv"
OUTPUT_DIR = ROOT / "output"

# Exact column contract from sample_output_format_v2.csv.
OUTPUT_COLUMNS = [
    "route", "week_of", "cost_per_tonne_km", "vs_own_history",
    "vs_similar_routes", "flagged", "matched_note_id", "reason",
]

# --- Baselines (fixed by the brief) ---
HISTORY_WEEKS = 8  # trailing window for "vs own history", strictly before the current week

# --- Flag rule ---
# Weekly noise vs own history has sigma ~2.9% and never exceeds 8.6% in calm periods,
# so 10% is ~3.5 sigma. No route sits more than 16.6% above its peers in calm periods,
# so 20% clears each route's structural premium/discount over its peers.
OWN_HISTORY_FLAG_PCT = 10.0
PEER_FLAG_PCT = 20.0

# --- Note matching ---
# A note with no explicit end ("starting this week") is treated as live for this many
# weeks; after that the rise is inside the rolling baseline and no longer looks unusual.
OPEN_ENDED_NOTE_WEEKS = 8
# When a note quotes a size ("roughly 5-7%"), it explains a rise only up to its upper
# bound plus this tolerance (~2 sigma of weekly noise). Anything bigger is not explained.
MAGNITUDE_TOLERANCE_PCT = 5.0
# Notes this close to a week (but not covering it) are mentioned as "considered" in reasons.
NEARBY_NOTE_DAYS = 14

# --- LLM (local, open-weights, greedy decoding => deterministic) ---
LLM_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
LLM_SEED = 0
LLM_EXPLANATION_MAX_TOKENS = 90
LLM_CLASSIFY_MAX_TOKENS = 5
LLM_EXPLANATION_MAX_WORDS = 70
