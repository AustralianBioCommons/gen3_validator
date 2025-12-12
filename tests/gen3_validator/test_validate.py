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
            "atrial_fibrillation": "yes",
            "cabg": "yes",
            "type": "medical_history"
        }
    ]

    expected = [
        {
            'node': 'medical_history',
            'index': 0,
            'validation_result': 'PASS',
            'invalid_key': None,
            'schema_path': None,
            'validator': None,
            'validator_value': None,
            'validation_error': None
        }
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
    data = [
        {
            "atrial_fibrillation": "yes",
            "cabg": "yes"
        }
    ]
    resolved_schema = fixture_resolver_inst.schema_resolved

    with pytest.raises(Exception, match="Error in validate_list_dict during object validation at index 0, key 'type' not found in"):
        gen3_validator.validate.validate_list_dict(data, resolved_schema)
