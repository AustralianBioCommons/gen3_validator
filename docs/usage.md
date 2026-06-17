# Data Validation
- Validating json data objects to the gen3jsonschema
- To validate data, the gen3 jsonschema must first be resovled using the special software built into gen3_validator


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



## Bulk Folder Validation
- Validates a whole folder of per-node JSON files against the Gen3 schema, processing each node in the sequence given by a data import order file.
- Reuses the same schema validation as `validate_list_dict` for each node, and (by default) additionally checks **reference integrity** between nodes — that every link points to a record that exists. See [Link / reference integrity](#link--reference-integrity) below.

### Expected folder layout
A folder contains one `<node>.json` file per node plus an import order file:

```
my_submission/
├── DataImportOrder.txt      # node names, one per line, in the order to process them
├── project.json             # a single JSON object  (one record)
├── subject.json             # a JSON array of record objects
└── ... one <node>.json per node
```

- Each `<node>.json` is either a JSON **array** of records or a **single object** (e.g. `project.json`); a single object is normalised to a one-record list.
- Every record must carry a `"type"` field equal to its node name.
- `DataImportOrder.txt` lists node names, one per line. A numbered format (`1<TAB>project`, `2<TAB>subject`, ...) is also accepted; blank lines and `#` comments are ignored.

### Functions
The `bulk.py` module provides:

- `parse_import_order(order_file_path)` — Parse the import order file into an ordered list of node names. Tolerates plain names (one per line) and the numbered format. Raises `FileNotFoundError` if the file is missing (it is mandatory).
- `load_node_records(file_path)` — Read a single `<node>.json` file and normalise it to a list of record dicts (a single object becomes `[object]`). Raises `ValueError` if the top-level JSON is neither an object nor an array.
- `validate_data_folder(folder_path, resolved_schema, import_order_filename="DataImportOrder.txt", check_links=True)` — Core validator. Takes an already-resolved schema dict (e.g. `ResolveSchema(...).schema_resolved`) and returns the flat report. Set `check_links=False` to validate schemas only.
- `validate_data_folder_from_schema(folder_path, schema_path, import_order_filename="DataImportOrder.txt", check_links=True)` — Convenience wrapper that resolves the schema from a path and then calls `validate_data_folder`.

These helpers support link checking (see below):

- `extract_links(node_schema)` — Flatten a resolved node schema's `links` (including `subgroup` wrappers) into a list of `{"name", "target_type"}` descriptors.
- `build_identifier_index(node_records)` — Build `{node: {id_key: {values}}}` from the loaded records so references can be resolved quickly. Every loaded node gets an entry, so a present-but-empty node is distinguishable from an absent one.
- `validate_record_links(record, idx, node_name, links, index, warned=None)` — Check one record's link references against the index and return any link FAIL rows.

### Behaviour for non-ideal inputs
- A node listed in the import order with **no matching file** is skipped with a warning.
- A `*.json` file **present but not listed** in the import order is ignored with a warning.
- A node file that **cannot be loaded or validated** (invalid JSON, a record missing `"type"`, a node not in the schema) produces a single row with `validation_result: "ERROR"` and processing continues — one bad file never aborts the run.

### Link / reference integrity
When `check_links=True` (the default), the validator also checks that the links between nodes resolve.

- In Gen3 a child record links up to a parent via a property named after the parent (the link `name`, typically the parent pluralised — e.g. a `sample` links to a `clinical_descriptor` via `"clinical_descriptors"`). The resolved schema's `links` array provides the authoritative `name → target_type` mapping.
- A reference value is either a single object `{"submitter_id": "..."}` or an array of them. The identifier is usually `submitter_id`; `project` is referenced by `code`. A reference resolves if any identifier it carries matches a record in the target node.
- A link whose **target node is absent** from the folder (e.g. `project` → `program` with no `program.json`) is **skipped with a warning** — there is nothing to validate against. A link into a node that is **present but empty** is reported as a failure.
- Dangling references are reported as rows with `validator: "link"`, `invalid_key` set to the link property, and `validator_value` set to the target node:

```python
{
    'node': 'sample',
    'index': 0,
    'validation_result': 'FAIL',
    'invalid_key': 'clinical_descriptors',
    'schema_path': 'links',
    'validator': 'link',
    'validator_value': 'clinical_descriptor',
    'validation_error': "Link 'clinical_descriptors' references clinical_descriptor "
                        "'clinical_descriptor_MISSING' (by submitter_id) but no matching record "
                        "exists in clinical_descriptor.json",
    'source_file': 'sample.json'
}
```

### Example
```python
import gen3_validator

# Resolve the schema yourself and reuse it...
resolver = gen3_validator.ResolveSchema(schema_path="../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
results = gen3_validator.validate_data_folder("path/to/my_submission", resolver.schema_resolved)

# ...or do it in one call:
results = gen3_validator.validate_data_folder_from_schema(
    folder_path="path/to/my_submission",
    schema_path="../tests/schema/gen3_test_schema.json",
)

print(results)
```

**Output** — a single flat list of failures, ordered by import order. Each row matches the `validate_list_dict` output plus a `source_file` field:

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

### Command line
Installing the package exposes the `gen3-validate` command:

```bash
gen3-validate path/to/my_submission -s path/to/gen3_schema.json
```

Flags: `-s/--schema` (required), `--order-file` (default `DataImportOrder.txt`), `-o/--output` (write the JSON report to a file instead of stdout), `--no-link-check` (disable reference integrity checks; validate schemas only), `-v/--verbose`. Exit code is `0` when clean, `1` when any record is a FAIL/ERROR, and `2` for input errors (e.g. a missing import order file).


## Creating a Dictionary Instance
The `DataDictionary` class in `dict.py` provides tools to:

-  Reads a bundled json file which is a list of gen3 jsonschemas and load its contents with `read_json()`.
- Retrieve all node names (entities) defined in the schema using `get_nodes()`.
- Extract links for a node with `get_node_link()`, categories with `get_node_category()`, and properties with `get_node_properties()`.
- Generate a lookup dictionary of nodes with their categories and properties via `generate_node_lookup()`.
- Find upstream and downstream relationships between nodes using `_find_upstream_downstream()`.
- Get all node dependency pairs with `get_all_node_pairs()` and determine a topological order for data loading using `get_node_order()`.
- Split the schema into individual node schemas with `split_json()`.
- Retrieve a specific node schema by its ID using `return_schema()`.
- Convert a list of node schemas into a dictionary format with `schema_list_to_json()`.
- Extract the schema version from the loaded schema using `get_schema_version()`.
- Call orchestration methods like `parse_schema()` and `calculate_node_order()`, to populate internal class attributes for the `DataDictionary` class.

*Note: A node is defined as the entity name*

```python
# initialise
dd = gen3_validator.DataDictionary(schema_path = "../tests/schema/gen3_test_schema.json")

# Call the orchestration method
dd.parse_schema()
dd.schema
dd.schema_list

# Call the node orchestration method
dd.calculate_node_order()
dd.nodes
dd.node_pairs
dd.node_order

# You can also get a summary of node, node category, and the properties for each node wtih
dd.generate_node_lookup()
```



## Creating resolver Instance
- This class inherits methods from the `DataDictionary` class and provides tools to resolve the schema and return the resolved schema


```python
resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
```

You can return the resolved schema with


```python
resolver.schema_resolved
```


## Finding Node Paths in the Schema Graph
You can use the `get_min_node_path` function to find the shortest path between the root node and a target node in the schema graph.
- The `get_min_node_path` constructs a graph model from the edges, infers the root node if not provided, and finds the shortest path from the root node to the target node.

```python
from gen3_validator.dict import get_min_node_path

edges = [
    ("project", "subject"),
    ("subject", "sample"),
]
min_path = get_min_node_path(edges, "sample", ignore_nodes=[])
print("Minimum path to 'sample':", min_path.path)
print("Steps:", min_path.steps)
```

**Output:**
```
Minimum path to 'sample': ['project', 'subject', 'sample']
Steps: 2
```

