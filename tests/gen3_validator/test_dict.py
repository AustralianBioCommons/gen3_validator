import pytest
import json
from gen3_validator.dict import DataDictionary
from unittest.mock import patch, MagicMock, mock_open
import os


@pytest.fixture
def test_schema_path():
    return "../../schema/gen3_test_schema.json"

def test_init_DataDictionary(test_schema_path):
    schema = DataDictionary(test_schema_path)
    assert schema.schema_path == test_schema_path

@pytest.fixture
def DataDictionary_instance(test_schema_path):
    return DataDictionary(test_schema_path)


def test_read_json(DataDictionary_instance, test_schema_path):
    mock_data = [{"submitter_id": "subject-example-990910001"}]
    with patch("gen3_validator.dict.open",
               mock_open(read_data=json.dumps(mock_data))):
        result = DataDictionary_instance.read_json(test_schema_path)
        assert result == mock_data

def test_get_nodes(DataDictionary_instance):
    schema = {
        "sample": "schema_content",
        "medication": "schema_content"
    }
    DataDictionary_instance.schema = schema
    result = DataDictionary_instance.get_nodes()
    assert result == ["sample", "medication"]

def test_get_node_link(DataDictionary_instance):
    schema = {
        "sample.yaml": {
            "id": "sample",
            "links": [
                {
                    "backref": "samples",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        }
    }
    links = [
        {
            "backref": "samples",
            "label": "taken_from",
            "multiplicity": "many_to_one",
            "name": "subjects",
            "required": True,
            "target_type": "subject"
        }
    ]
    DataDictionary_instance.schema = schema
    result = DataDictionary_instance.get_node_link("sample.yaml")
    assert result == ("sample", links)

def test_get_node_category(DataDictionary_instance):
    schema = {
        "demographic.yaml": {
            "id": "demographic",
            "category": "clinical"
        }
    }
    DataDictionary_instance.schema = schema
    node_id, category = DataDictionary_instance.get_node_category("demographic.yaml")
    assert node_id == "demographic"
    assert category == "clinical"

def test_get_node_properties(DataDictionary_instance):
    schema = {
        "demographic.yaml": {
            "id": "demographic",
            "properties": {
                "sex": {
                    "description": "Sex of the participant",
                    "enum": ["male", "female", "other"]
                }
            }
        }
    }
    DataDictionary_instance.schema = schema
    node_id, property_keys = DataDictionary_instance.get_node_properties("demographic.yaml")
    assert node_id == "demographic"
    assert set(property_keys) == {"sex"}

def test_generate_node_lookup(DataDictionary_instance):
    schema = {
        "demographic.yaml": {
            "id": "demographic",
            "category": "clinical",
            "properties": {
                "sex": {
                    "description": "Sex of the participant",
                    "enum": ["male", "female", "other"]
                }
            }
        },
        "_definitions.yaml": None
    }
    expected = {
        'demographic.yaml': {
            'category': 'clinical',
            'properties': ('demographic', ['sex'])
        }
    }
    DataDictionary_instance.schema = schema
    DataDictionary_instance.nodes = ['demographic.yaml', '_definitions.yaml']
    node_lookup = DataDictionary_instance.generate_node_lookup()
    assert node_lookup == expected

def test_find_upstream_downstream(DataDictionary_instance):
    schema = {
        "sample.yaml": {
            "id": "sample",
            "links": [
                {
                    "backref": "samples",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        }
    }
    DataDictionary_instance.schema = schema
    node_pairs = DataDictionary_instance._find_upstream_downstream("sample.yaml")
    assert node_pairs == [("subject", "sample")]

def test_get_all_node_pairs(DataDictionary_instance):
    schema = {
        "sample.yaml": {
            "id": "sample",
            "links": [
                {
                    "backref": "samples",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        },
        "medication.yaml": {
            "id": "medication",
            "links": [
                {
                    "backref": "medications",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        }
    }
    DataDictionary_instance.schema = schema
    DataDictionary_instance.nodes = ["sample.yaml", "medication.yaml"]
    node_pairs = DataDictionary_instance.get_all_node_pairs()
    assert node_pairs == [("subject", "sample"), ("subject", "medication")]

def test_get_node_order(DataDictionary_instance):
    schema = {
        "subject.yaml": {
            "id": "subject",
            "links": [
                {
                    "backref": "subjects",
                    "label": "part_of",
                    "multiplicity": "many_to_one",
                    "name": "projects",
                    "required": True,
                    "target_type": "project"
                }
            ]
        },
        "sample.yaml": {
            "id": "sample",
            "links": [
                {
                    "backref": "samples",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        }
    }
    DataDictionary_instance.schema = schema
    DataDictionary_instance.nodes = ["subject.yaml", "sample.yaml"]
    node_pairs = DataDictionary_instance.get_all_node_pairs()
    node_order = DataDictionary_instance.get_node_order(node_pairs)
    assert node_order == ['project', 'subject', 'sample']

def test_split_json(DataDictionary_instance):
    schema = {
        "subject.yaml": {"id": "subject", "type": "object"},
        "sample.yaml": {"id": "sample", "type": "object"},
        "project.yaml": {"id": "project", "type": "object"},
    }
    DataDictionary_instance.schema = schema
    DataDictionary_instance.nodes = ["subject.yaml", "sample.yaml", "project.yaml"]
    result = DataDictionary_instance.split_json()
    expected = [
        {"id": "subject", "type": "object"},
        {"id": "sample", "type": "object"},
        {"id": "project", "type": "object"},
    ]
    assert result == expected

def test_return_schema(DataDictionary_instance):
    # Prepare a mock schema_list with several node dicts
    schema_list = [
        {"id": "subject", "type": "object"},
        {"id": "sample", "type": "object"},
        {"id": "project", "type": "object"},
    ]
    DataDictionary_instance.schema_list = schema_list

    # Test with id without .yaml
    result = DataDictionary_instance.return_schema("sample")
    assert result == {"id": "sample", "type": "object"}

    # Test with id with .yaml
    result = DataDictionary_instance.return_schema("project.yaml")
    assert result == {"id": "project", "type": "object"}

    # Test with id that does not exist
    result = DataDictionary_instance.return_schema("not_a_node")
    assert result is None

    # Test with id with .yaml that does not exist
    result = DataDictionary_instance.return_schema("not_a_node.yaml")
    assert result is None

def test_schema_list_to_json(DataDictionary_instance):
    schema_list = [
        {"id": "subject", "type": "object"},
        {"id": "project", "type": "object"},
        {"id": "sample", "type": "object"},
    ]
    result = DataDictionary_instance.schema_list_to_json(schema_list)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"subject.yaml", "project.yaml", "sample.yaml"}
    assert result["subject.yaml"] == {"id": "subject", "type": "object"}
    assert result["project.yaml"] == {"id": "project", "type": "object"}
    assert result["sample.yaml"] == {"id": "sample", "type": "object"}

    schema_list_with_missing_id = [
        {"id": "subject", "type": "object"},
        {"type": "object"},
    ]
    result = DataDictionary_instance.schema_list_to_json(schema_list_with_missing_id)
    assert "subject.yaml" in result
    assert len(result) == 1

def test_get_schema_version(DataDictionary_instance):
    schema = {
        "_settings.yaml": {
            "_dict_version": "3.0.1"
        },
        "sample.yaml": {
            "id": "sample"
        }
    }
    version = DataDictionary_instance.get_schema_version(schema)
    assert version == "3.0.1"

    schema_missing_settings = {
        "sample.yaml": {
            "id": "sample"
        }
    }
    try:
        DataDictionary_instance.get_schema_version(schema_missing_settings)
        assert False, "Expected exception for missing _settings.yaml"
    except Exception as e:
        assert "Could not pull schema version" in str(e) or isinstance(e, KeyError)

    schema_missing_version = {
        "_settings.yaml": {},
        "sample.yaml": {
            "id": "sample"
        }
    }
    try:
        DataDictionary_instance.get_schema_version(schema_missing_version)
        assert False, "Expected exception for missing _dict_version"
    except Exception as e:
        assert "Could not pull schema version" in str(e) or isinstance(e, KeyError)


# ... existing code ...

def test_parse_schema_sets_attributes(tmp_path):
    # Create a minimal schema file
    schema_content = {
        "subject.yaml": {"id": "subject", "type": "object"},
        "sample.yaml": {"id": "sample", "type": "object"},
    }
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema_content))

    dd = DataDictionary(str(schema_path))
    dd.nodes = ["subject.yaml", "sample.yaml"]  # Needed for split_json

    dd.parse_schema()

    # Check that schema and schema_list are set correctly
    assert dd.schema == schema_content
    assert isinstance(dd.schema_list, list)
    assert {"id": "subject", "type": "object"} in dd.schema_list
    assert {"id": "sample", "type": "object"} in dd.schema_list

def test_calculate_node_order_sets_attributes():
    dd = DataDictionary("dummy_path")
    # Mock schema and nodes
    dd.schema = {
        "subject.yaml": {
            "id": "subject",
            "links": [
                {
                    "backref": "subjects",
                    "label": "part_of",
                    "multiplicity": "many_to_one",
                    "name": "projects",
                    "required": True,
                    "target_type": "project"
                }
            ]
        },
        "sample.yaml": {
            "id": "sample",
            "links": [
                {
                    "backref": "samples",
                    "label": "taken_from",
                    "multiplicity": "many_to_one",
                    "name": "subjects",
                    "required": True,
                    "target_type": "subject"
                }
            ]
        }
    }
    dd.nodes = ["subject.yaml", "sample.yaml"]

    dd.calculate_node_order()

    # Check that node_pairs and node_order are set correctly
    assert dd.node_pairs == [("project", "subject"), ("subject", "sample")]
    assert dd.node_order == ["project", "subject", "sample"]