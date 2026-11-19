from pathlib import Path

import pyarrow.parquet as pq

from dataguard.validator import validate_staging_file
from ingestion.egypt import EGYPT_SCHEMA, process_egypt
from ingestion.ndc import NDC_PACKAGE_SCHEMA, NDC_PRODUCT_SCHEMA, process_ndc


def test_egypt_7col_to_6col_contract(tmp_path: Path) -> None:
    raw = tmp_path / "egypt"
    raw.mkdir()
    sample = raw / "Egypt_Data.txt"
    sample.write_text(
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,drug_class,route,price_egp\n"
        '"Panadol Extra, 500mg",بانادول اكسترا,'
        "Paracetamol + Caffeine,GSK,Analgesic > Antipyretic,Oral,45.5\n"
        "Augmentin 1g,اوجمنتين,Amoxicillin + Clavulanate,GSK,Antibiotic,Oral,\n",
        encoding="utf-8",
    )
    staging = tmp_path / "staging"
    outputs = process_egypt(raw, staging)
    assert len(outputs) == 1
    tbl = pq.read_table(outputs[0])
    assert tbl.schema.equals(EGYPT_SCHEMA)
    assert tbl.num_rows == 2
    assert tbl["commercial_name_en"].to_pylist() == ["Panadol Extra, 500mg", "Augmentin 1g"]
    assert tbl["price_egp"].to_pylist() == [45.5, None]


def test_ndc_xls_tab_delimited_contract(tmp_path: Path) -> None:
    raw = tmp_path / "ndc"
    raw.mkdir()
    (raw / "product.xls").write_text(
        "PRODUCTID\tPRODUCTNDC\tPRODUCTTYPENAME\tPROPRIETARYNAME\tNONPROPRIETARYNAME\t"
        "DOSAGEFORMNAME\tROUTENAME\tSUBSTANCENAME\tACTIVE_NUMERATOR_STRENGTH\t"
        "ACTIVE_INGRED_UNIT\tPHARM_CLASSES\n"
        "0002-1200_1\t0002-1200\tHUMAN PRESCRIPTION DRUG\tAmyvid\tFlorbetapir F 18\t"
        "INJECTION, SOLUTION\tINTRAVENOUS\tFLORBETAPIR F-18\t51\tmCi/mL\t"
        "Radioactive Diagnostic Agent\n",
        encoding="utf-8",
    )
    (raw / "package.xls").write_text(
        "PRODUCTID\tPRODUCTNDC\tNDCPACKAGECODE\tPACKAGEDESCRIPTION\n"
        "0002-1200_1\t0002-1200\t0002-1200-01\t1 VIAL in 1 CARTON\n",
        encoding="utf-8",
    )
    staging = tmp_path / "staging"
    outputs = process_ndc(raw, staging)
    assert len(outputs) == 2
    assert pq.read_table(outputs[0]).schema.equals(NDC_PRODUCT_SCHEMA)
    assert pq.read_table(outputs[1]).schema.equals(NDC_PACKAGE_SCHEMA)


def test_dataguard_validation(tmp_path: Path) -> None:
    raw = tmp_path / "egypt"
    raw.mkdir()
    (raw / "Egypt_Data.txt").write_text(
        "commercial_name_en,commercial_name_ar,scientific_name,manufacturer,drug_class,route,price_egp\n"
        "1 2 3 (ONE TWO THREE) 20 F.C.TABS.,1 2 3,"
        "CHLORPHENIRAMINE+PARACETAMOL(ACETAMINOPHEN)+PSEUDOEPHEDRINE,"
        "HIKMA PHARMA,COLD PRODUCTS,ORAL.SOLID,10.0\n",
        encoding="utf-8",
    )
    staging = tmp_path / "staging"
    out = process_egypt(raw, staging)[0]
    res = validate_staging_file(
        out, {"primary_key": ["commercial_name_en"], "required_columns": ["commercial_name_en"]}
    )
    assert res["status"] == "PASS"
    assert res["rows"] == 1
