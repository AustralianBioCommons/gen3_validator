import pytest
from gen3_validator import *
from typing import List, Dict, Any
import os

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


def fixture_schema_path() -> str:
    current_dir = os.path.dirname(__file__)
    schema_path = os.path.join(current_dir, "..", "schema", "gen3_test_schema.json")
    return schema_path

def fixture_resolver_inst(fixture_schema_path) -> dict:
    resolver = gen3_validator.ResolveSchema(fixture_schema_path)
    resolver.resolve_schema()
    return resolver

# def test_resolved_schema_version(fixture_resolver_inst):
#     schema = fixture_resolver_inst.schema_resolved
#     assert schema["_dict_version"] == "3.1.0"