import json
import re
from pathlib import Path

import yaml

from common.interfaces import MatchStatus, QualityStatus

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(name):
    return yaml.safe_load((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def test_enums_match_code():
    enums = load_yaml("enums.yaml")
    assert enums["match_status"] == [s.value for s in MatchStatus]
    assert enums["quality_status"] == [s.value for s in QualityStatus]


def test_model_foreign_keys_point_to_existing_tables():
    model = load_yaml("contracts.yaml")["model"]
    for table, spec in model.items():
        for col in spec["columns"]:
            m = re.search(r"fk -> ([a-z_]+)", str(col))
            if m:
                assert m.group(1) in model, f"{table}: {col} points to unknown table"


def test_model_has_expected_shape():
    model = load_yaml("contracts.yaml")["model"]
    assert sum(k.startswith("dim_") for k in model) == 16
    assert sum(k.startswith("fact_") for k in model) == 5


def test_event_schema_is_consistent():
    schema = json.loads((ROOT / "contracts" / "event_schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(schema["properties"])
