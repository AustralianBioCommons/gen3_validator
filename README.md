# Gen3 Validator

**Gen3 Validator** is a Python toolkit designed to make working with Gen3 metadata schemas and data validation straightforward for developers.

## Installation
```bash
pip install gen3_validator
pip show gen3_validator
```

## Docs
- [example usage](https://github.com/AustralianBioCommons/gen3_validator/blob/main/docs/usage.md)


## Quickstart
```python
import gen3_validator

resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
schema = resolver.schema_resolved

data = [
    {
        "baseline_timepoint": True, # variable not in data dictionary
        "freeze_thaw_cycles": "10", # should be an integer
        "sample_collection_method": "2fddbe7d09",
        "sample_id": "d4f31f7bb6",
        "sample_in_preservation": "snap Frozen",
        "sample_in_storage": "yes",
        "sample_provider": "USYD",
        "sample_source": "UBERON:3781554",
        "sample_storage_method": "not stored",
        "sample_type": "59a8fd8005",
        "storage_location": "UMELB",
        "subjects": {
            "submitter_id": "subject_e5616257f8"
        },
        "submitter_id": "sample_efdbe56d20",
        "type": "sample"
    },
    {
        "baseline_timepoint": True, 
        "freeze_thaw_cycles": 76,
        "sample_collection_method": "e2a6403b51",
        "sample_id": 3324635, # should be a string
        "sample_in_preservation": "not allowed to collect",
        "sample_in_storage": "unknown",
        "sample_provider": "USYD",
        "sample_source": "UBERON:9332357",
        "sample_storage_method": "frozen, liquid nitrogen",
        "sample_type": "8fd28ec2f3",
        "storage_location": "Baker",
        "subjects": {
            "submitter_id": "subject_071bc3e81a"
        },
        "submitter_id": "sample_f7645c1221",
        "type": "sample"
    }
]
results = gen3_validator.validate.validate_list_dict(data, schema)

print(results)
```

Example output:

```python
[
    {
        'node': 'sample',
        'index': 0,
        'validation_result': 'FAIL',
        'invalid_key': 'freeze_thaw_cycles',
        'schema_path': 'properties.freeze_thaw_cycles.type',
        'validator': 'type',
        'validator_value': 'integer',
        'validation_error': "'10' is not of type 'integer'"
    },
    {
        'node': 'sample',
        'index': 0,
        'validation_result': 'FAIL',
        'invalid_key': 'root',
        'schema_path': 'additionalProperties',
        'validator': 'additionalProperties',
        'validator_value': False,
        'validation_error': "Additional properties are not allowed ('baseline_timepoint', 'subjects' were unexpected)"
    },
    {
        'node': 'sample',
        'index': 1,
        'validation_result': 'FAIL',
        'invalid_key': 'sample_id',
        'schema_path': 'properties.sample_id.type',
        'validator': 'type',
        'validator_value': 'string',
        'validation_error': "3324635 is not of type 'string'"
    },
    {
        'node': 'sample',
        'index': 1,
        'validation_result': 'FAIL',
        'invalid_key': 'root',
        'schema_path': 'additionalProperties',
        'validator': 'additionalProperties',
        'validator_value': False,
        'validation_error': "Additional properties are not allowed ('baseline_timepoint', 'subjects' were unexpected)"
    }
]

```

---

## Dev Setup
1. Make sure you have [poetry](https://python-poetry.org/docs/#installing-with-pipx) installed.
2. Clone the repository.
3. Run the following command to activate the virtual environment.
```bash
eval $(poetry env activate)
```
4. Run the following command to install the dependencies.
```bash
poetry install
```
5. Run the following command to run the tests.
```bash
pytest -vv tests/
```
---

## License

See the [license](LICENSE) page for more information.
