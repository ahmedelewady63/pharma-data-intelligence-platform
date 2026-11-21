import json
import re
from pathlib import Path

import pyarrow as pa
import yaml

from common.interfaces import MatchStatus, QualityStatus
from ingestion.egypt import EGYPT_SCHEMA
from ingestion.faers import DEMO_SCHEMA, DRUG_SCHEMA, OUTC_SCHEMA, REAC_SCHEMA
from ingestion.nadac import NADAC_SCHEMA
from ingestion.ndc import PACKAGE_SCHEMA, PRODUCT_SCHEMA
from ingestion.rxnorm import CONCEPT_SCHEMA, NDC_SCHEMA, RELATION_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
TYPE_MAP = {
    "varchar": pa.string(),
    "integer": pa.int32(),
    "double": pa.float64(),
    "date": pa.date32(),
}
STAGING_SCHEMAS = {
    "stg_faers_demo": DEMO_SCHEMA,
    "stg_faers_drug": DRUG_SCHEMA,
    "stg_faers_reac": REAC_SCHEMA,
    "stg_faers_outc": OUTC_SCHEMA,
    "stg_rxnorm_concept": CONCEPT_SCHEMA,
    "stg_rxnorm_ndc": NDC_SCHEMA,
    "stg_rxnorm_relation": RELATION_SCHEMA,
    "stg_ndc_product": PRODUCT_SCHEMA,
    "stg_ndc_package": PACKAGE_SCHEMA,
    "stg_nadac": NADAC_SCHEMA,
    "stg_eg_product": EGYPT_SCHEMA,
}


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
            match = re.search(r"fk -> ([a-z_]+)", str(col))
            if match:
                assert match.group(1) in model, f"{table}: {col} points to unknown table"


def test_model_has_expected_shape():
    model = load_yaml("contracts.yaml")["model"]
    assert sum(name.startswith("dim_") for name in model) == 16
    assert sum(name.startswith("fact_") for name in model) == 5


def test_event_schema_is_consistent():
    schema = json.loads((ROOT / "contracts" / "event_schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]) <= set(schema["properties"])


def test_every_ingestion_schema_matches_yaml_contract():
    contracts = load_yaml("contracts.yaml")
    contract_tables = {
        **contracts["staging_faers"],
        **contracts["staging_reference"],
    }
    assert set(STAGING_SCHEMAS) == set(contract_tables)

    for table, schema in STAGING_SCHEMAS.items():
        fields = contract_tables[table]["columns"]
        expected = pa.schema(
            [
                pa.field(
                    field["name"],
                    TYPE_MAP[field["type"]],
                    nullable=field["nullable"],
                )
                for field in fields
            ]
        )
        assert schema.equals(expected, check_metadata=False), table
