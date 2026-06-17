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

## Bulk Folder Validation

Instead of assembling a list of objects by hand, you can point Gen3 Validator at a **folder** that
holds one JSON file per node plus a data import order file, and it will validate every node **in
import order**, reusing the same schema validation shown above. It also checks the **links between
nodes** (reference integrity) by default — see [below](#link--reference-integrity).

### Expected folder layout

```
my_submission/
├── DataImportOrder.txt      # node names, one per line, in the order to process them
├── project.json             # a single JSON object  (one record)
├── subject.json             # a JSON array of record objects
├── sample.json
└── ... one <node>.json per node
```

- Each `<node>.json` is either a JSON **array** of records or a **single object** (e.g.
  `project.json`); single objects are treated as a one-record list.
- Every record must carry a `"type"` field equal to its node name (same requirement as the
  in-memory API).
- `DataImportOrder.txt` lists node names, one per line. A numbered format
  (`1<TAB>project`, `2<TAB>subject`, ...) is also accepted.

### Python API

```python
import gen3_validator

# Convenience: resolve the schema from a path and validate the folder in one call.
results = gen3_validator.validate_data_folder_from_schema(
    folder_path="path/to/my_submission",
    schema_path="path/to/gen3_schema.json",
)

# Or, if you already have a resolved schema, reuse it:
resolver = gen3_validator.ResolveSchema(schema_path="path/to/gen3_schema.json")
resolver.resolve_schema()
results = gen3_validator.validate_data_folder("path/to/my_submission", resolver.schema_resolved)
```

The output is a single **flat list** of failures, ordered by import order. Each row is the same
shape as the in-memory validator's output plus a `source_file` field naming the file the record came
from:

```python
[
    {
        'node': 'project',
        'index': 0,                       # index of the record within its node file
        'validation_result': 'FAIL',
        'invalid_key': 'root',
        'schema_path': 'additionalProperties',
        'validator': 'additionalProperties',
        'validator_value': False,
        'validation_error': "Additional properties are not allowed ('data_release', 'data_release_date' were unexpected)",
        'source_file': 'project.json'
    },
    ...
]
```

A node listed in the import order with no matching file is skipped with a warning, and a `*.json`
file not listed in the import order is ignored with a warning. If a node file cannot be loaded or
validated (invalid JSON, a record missing `"type"`, etc.) a single row with
`'validation_result': 'ERROR'` is emitted for that node and processing continues — one bad file never
aborts the run.

### Link / reference integrity

By default the folder validator also checks that the **links between nodes resolve**: for every
record, each link reference must point to a record that actually exists in the target node's file.
In Gen3 a child links up to a parent via a property named after the parent (e.g. a `sample` links to
a `clinical_descriptor` via `"clinical_descriptors": {"submitter_id": "..."}`), and the reference may
be a single object or an array of them. Most nodes are referenced by `submitter_id`; `project` is
referenced by `code`.

A dangling reference is reported as a row with `validator: "link"`:

```python
{
    'node': 'sample',
    'index': 0,                       # index of the record within its node file
    'validation_result': 'FAIL',
    'invalid_key': 'clinical_descriptors',   # the link property
    'schema_path': 'links',
    'validator': 'link',
    'validator_value': 'clinical_descriptor',  # the target node
    'validation_error': "Link 'clinical_descriptors' references clinical_descriptor "
                        "'clinical_descriptor_MISSING' (by submitter_id) but no matching record "
                        "exists in clinical_descriptor.json",
    'source_file': 'sample.json'
}
```

Rules:
- A link whose **target node is absent** from the folder (e.g. `project` links to `program`, but
  there is no `program.json`) is **skipped with a warning** — there is nothing to validate against.
- A link into a node that is **present but empty** is reported as a failure.
- Disable link checking with the `check_links=False` parameter (Python API) or the `--no-link-check`
  flag (CLI) to validate schemas only.

```python
results = gen3_validator.validate_data_folder_from_schema(
    folder_path="path/to/my_submission",
    schema_path="path/to/gen3_schema.json",
    check_links=False,   # schema validation only
)
```

### Command line

Installing the package also exposes a `gen3-validate` command:

```bash
gen3-validate path/to/my_submission -s path/to/gen3_schema.json
```

| Flag | Description |
|------|-------------|
| `-s`, `--schema` | Path to the Gen3 JSON schema (required). |
| `--order-file`   | Import order filename within the folder (default `DataImportOrder.txt`). |
| `-o`, `--output` | Write the JSON report to a file instead of stdout. |
| `--no-link-check`| Disable cross-node reference integrity checks (validate schemas only). |
| `-v`, `--verbose`| Verbose (INFO-level) logging. |

The report is printed as JSON to stdout (or written with `-o`). The exit code is `0` when the folder
is clean, `1` when any record is a FAIL or ERROR, and `2` for input errors (e.g. a missing import
order file). This makes it convenient as a pass/fail gate in scripts and CI.

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
