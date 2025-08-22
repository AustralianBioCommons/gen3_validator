import pytest
import pandas as pd
import json
from gen3_validator.resolve_schema import ResolveSchema
from unittest.mock import patch, MagicMock, mock_open
import os


@pytest.fixture
def test_schema_path():
    return "../../schema/gen3_test_schema.json"

def test_init_ResolveSchema(test_schema_path):
    schema = ResolveSchema(test_schema_path)
    assert schema.schema_path == test_schema_path

@pytest.fixture
def ResolveSchema_instance(test_schema_path):
    return ResolveSchema(test_schema_path)


def test_read_json(ResolveSchema_instance, test_schema_path):
    mock_data = [{"submitter_id": "subject-example-990910001"}]
    with patch("gen3_validator.dict.open",
               mock_open(read_data=json.dumps(mock_data))):
        result = ResolveSchema_instance.read_json(test_schema_path)
        assert result == mock_data


def test_get_nodes(ResolveSchema_instance):
    schema = {
        "sample": "schema_content",
        "medication": "schema_content"
    }
    ResolveSchema_instance.schema = schema
    result = ResolveSchema_instance.get_nodes()
    assert result == ["sample", "medication"]


def test_get_node_link(ResolveSchema_instance):
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
    ResolveSchema_instance.schema = schema
    result = ResolveSchema_instance.get_node_link("sample.yaml")
    assert result == ("sample", links)


def test_get_node_category(ResolveSchema_instance):
    schema = {
        "demographic.yaml": {
            "id": "demographic",
            "category": "clinical"
        }
    }
    ResolveSchema_instance.schema = schema
    node_id, category = ResolveSchema_instance.get_node_category("demographic.yaml")
    assert node_id == "demographic"
    assert category == "clinical"


def test_get_node_properties(ResolveSchema_instance):
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
    ResolveSchema_instance.schema = schema
    node_id, property_keys = ResolveSchema_instance.get_node_properties("demographic.yaml")
    assert node_id == "demographic"
    assert set(property_keys) == {"sex"}


def test_generate_node_lookup(ResolveSchema_instance):
    # Prepare a mock schema with multiple nodes, including excluded ones
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

    ResolveSchema_instance.schema = schema
    ResolveSchema_instance.nodes = ['demographic.yaml', '_definitions.yaml']
    node_lookup = ResolveSchema_instance.generate_node_lookup()
    assert node_lookup == expected


def test_find_upstream_downstream(ResolveSchema_instance):
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
    ResolveSchema_instance.schema = schema
    node_pairs = ResolveSchema_instance._find_upstream_downstream("sample.yaml")
    assert node_pairs == [("subject", "sample")]

def test_get_all_node_pairs(ResolveSchema_instance):
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
    ResolveSchema_instance.schema = schema
    ResolveSchema_instance.nodes = ["sample.yaml", "medication.yaml"]
    node_pairs = ResolveSchema_instance.get_all_node_pairs()
    assert node_pairs == [("subject", "sample"), ("subject", "medication")]


def test_get_node_order(ResolveSchema_instance):
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
    ResolveSchema_instance.schema = schema
    ResolveSchema_instance.nodes = ["subject.yaml", "sample.yaml"]
    node_pairs = ResolveSchema_instance.get_all_node_pairs()
    node_order = ResolveSchema_instance.get_node_order(node_pairs)
    assert node_order == ['project', 'subject', 'sample']
    

    # INSERT_YOUR_CODE
def test_split_json(ResolveSchema_instance):
    # Prepare a mock schema with three nodes
    schema = {
        "subject.yaml": {"id": "subject", "type": "object"},
        "sample.yaml": {"id": "sample", "type": "object"},
        "project.yaml": {"id": "project", "type": "object"},
    }
    ResolveSchema_instance.schema = schema
    ResolveSchema_instance.nodes = ["subject.yaml", "sample.yaml", "project.yaml"]

    # Call split_json and check the result
    result = ResolveSchema_instance.split_json()
    expected = [
        {"id": "subject", "type": "object"},
        {"id": "sample", "type": "object"},
        {"id": "project", "type": "object"},
    ]
    assert result == expected


def test_return_schema(ResolveSchema_instance):
    # Prepare a mock schema_list with several node dicts
    schema_list = [
        {"id": "subject", "type": "object"},
        {"id": "sample", "type": "object"},
        {"id": "project", "type": "object"},
    ]
    ResolveSchema_instance.schema_list = schema_list

    # Test with id without .yaml
    result = ResolveSchema_instance.return_schema("sample")
    assert result == {"id": "sample", "type": "object"}

    # Test with id with .yaml
    result = ResolveSchema_instance.return_schema("project.yaml")
    assert result == {"id": "project", "type": "object"}

    # Test with id that does not exist
    result = ResolveSchema_instance.return_schema("not_a_node")
    assert result is None

    # Test with id with .yaml that does not exist
    result = ResolveSchema_instance.return_schema("not_a_node.yaml")
    assert result is None



def test_resolve_references(ResolveSchema_instance):
    # Prepare a mock schema and reference with a $ref to _definitions.yaml
    schema = {
        "subject.yaml": {
            "id": "subject",
            "type": "object",
            "properties": {
                "foo": {"$ref": "_definitions.yaml#/bar"}
            }
        },
        "_definitions.yaml": {
            "bar": {
                "type": "string",
                "description": "A bar property"
            }
        }
    }
    # The reference schema should be the resolved _definitions.yaml
    reference = schema["_definitions.yaml"]

    # Test resolving the $ref in subject.yaml
    resolved = ResolveSchema_instance.resolve_references(
        schema["subject.yaml"], reference
    )
    # The "foo" property should be replaced with the resolved definition
    assert "foo" in resolved["properties"]
    assert resolved["properties"]["foo"]["type"] == "string"
    assert resolved["properties"]["foo"]["description"] == "A bar property"
    # The rest of the schema should be preserved
    assert resolved["id"] == "subject"
    assert resolved["type"] == "object"


def test_schema_list_to_json(ResolveSchema_instance):
    # Prepare a mock schema list
    schema_list = [
        {"id": "subject", "type": "object"},
        {"id": "project", "type": "object"},
        {"id": "sample", "type": "object"},
    ]
    # Call the method
    result = ResolveSchema_instance.schema_list_to_json(schema_list)
    # Check that the result is a dict with the correct keys and values
    assert isinstance(result, dict)
    assert set(result.keys()) == {"subject.yaml", "project.yaml", "sample.yaml"}
    assert result["subject.yaml"] == {"id": "subject", "type": "object"}
    assert result["project.yaml"] == {"id": "project", "type": "object"}
    assert result["sample.yaml"] == {"id": "sample", "type": "object"}

    # Test that schemas without an 'id' key are skipped
    schema_list_with_missing_id = [
        {"id": "subject", "type": "object"},
        {"type": "object"},  # No id
    ]
    result = ResolveSchema_instance.schema_list_to_json(schema_list_with_missing_id)
    assert "subject.yaml" in result
    assert len(result) == 1

def test_resolve_all_references(ResolveSchema_instance):
    # Prepare a mock schema with $ref in properties and a definitions node
    schema = {
        "sample.yaml": {
            "id": "sample",
            "type": "object",
            "properties": {
                "$ref": "_definitions.yaml#/ubiquitous_properties",
                "sample_id": {
                    "type": "string"
                }
            }
        },
        "subject.yaml": {
            "id": "subject",
            "type": "object",
            "properties": {
                "$ref": "_definitions.yaml#/ubiquitous_properties",
                "subject_id": {
                    "type": "string"
                }
            }
        },
        "_definitions.yaml": {
            "ubiquitous_properties": {
                "created_at": {
                    "type": "string",
                    "description": "Creation timestamp"
                },
                "updated_at": {
                    "type": "string",
                    "description": "Update timestamp"
                }
            }
        },
        "_terms.yaml": None  # Should be skipped
    }
    # Set up the instance
    ResolveSchema_instance.schema = schema
    ResolveSchema_instance.schema_def_resolved = schema["_definitions.yaml"]
    ResolveSchema_instance.nodes = list(schema.keys())

    # Call the method
    resolved_list = ResolveSchema_instance.resolve_all_references()

    # There should be two resolved schemas (sample.yaml and subject.yaml)
    assert isinstance(resolved_list, list)
    assert len(resolved_list) == 2

    # Check that the $ref in properties is resolved for both nodes
    for resolved in resolved_list:
        assert "properties" in resolved
        # The resolved properties should include the ubiquitous_properties keys
        assert "created_at" in resolved["properties"]
        assert "updated_at" in resolved["properties"]
        # The node-specific property should also be present
        if resolved["id"] == "sample":
            assert "sample_id" in resolved["properties"]
        elif resolved["id"] == "subject":
            assert "subject_id" in resolved["properties"]


def test_return_resolved_schema(ResolveSchema_instance):
    # Prepare a resolved schema list with two nodes
    resolved_schema_list = [
        {
            "id": "sample",
            "type": "object",
            "properties": {
                "created_at": {"type": "string"},
                "updated_at": {"type": "string"},
                "sample_id": {"type": "string"}
            }
        },
        {
            "id": "subject",
            "type": "object",
            "properties": {
                "created_at": {"type": "string"},
                "updated_at": {"type": "string"},
                "subject_id": {"type": "string"}
            }
        }
    ]
    # Set the resolved schema list on the instance
    ResolveSchema_instance.schema_list_resolved = resolved_schema_list

    # Test with id with .yaml extension
    sample_schema = ResolveSchema_instance.return_resolved_schema("sample.yaml")
    assert sample_schema is not None
    assert sample_schema["id"] == "sample"
    assert "sample_id" in sample_schema["properties"]

    # Test with id without .yaml extension
    subject_schema = ResolveSchema_instance.return_resolved_schema("subject")
    assert subject_schema is not None
    assert subject_schema["id"] == "subject"
    assert "subject_id" in subject_schema["properties"]

    # Test with a non-existent id
    none_schema = ResolveSchema_instance.return_resolved_schema("not_a_node.yaml")
    assert none_schema is None


    # INSERT_YOUR_CODE
def test_get_schema_version(ResolveSchema_instance):
    # Prepare a schema dict with _settings.yaml and _dict_version
    schema = {
        "_settings.yaml": {
            "_dict_version": "3.0.1"
        },
        "sample.yaml": {
            "id": "sample"
        }
    }
    version = ResolveSchema_instance.get_schema_version(schema)
    assert version == "3.0.1"

    # Test with missing _settings.yaml
    schema_missing_settings = {
        "sample.yaml": {
            "id": "sample"
        }
    }
    try:
        ResolveSchema_instance.get_schema_version(schema_missing_settings)
        assert False, "Expected exception for missing _settings.yaml"
    except Exception as e:
        assert "Could not pull schema version" in str(e) or isinstance(e, KeyError)

    # Test with missing _dict_version
    schema_missing_version = {
        "_settings.yaml": {},
        "sample.yaml": {
            "id": "sample"
        }
    }
    try:
        ResolveSchema_instance.get_schema_version(schema_missing_version)
        assert False, "Expected exception for missing _dict_version"
    except Exception as e:
        assert "Could not pull schema version" in str(e) or isinstance(e, KeyError)



def test_resolve_schema(monkeypatch, ResolveSchema_instance):
    # Prepare a mock schema dict with all required keys
    schema = {
        "_settings.yaml": {
            "_dict_version": "3.1.0"
        },
        "_definitions.yaml": {
            "some_def": {"type": "string"}
        },
        "_terms.yaml": {
            "term1": "definition"
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
            ],
            "properties": {
                "sample_id": {"type": "string"}
            }
        },
        "subject.yaml": {
            "id": "subject",
            "properties": {
                "subject_id": {"type": "string"}
            }
        }
    }

    # Patch read_json to return our schema
    monkeypatch.setattr(ResolveSchema_instance, "read_json", lambda path: schema)
    # Patch get_nodes to return the node keys
    monkeypatch.setattr(ResolveSchema_instance, "get_nodes", lambda: list(schema.keys()))
    # Patch get_all_node_pairs to use the real method (it uses self.schema and self.nodes)
    # Patch split_json to return a list of node dicts (excluding _definitions.yaml and _terms.yaml)
    def fake_split_json():
        return [schema[k] for k in schema if k.endswith(".yaml") and not k.startswith("_")]
    monkeypatch.setattr(ResolveSchema_instance, "split_json", fake_split_json)
    # Patch return_schema to return the relevant dict
    monkeypatch.setattr(ResolveSchema_instance, "return_schema", lambda k: schema.get(k))
    # Patch resolve_references to just return the input schema for simplicity
    monkeypatch.setattr(ResolveSchema_instance, "resolve_references", lambda s, t: s)
    # Patch schema_list_to_json to just return the input list
    monkeypatch.setattr(ResolveSchema_instance, "schema_list_to_json", lambda l: l)

    # Now call resolve_schema
    ResolveSchema_instance.resolve_schema()

    # Check that the attributes are set as expected
    assert ResolveSchema_instance.schema == schema
    assert set(ResolveSchema_instance.nodes) == set(schema.keys())
    assert isinstance(ResolveSchema_instance.node_pairs, list)
    assert isinstance(ResolveSchema_instance.node_order, list)
    assert isinstance(ResolveSchema_instance.schema_list, list)
    assert ResolveSchema_instance.schema_def == schema["_definitions.yaml"]
    assert ResolveSchema_instance.schema_term == schema["_terms.yaml"]
    assert ResolveSchema_instance.schema_def_resolved == schema["_definitions.yaml"]
    assert isinstance(ResolveSchema_instance.schema_list_resolved, list)
    assert ResolveSchema_instance.schema_resolved == ResolveSchema_instance.schema_list_resolved
    assert ResolveSchema_instance.schema_version == "3.1.0"
