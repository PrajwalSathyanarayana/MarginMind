"""
metrics_logger.py — append-only evaluation metrics log.

Each call to log_evaluation() writes one JSON record to metrics_log.json.
Records are read by generate_poster_graphs.py to produce poster visuals.
"""

import json
from datetime import datetime
from pathlib import Path

METRICS_FILE = Path(__file__).parent / "metrics_log.json"


def log_evaluation(record: dict) -> None:
    """Append one grading session record to metrics_log.json."""
    records: list = []

    if METRICS_FILE.exists():
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except (json.JSONDecodeError, IOError):
            records = []

    record["logged_at"] = datetime.utcnow().isoformat()
    records.append(record)

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
