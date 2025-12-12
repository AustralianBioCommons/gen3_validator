```python
import gen3_validator
```

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


# Data Validation
- Validating json data objects to the gen3jsonschema



```python
import gen3_validator

resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
schema = resolver.schema_resolved

data = [
    {
        "alternate_timepoint": "1f56770b0b",
        "baseline_timepoint": true,
        "freeze_thaw_cycles": 10,
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
        "alternate_timepoint": "da9b7324c3",
        "baseline_timepoint": true,
        "freeze_thaw_cycles": 76,
        "sample_collection_method": "e2a6403b51",
        "sample_id": "b19a9545df",
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

