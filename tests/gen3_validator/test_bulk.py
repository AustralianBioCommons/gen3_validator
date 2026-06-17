import json
import logging
import os

import pytest

import gen3_validator
from gen3_validator import bulk


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fixture_schema_path() -> str:
    """Path to the bundled test schema (the same one used by test_validate.py)."""
    current_dir = os.path.dirname(__file__)
    return os.path.join(current_dir, "..", "schema", "gen3_test_schema.json")


@pytest.fixture
def fixture_resolved_schema(fixture_schema_path) -> dict:
    """A resolved schema dict, ready to pass to the bulk validator."""
    resolver = gen3_validator.ResolveSchema(fixture_schema_path)
    resolver.resolve_schema()
    return resolver.schema_resolved


def _write(folder, name, content) -> str:
    """
    Write a node JSON file or the import order file into ``folder``.

    A dict/list is serialised as JSON (a data node file); a string is written verbatim
    (used for the plain-text import order file).
    """
    path = os.path.join(str(folder), name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f)
    return path


# Records whose validity against the test schema is verified by test_validate.py:
# a valid/invalid medical_history and a valid/invalid medication. The invalid records
# each trip exactly one enum constraint.
MH_VALID = {
    "submitter_id": "medical_history_1",
    "atrial_fibrillation": "yes",
    "cabg": "yes",
    "type": "medical_history",
}
MH_INVALID = {
    "submitter_id": "medical_history_2",
    "atrial_fibrillation": "NOPE",  # not in the ['yes', 'no'] enum
    "cabg": "yes",
    "type": "medical_history",
}
MED_INVALID = {
    "submitter_id": "med_1",
    "type": "medication",
    "bp_lowering_meds": "yes",
    "diabetes_therapy": "oral",
    "lipid_lowering_meds": "No",  # should be lowercase 'no'
    "clinical_descriptors": {"submitter_id": "cd_1"},
}


# ---------------------------------------------------------------------------
# parse_import_order
# ---------------------------------------------------------------------------

def test_parse_import_order_plain(tmp_path):
    """
    Plain node names, one per line, are the real format emitted by the synthetic data
    pipeline. Blank lines, surrounding whitespace, and ``#`` comments must be ignored so
    a hand-edited file still parses cleanly.

    Input: a file with padding, a blank line and a comment.
    Expected: the three node names in file order.
    """
    path = tmp_path / "DataImportOrder.txt"
    path.write_text("project\n\n  subject  \n# a comment line\nsample\n", encoding="utf-8")
    assert bulk.parse_import_order(str(path)) == ["project", "subject", "sample"]


def test_parse_import_order_numbered(tmp_path):
    """
    Some import order files prefix each node with an order number (tab- or space-
    separated). The number, not the line position, defines the sequence — so an
    out-of-order file must still produce the numbered order.

    Input: numbered rows written out of order (2, 1, 3).
    Expected: nodes sorted by their number.
    """
    path = tmp_path / "DataImportOrder.txt"
    path.write_text("2\tsubject\n1\tproject\n3\tsample\n", encoding="utf-8")
    assert bulk.parse_import_order(str(path)) == ["project", "subject", "sample"]


def test_parse_import_order_missing_file_raises(tmp_path):
    """
    The import order file is mandatory — without it there is no sequence to validate, so
    its absence should fail fast rather than silently validate nothing.
    """
    with pytest.raises(FileNotFoundError):
        bulk.parse_import_order(str(tmp_path / "DoesNotExist.txt"))


# ---------------------------------------------------------------------------
# load_node_records
# ---------------------------------------------------------------------------

def test_load_node_records_single_object_normalized(tmp_path):
    """
    Some node files (e.g. project.json) contain a single JSON object rather than an array.
    These must be normalised to a one-element list so every node validates uniformly.
    """
    path = tmp_path / "project.json"
    path.write_text(json.dumps({"code": "X", "type": "project"}), encoding="utf-8")
    assert bulk.load_node_records(str(path)) == [{"code": "X", "type": "project"}]


def test_load_node_records_array_passthrough(tmp_path):
    """A node file containing a JSON array of records is returned unchanged."""
    records = [{"submitter_id": "a", "type": "sample"}, {"submitter_id": "b", "type": "sample"}]
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    assert bulk.load_node_records(str(path)) == records


def test_load_node_records_non_collection_raises(tmp_path):
    """
    A node file whose top level is neither an object nor an array (here, a bare number)
    is a structural error and should raise ValueError.
    """
    path = tmp_path / "broken.json"
    path.write_text("42", encoding="utf-8")
    with pytest.raises(ValueError):
        bulk.load_node_records(str(path))


# ---------------------------------------------------------------------------
# validate_data_folder
# ---------------------------------------------------------------------------

def test_validate_data_folder_happy_path(tmp_path, fixture_resolved_schema):
    """
    When every record is valid, the report is empty — and this must hold whether a node
    file is a single object (medical_history here) or an array (medication here).
    """
    _write(tmp_path, "medical_history.json", MH_VALID)              # single object
    _write(tmp_path, "medication.json", [])                          # empty array
    _write(tmp_path, "DataImportOrder.txt", "medical_history\nmedication\n")
    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)
    assert results == []


def test_validate_data_folder_reports_failure_augmented(tmp_path, fixture_resolved_schema):
    """
    A schema failure must be reported with the node name, the within-node index, and the
    new ``source_file`` field that tells the user which file the bad record came from.

    Input: a file with one valid then one invalid medical_history record.
    Expected: one FAIL for the second record (index 1), tagged with its source file.
    """
    _write(tmp_path, "medical_history.json", [MH_VALID, MH_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "medical_history\n")
    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)

    assert len(results) == 1
    fail = results[0]
    assert fail["node"] == "medical_history"
    assert fail["source_file"] == "medical_history.json"
    assert fail["index"] == 1
    assert fail["validation_result"] == "FAIL"
    assert fail["validator"] == "enum"
    assert fail["invalid_key"] == "atrial_fibrillation"


def test_validate_data_folder_global_ordering(tmp_path, fixture_resolved_schema):
    """
    The flat report follows the import order: all of an earlier node's records precede a
    later node's records. Here the import order deliberately lists medication before
    medical_history, which is the order the results must appear in.
    """
    _write(tmp_path, "medical_history.json", [MH_INVALID])
    _write(tmp_path, "medication.json", [MED_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "medication\nmedical_history\n")
    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)
    assert [r["node"] for r in results] == ["medication", "medical_history"]


def test_missing_node_file_warns_and_skips(tmp_path, fixture_resolved_schema, caplog):
    """
    A node listed in the import order but with no matching file is skipped with a warning
    (its absence is expected, not fatal); the remaining nodes are still validated.
    """
    _write(tmp_path, "medical_history.json", [MH_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "subject\nmedical_history\n")  # subject.json absent
    with caplog.at_level(logging.WARNING):
        results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)
    assert [r["node"] for r in results] == ["medical_history"]
    assert any("subject" in r.message and "not found" in r.message for r in caplog.records)


def test_extra_file_not_in_order_ignored(tmp_path, fixture_resolved_schema, caplog):
    """
    A ``*.json`` file present in the folder but absent from the import order is ignored
    (never validated) and a warning is logged. Here medication.json would fail if it were
    validated, so an empty report proves it was skipped.
    """
    _write(tmp_path, "medical_history.json", [MH_VALID])
    _write(tmp_path, "medication.json", [MED_INVALID])           # not listed -> must be ignored
    _write(tmp_path, "DataImportOrder.txt", "medical_history\n")
    with caplog.at_level(logging.WARNING):
        results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)
    assert results == []
    assert any("medication.json" in r.message for r in caplog.records)


def test_bad_record_does_not_abort_run(tmp_path, fixture_resolved_schema):
    """
    A record that breaks validation outright (missing the required 'type' key, which makes
    the underlying validate_list_dict raise) must not abort the whole run: that node yields
    a single ERROR record and later nodes are still validated.
    """
    _write(tmp_path, "medical_history.json", [{"atrial_fibrillation": "yes"}])  # no 'type'
    _write(tmp_path, "medication.json", [MED_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "medical_history\nmedication\n")
    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)

    assert results[0]["node"] == "medical_history"
    assert results[0]["validation_result"] == "ERROR"
    assert results[0]["source_file"] == "medical_history.json"
    assert any(
        r["node"] == "medication" and r["validation_result"] == "FAIL" for r in results
    )


def test_validate_data_folder_from_schema_matches_core(
    tmp_path, fixture_schema_path, fixture_resolved_schema
):
    """
    The path-based convenience wrapper resolves the schema itself and must produce exactly
    the same report as the core function given a pre-resolved schema.
    """
    _write(tmp_path, "medical_history.json", [MH_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "medical_history\n")
    via_path = bulk.validate_data_folder_from_schema(str(tmp_path), fixture_schema_path)
    via_core = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)
    assert via_path == via_core
