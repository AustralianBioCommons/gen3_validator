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
    """Path to the bundled test schema (the same one used by the other test modules)."""
    current_dir = os.path.dirname(__file__)
    return os.path.join(current_dir, "..", "schema", "gen3_test_schema.json")


@pytest.fixture
def fixture_resolved_schema(fixture_schema_path) -> dict:
    """A resolved schema dict, ready to pass to the bulk/link validator."""
    resolver = gen3_validator.ResolveSchema(fixture_schema_path)
    resolver.resolve_schema()
    return resolver.schema_resolved


def _write(folder, name, content) -> str:
    """Write a node JSON file (dict/list) or the import order file (str) into ``folder``."""
    path = os.path.join(str(folder), name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f)
    return path


def _link_rows(results) -> list:
    """Return only the link-integrity rows, so tests don't couple to schema-validation rows."""
    return [r for r in results if r["validator"] == "link"]


# ---------------------------------------------------------------------------
# Flagship tests: the clearest possible happy-path and angry-path examples
# ---------------------------------------------------------------------------

def test_links_happy_path(tmp_path, fixture_resolved_schema):
    """
    HAPPY PATH: a child whose link points at a parent that exists -> no link errors.

    A `sample` links up to a `clinical_descriptor` via the `clinical_descriptors` property.
    Here the sample points at "clinical_descriptor_1", and that exact record exists in
    clinical_descriptor.json, so the reference resolves and NO link errors are produced.

    Input folder:
        clinical_descriptor.json : [ {submitter_id: "clinical_descriptor_1", ...} ]
        sample.json              : [ {submitter_id: "sample_1",
                                      clinical_descriptors: {submitter_id: "clinical_descriptor_1"}} ]
        DataImportOrder.txt      : clinical_descriptor, then sample

    Expected: the link-integrity result is empty (every reference resolves).
    """
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "clinical_descriptor_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "sample.json", [
        {
            "submitter_id": "sample_1",
            "type": "sample",
            "clinical_descriptors": {"submitter_id": "clinical_descriptor_1"},
        },
    ])
    _write(tmp_path, "DataImportOrder.txt", "clinical_descriptor\nsample\n")

    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)

    assert _link_rows(results) == []


def test_links_angry_path(tmp_path, fixture_resolved_schema):
    """
    ANGRY PATH: a child whose link points at a parent that does NOT exist -> one link error.

    Same shape as the happy path, but the sample points at "clinical_descriptor_MISSING",
    which is not present in clinical_descriptor.json. This is a dangling reference, so exactly
    one link FAIL is produced that names the offending property and the missing id.

    Input folder:
        clinical_descriptor.json : [ {submitter_id: "clinical_descriptor_1", ...} ]
        sample.json              : [ {submitter_id: "sample_1",
                                      clinical_descriptors: {submitter_id: "clinical_descriptor_MISSING"}} ]
        DataImportOrder.txt      : clinical_descriptor, then sample

    Expected: exactly one link row, fully specified below.
    """
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "clinical_descriptor_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "sample.json", [
        {
            "submitter_id": "sample_1",
            "type": "sample",
            "clinical_descriptors": {"submitter_id": "clinical_descriptor_MISSING"},
        },
    ])
    _write(tmp_path, "DataImportOrder.txt", "clinical_descriptor\nsample\n")

    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)

    assert _link_rows(results) == [
        {
            "node": "sample",
            "index": 0,
            "validation_result": "FAIL",
            "invalid_key": "clinical_descriptors",
            "schema_path": "links",
            "validator": "link",
            "validator_value": "clinical_descriptor",
            "validation_error": (
                "Link 'clinical_descriptors' references clinical_descriptor "
                "'clinical_descriptor_MISSING' (by submitter_id) but no matching record "
                "exists in clinical_descriptor.json"
            ),
            "source_file": "sample.json",
        }
    ]


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------

def test_extract_links_plain(fixture_resolved_schema):
    """A node with one plain link exposes its property name and target node."""
    schema = bulk.pull_schema("medication", fixture_resolved_schema)
    assert bulk.extract_links(schema) == [
        {"name": "clinical_descriptors", "target_type": "clinical_descriptor"},
    ]


def test_extract_links_subgroup_is_flattened(fixture_resolved_schema):
    """
    A node whose links are wrapped in a `subgroup` (imaging_file can attach to either a
    clinical_descriptor or a core_metadata_collection) is flattened to both links.
    """
    schema = bulk.pull_schema("imaging_file", fixture_resolved_schema)
    assert bulk.extract_links(schema) == [
        {"name": "clinical_descriptors", "target_type": "clinical_descriptor"},
        {"name": "core_metadata_collections", "target_type": "core_metadata_collection"},
    ]


def test_extract_links_handles_missing_or_empty():
    """A schema with no/None/empty links yields an empty list (nothing to check)."""
    assert bulk.extract_links({}) == []
    assert bulk.extract_links({"links": None}) == []
    assert bulk.extract_links({"links": []}) == []


# ---------------------------------------------------------------------------
# build_identifier_index
# ---------------------------------------------------------------------------

def test_build_identifier_index_keys_by_id_field():
    """
    Records are indexed under whichever identifier key they carry: project uses `code`,
    everything else uses `submitter_id`. A present-but-empty node still gets an entry so it
    can be told apart from an absent node.
    """
    index = bulk.build_identifier_index({
        "project": [{"code": "P1", "type": "project"}],
        "subject": [{"submitter_id": "subject_1", "type": "subject"}],
        "empty_node": [],
    })
    assert index["project"] == {"code": {"P1"}}
    assert index["subject"] == {"submitter_id": {"subject_1"}}
    assert index["empty_node"] == {}


# ---------------------------------------------------------------------------
# validate_record_links (unit-level)
# ---------------------------------------------------------------------------

def test_validate_record_links_array_reports_only_missing():
    """
    A to-many link whose value is an ARRAY of references is checked per element: the present
    one resolves and the missing one fails. Here a lipidomics_assay links to two samples but
    only sample_1 exists.
    """
    record = {
        "submitter_id": "la_1",
        "type": "lipidomics_assay",
        "samples": [{"submitter_id": "sample_1"}, {"submitter_id": "sample_2"}],
    }
    links = [{"name": "samples", "target_type": "sample"}]
    index = {"sample": {"submitter_id": {"sample_1"}}}

    rows = bulk.validate_record_links(record, 0, "lipidomics_assay", links, index)

    assert len(rows) == 1
    assert "sample_2" in rows[0]["validation_error"]


def test_validate_record_links_null_or_malformed_ref_skipped():
    """
    Null/missing link fields and non-object reference shapes are NOT referential-integrity
    errors (a wrong-typed value is caught by schema validation), so they produce no link rows.
    """
    links = [{"name": "clinical_descriptors", "target_type": "clinical_descriptor"}]
    index = {"clinical_descriptor": {"submitter_id": {"cd_1"}}}
    assert bulk.validate_record_links({"clinical_descriptors": None}, 0, "sample", links, index) == []
    assert bulk.validate_record_links({"clinical_descriptors": "cd_1"}, 0, "sample", links, index) == []
    assert bulk.validate_record_links({}, 0, "sample", links, index) == []


# ---------------------------------------------------------------------------
# Integration: validate_data_folder
# ---------------------------------------------------------------------------

def test_project_referenced_by_code(tmp_path, fixture_resolved_schema):
    """
    The `project` node is special: it is identified by `code` (not submitter_id) and other
    nodes reference it via {"code": ...}. A subject pointing at a real project code resolves;
    pointing at an unknown code fails.
    """
    _write(tmp_path, "project.json", {"code": "P1", "type": "project"})
    _write(tmp_path, "subject.json", [
        {"submitter_id": "subject_1", "type": "subject", "projects": {"code": "P1"}},
    ])
    _write(tmp_path, "DataImportOrder.txt", "project\nsubject\n")
    assert _link_rows(bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)) == []

    _write(tmp_path, "subject.json", [
        {"submitter_id": "subject_1", "type": "subject", "projects": {"code": "NOPE"}},
    ])
    rows = _link_rows(bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema))
    assert len(rows) == 1
    assert rows[0]["validator_value"] == "project"
    assert "NOPE" in rows[0]["validation_error"]


def test_subgroup_node_only_fails_missing_target(tmp_path, fixture_resolved_schema):
    """
    A subgroup node (imaging_file) links to two parents. With one parent present and one
    missing, only the missing reference fails.
    """
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "cd_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "core_metadata_collection.json", [
        {"submitter_id": "cmc_1", "type": "core_metadata_collection"},
    ])
    _write(tmp_path, "imaging_file.json", [
        {
            "submitter_id": "if_1",
            "type": "imaging_file",
            "clinical_descriptors": {"submitter_id": "cd_MISSING"},
            "core_metadata_collections": {"submitter_id": "cmc_1"},
        },
    ])
    _write(
        tmp_path,
        "DataImportOrder.txt",
        "clinical_descriptor\ncore_metadata_collection\nimaging_file\n",
    )

    rows = _link_rows(bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema))
    assert len(rows) == 1
    assert rows[0]["invalid_key"] == "clinical_descriptors"
    assert rows[0]["validator_value"] == "clinical_descriptor"


def test_absent_target_node_skipped_with_one_warning(tmp_path, fixture_resolved_schema, caplog):
    """
    When a link points to a node that is not in the folder at all, there is nothing to check
    against, so the reference is skipped with a warning (not failed). Two subjects both
    reference an absent `project`, and the warning is emitted only once (deduplicated).
    """
    _write(tmp_path, "subject.json", [
        {"submitter_id": "subject_1", "type": "subject", "projects": {"code": "P1"}},
        {"submitter_id": "subject_2", "type": "subject", "projects": {"code": "P2"}},
    ])
    _write(tmp_path, "DataImportOrder.txt", "subject\n")  # project.json absent

    with caplog.at_level(logging.WARNING):
        rows = _link_rows(bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema))

    assert rows == []
    project_warnings = [
        r for r in caplog.records if "projects" in r.message and "project" in r.message
    ]
    assert len(project_warnings) == 1


def test_present_but_empty_target_node_fails(tmp_path, fixture_resolved_schema):
    """
    A node that is present in the folder but empty is different from an absent node: a
    reference into a shipped-but-empty node cannot resolve and is reported as a failure.
    """
    _write(tmp_path, "sample.json", [])  # present but empty
    _write(tmp_path, "lipidomics_assay.json", [
        {
            "submitter_id": "la_1",
            "type": "lipidomics_assay",
            "samples": {"submitter_id": "sample_1"},
        },
    ])
    _write(tmp_path, "DataImportOrder.txt", "sample\nlipidomics_assay\n")

    rows = _link_rows(bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema))
    assert len(rows) == 1
    assert rows[0]["validator_value"] == "sample"


def test_check_links_false_disables_link_validation(tmp_path, fixture_resolved_schema):
    """
    With check_links=False the validator behaves exactly as before this feature: schema
    validation only, no link rows, even when a reference is dangling.
    """
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "clinical_descriptor_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "sample.json", [
        {
            "submitter_id": "sample_1",
            "type": "sample",
            "clinical_descriptors": {"submitter_id": "clinical_descriptor_MISSING"},
        },
    ])
    _write(tmp_path, "DataImportOrder.txt", "clinical_descriptor\nsample\n")

    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema, check_links=False)
    assert _link_rows(results) == []


def test_rows_are_ordered_by_import_order(tmp_path, fixture_resolved_schema):
    """
    The flat report stays ordered by import order even with link checking: an earlier node's
    rows precede a later node's, and within a node schema rows precede link rows.

    medical_history (bad enum -> schema FAIL) comes before sample (dangling link -> link
    FAIL); sample carries both a schema failure (freeze_thaw_cycles wrong type) and a link
    failure, and its schema row appears before its link row.
    """
    _write(tmp_path, "medical_history.json", [
        {"submitter_id": "mh_1", "type": "medical_history", "atrial_fibrillation": "NOPE", "cabg": "yes"},
    ])
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "cd_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "sample.json", [
        {
            "submitter_id": "sample_1",
            "type": "sample",
            "freeze_thaw_cycles": "NOT_AN_INT",
            "clinical_descriptors": {"submitter_id": "cd_MISSING"},
        },
    ])
    _write(
        tmp_path,
        "DataImportOrder.txt",
        "medical_history\nclinical_descriptor\nsample\n",
    )

    results = bulk.validate_data_folder(str(tmp_path), fixture_resolved_schema)

    nodes_seen = [r["node"] for r in results]
    # medical_history rows come before sample rows
    assert nodes_seen.index("medical_history") < nodes_seen.index("sample")
    # within sample, the schema failure precedes the link failure
    sample_validators = [r["validator"] for r in results if r["node"] == "sample"]
    assert "link" in sample_validators
    assert sample_validators.index("link") == len(sample_validators) - 1
