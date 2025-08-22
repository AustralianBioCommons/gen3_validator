import pytest
from gen3_validator.resolve_schema import ResolveSchema


@pytest.fixture
def test_schema_path():
    return "../../schema/gen3_test_schema.json"


def test_init_ResolveSchema(test_schema_path):
    schema = ResolveSchema(test_schema_path)
    assert schema.schema_path == test_schema_path


@pytest.fixture
def ResolveSchema_instance(test_schema_path):
    return ResolveSchema(test_schema_path)


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

    # Patch split_json to return a list of node dicts (excluding _definitions.yaml and _terms.yaml)
    def fake_split_json():
        return [schema[k] for k in schema if k.endswith(".yaml") and not k.startswith("_")]

    monkeypatch.setattr(ResolveSchema_instance, "split_json", fake_split_json)
    # Patch return_schema to return the relevant dict
    monkeypatch.setattr(ResolveSchema_instance, "return_schema", lambda k: schema.get(k))
    # Patch resolve_references to just return the input schema for simplicity
    monkeypatch.setattr(ResolveSchema_instance, "resolve_references", lambda s, t: s)
    # Patch convert resolved schema list to json format
    monkeypatch.setattr(ResolveSchema_instance, "schema_list_to_json", lambda s: s)
    # Now call resolve_schema
    ResolveSchema_instance.resolve_schema()

    # Check that the attributes are set as expected
    assert ResolveSchema_instance.schema == schema
    assert isinstance(ResolveSchema_instance.schema_list, list)
    assert ResolveSchema_instance.schema_def == schema["_definitions.yaml"]
    assert ResolveSchema_instance.schema_term == schema["_terms.yaml"]
    assert ResolveSchema_instance.schema_def_resolved == schema["_definitions.yaml"]
    assert isinstance(ResolveSchema_instance.schema_list_resolved, list)
    assert ResolveSchema_instance.schema_resolved == ResolveSchema_instance.schema_list_resolved

