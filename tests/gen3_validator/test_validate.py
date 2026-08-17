import pytest
import gen3_validator as gen3_validator
from typing import List, Dict, Any
import os
from unittest.mock import patch



@pytest.fixture
def fixture_data_pass() -> List[Dict[str, Any]]:
    data = [
        {
            "atrial_fibrillation": "yes",
            "cabg": "yes",
            "cvd_death": "yes",
            "cvd_family_history": "yes",
            "cvd_non_fatal_10_year": "yes",
            "cvd_reported": "yes",
            "cvd_self_reported": "yes",
            "date_death": "8583-24-35",
            "diabetes_self_reported": "no",
            "diabetes_type": "type-1",
            "heart_failure_status": "no",
            "heart_rate": 80,
            "hypertension_measured": "yes",
            "hypertension_self_reported": "yes",
            "mhx_pad": "no",
            "os_event": "alive",
            "os_time": 54,
            "stent": "no",
            "subjects": {
                "submitter_id": "subject_e5616257f8"
            },
            "submitter_id": "medical_history_7598b38ca0",
            "type": "medical_history"
        }
    ]
    return data


def fixture_data_fail() -> List[Dict[str, Any]]:
    data = [
        {
            "atrial_fibrillation": "invalid_atrial_fib_enum",
            "cabg": "invalid_cabg_enum",
            "cvd_death": "yes",
            "cvd_family_history": "yes",
            "cvd_non_fatal_10_year": "yes",
            "cvd_reported": "yes",
            "cvd_self_reported": "yes",
            "date_death": "8583-24-35",
            "diabetes_self_reported": "no",
            "diabetes_type": "type-1",
            "heart_failure_status": "no",
            "heart_rate": "80",
            "hypertension_measured": "yes",
            "hypertension_self_reported": "yes",
            "mhx_pad": "no",
            "os_event": "alive",
            "os_time": 54,
            "stent": "no",
            "subjects": {
                "submitter_id": "subject_e5616257f8"
            },
            "submitter_id": "medical_history_7598b38ca0",
            "type": "medical_history"
        }
    ]
    return data


@pytest.fixture
def fixture_schema_path() -> str:
    current_dir = os.path.dirname(__file__)
    schema_path = os.path.join(current_dir, "..", "schema", "gen3_test_schema.json")
    return schema_path


@pytest.fixture
def fixture_resolver_inst(fixture_schema_path) -> dict:
    resolver = gen3_validator.ResolveSchema(fixture_schema_path)
    resolver.resolve_schema()
    return resolver


def test_resolved_schema_version(fixture_resolver_inst):
    assert fixture_resolver_inst.get_schema_version() == "1.0.0"


def test_validate_json_pass(fixture_resolver_inst):
    data = [
        {
            "submitter_id": "medical_history_7598b38ca0",
            "atrial_fibrillation": "yes",
            "cabg": "yes",
            "type": "medical_history"
        }
    ]

    expected = [
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved
    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)
    assert result == expected


def test_validate_json_fail(fixture_resolver_inst):
    data = [
        {
            "atrial_fibrillation": 2,
            "cabg": 14,
            "type": "medical_history"
        }
    ]

    expected = [
        {
            'node': 'medical_history',
            'index': 0,
            'validation_result': 'FAIL',
            'invalid_key': 'root',
            'schema_path': 'required',
            'validator': 'required',
            'validator_value': ['submitter_id', 'type'],
            'validation_error': "'submitter_id' is a required property"
        },
        {
            'node': 'medical_history',
            'index': 0,
            'validation_result': 'FAIL',
            'invalid_key': 'atrial_fibrillation',
            'schema_path': 'properties.atrial_fibrillation.enum',
            'validator': 'enum',
            'validator_value': ['yes', 'no'],
            'validation_error': "2 is not one of ['yes', 'no']"
        },
        {
            'node': 'medical_history',
            'index': 0,
            'validation_result': 'FAIL',
            'invalid_key': 'cabg',
            'schema_path': 'properties.cabg.enum',
            'validator': 'enum',
            'validator_value': ['yes', 'no'],
            'validation_error': "14 is not one of ['yes', 'no']"
        }
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved
    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)
    assert result == expected


def test_missing_type_key(fixture_resolver_inst):
    """A record with no 'type' key is reported, not raised on.

    Every Gen3 record names its node in a 'type' field; without it there is
    nothing to look up a schema by, so the record cannot be checked. That is a
    defect in the data, and the caller needs it back as a result row it can
    write to a report alongside everything else. Before this behaviour existed
    the function raised instead, which threw away every other finding in the
    same batch.
    """
    data = [
        {
            "atrial_fibrillation": "yes",
            "cabg": "yes"
        }
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved

    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)

    assert result == [
        {
            "node": None,
            "index": 0,
            "validation_result": "ERROR",
            "invalid_key": None,
            "schema_path": None,
            "validator": None,
            "validator_value": None,
            "validation_error": "record at index 0 has no 'type' key",
        }
    ]


def test_unknown_node_type(fixture_resolver_inst):
    """A 'type' naming a node the dictionary does not define is reported, not raised on.

    This is the exact shape of a real failure: the omix3 project's dbt models
    emitted records of type 'case', but the omix3 dictionary calls that node
    'subject' and has no 'case' at all. The run must say so in its results,
    because that message is the only thing telling an operator which model to
    rename.
    """
    data = [{"type": "case", "submitter_id": "case_0001"}]
    resolved_schema = fixture_resolver_inst.schema_resolved

    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)

    assert len(result) == 1
    assert result[0]["node"] == "case"
    assert result[0]["index"] == 0
    assert result[0]["validation_result"] == "ERROR"
    assert result[0]["validation_error"] == "node 'case' not found in resolved schema"


def test_unknown_node_does_not_suppress_real_failures(fixture_resolver_inst):
    """An unreportable record must not hide the genuine failures beside it.

    THE regression this change exists for. validate_list_dict used to raise on
    the first unknown node type, so a single stray record aborted the batch and
    every real schema violation after it went unreported — the caller saw one
    exception instead of a list of things to fix. Both records here must come
    back: the unknown type as ERROR, the bad enum value as FAIL.

    Ordering matters too. The unknown type is deliberately FIRST, because that
    is the position that used to abort everything downstream.
    """
    data = [
        {"type": "case", "submitter_id": "case_0001"},
        {
            "type": "medical_history",
            "submitter_id": "medical_history_7598b38ca0",
            "atrial_fibrillation": "definitely",  # not in the enum
        },
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved

    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)

    outcomes = {(r["node"], r["validation_result"]) for r in result}
    assert ("case", "ERROR") in outcomes
    assert ("medical_history", "FAIL") in outcomes


def test_catch_agilent_error(fixture_resolver_inst):
    """
    This test aims to capture a real world error that was missed in version 1
    """
    data = [
        {
            "submitter_id": "lipidomics-assay-ausdiab-12-221-990940238_e91aef83bc5a85c37d2c8ddbb289de3ffc863bbb3489c650b3a10f13f1477895",
            "type": "lipidomics_assay",
            "assay_id": "AD12_250#12-221-990940238",
            "assay_description": "Targeted mass spec lipidome",
            "instrument_type": "Agilent QQQ LC-MS",
            "samples": [
                {
                    "submitter_id": "sample-ausdiab-0441301_e91aef83bc5a85c37d2c8ddbb289de3ffc863bbb3489c650b3a10f13f1477895"
                }
            ]
        }
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved
    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)

    # Instead of relying on exact error string, check presence of expected values in the error message for robustness
    error_msg = result[0]["validation_error"]
    assert "'Agilent QQQ LC-MS'" in error_msg
    assert "is not one of" in error_msg

def test_catch_uppercase_enum_error(fixture_resolver_inst):
    """
    This test aims to catch Yes or No when it should be lowercase according to the schema
    """
    data = [{    
        "submitter_id": "CDAH_medication_d4a8b34e-70c6-4e05-9898-5eba6ab0f88a",
        "type": "medication",
        "bp_lowering_meds": 'yes',
        "diabetes_therapy": 'oral',
        "lipid_lowering_meds": "No",  #this is an invalid value
        "clinical_descriptors": {
            "submitter_id": "CDAH_clinical_descriptor_50811594-b207-4e3e-8ab8-e8788806d2bc"
        }
    }]
    resolved_schema = fixture_resolver_inst.schema_resolved
    result = gen3_validator.validate.validate_list_dict(data, resolved_schema)
    error_msg = result[0]["validation_error"]
    assert "'No'" in error_msg
    assert "is not one of" in error_msg