```python
import gen3_validator
from gen3_validator.logging_config import setup_logging
setup_logging()
```

## Reading in xlsx data and writing to json
- xlsx data comes from xlsx manifest file created from acdc_submission_template


```python
# resolverClass = gen3_validator.ResolveSchema(schema_path = "../schema/gen3_test_schema.json")
xlsxData = gen3_validator.ParseXlsxMetadata(xlsx_path = "gen3-validator/data/lipid_metadata_example.xlsx", skip_rows=1)
xlsxdata.parse_metadata_template()
xlsxdata.write_dict_to_json(xlsx_data_dict=xlsxdata.xlsx_data_dict, output_dir="gen3-validator/data/restricted/lipid_metadata_example")
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


## Parsing data
- The parse data class takes in a data folder path containing json files for each data node



```python
# Testing linkage for test data that passes
data = gen3_validator.ParseData(data_folder_path = "../tests/data/pass")
```

To list the files read into the Data instance, you can use the following code:


```python
data.file_path_list
```

All of the read data is stored in data.data_dict as a dictionary, where the key is the entity and the value is a list of json objects


```python
data.data_dict
```

The default link suffix is 's'
- This links suffix can be changed depending on what the key_name for the linked information is.


```python
data.link_suffix
```

For example, in the json object below, we can see that the key "subjects" is what describes the link from sample to subject, since the value of 'subjects' is an array containing the key "submitter_id".
- Furthermore, the backref is called 'subjects' while the entity is called 'sample'
- Therefore, the link suffix is 's'


```python
data.data_dict["sample"][0]
```

Finally, you can also check what the detected entities are below:


```python
data.data_nodes
```

## Testing Linkage

The first thing you should do is create a linkage configuration map. The `.generate_config` method will do this for you, it will read in the data (stored in the `data_dict` attribute) and return a linkage configuration map.

The linkage configuration map is a dictionary that maps each entity to a dictionary of its primary and foreign keys, with the format:

```
{
    "entity_name": {
        "primary_key": "primary_key_field",
        "foreign_key": "foreign_key_field"
    }
}
```

Also, you can define the linkage configuration map yourself, but you need to make sure that the primary and foreign keys are defined for each entity.


```python
import gen3_validator
data_pass = gen3_validator.ParseData(data_folder_path = "../tests/data/pass")
linkage_pass = gen3_validator.Linkage()
link_pass_config = linkage_pass.generate_config(data_pass.data_dict)
link_pass_config
```

Once you have the linkage configuration map, you can validate the links. The `.validate_links` method will do this for you, it will read in the data and the linkage configuration map then return a dictionary of the linkage validation results.

As a reminder, the data parsed to the `.validate_links` method as the `data_map` argument, has the format:

```python
{
    "entity_name_1": [
        {
            "field_name": "field_value"
        },
        {
            "field_name": "field_value"
        }
    ],
    "entity_name_2": [
        {
            "field_name": "field_value"
        },
        {
            "field_name": "field_value"
        }
    ]
}
```
Where `entity_name_1` and `entity_name_2` are the names of the entities in the data, and value is a list of json objects, each representing a record in the entity.


```python
import gen3_validator
data_pass = gen3_validator.ParseData(data_folder_path = "../tests/data/pass")
linkage_pass = gen3_validator.Linkage()
link_pass_config = linkage_pass.generate_config(data_pass.data_dict)
linkage_pass.validate_links(data_map = data_pass.data_dict, config = link_pass_config, root_node = 'subject')
```

Testing linkage for test data that fails:
- Note that the `root_node` argument tells the validate_links method which entitie is a root node, therefore will not have any upstream links.


```python
data_fail = gen3_validator.ParseData(data_folder_path = "../tests/data/fail")
linkage_fail = gen3_validator.Linkage()
link_fail_config = linkage_fail.generate_config(data_fail.data_dict)
linkage_fail.validate_links(data_map = data_fail.data_dict, config = link_fail_config, root_node = 'subject')
```

You can check the json files read into the data_fail instance


```python
data_fail.file_path_list
```

This returns all of the foreign keys that are not linked to a primary key


```python
linkage_fail.link_validation_results
```

# Data Validation
- Validating json data objects to the gen3jsonschema


Creating the validation class
- You will need to preload the data under the `data_map` attribute and the resolved schema under the `resolved_schema` attribute in the `Validate` class.


```python
import gen3_validator

resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
data = gen3_validator.ParseData(data_folder_path = "../tests/data/fail")
validator = gen3_validator.Validate(data_map=data.data_dict, resolved_schema=resolver.schema_resolved)

```

You can call the orchestrator method to run the validation pipeline with `.validate_schema`


```python
validator.validate_schema()
```

What is returned is a data structure in the following format:

```python
{
    'entity_name': [
        {
            'row_index_number': [
                {
                    'index': 0, # this is the index of the row in the entity
                    'invalid_key': 'this_is_the_column_name',
                    'validation_result': 'FAIL',
                    'schema_path': 'this_is_the_path_to_the_property_in_the_schema',
                    'validator': 'the_target_data_type',
                    'validator_value': 'the_correct_value',
                    'validation_error': 'this_is_the_validation_error_message'
                },
                {
                    'index': 0, # this is the index of the row in the entity
                    'invalid_key': 'same_row_validation_error_in_another_column',
                    'validation_result': 'FAIL',
                    'schema_path': 'this_is_the_path_to_the_property_in_the_schema',
                    'validator': 'the_target_data_type',
                    'validator_value': 'the_correct_value',
                    'validation_error': 'this_is_the_validation_error_message'
                }
            ]
        }
    ],
    'metabolomics_file': [
        {
            'index_0': [
                {'index': 0, # error in first row
                'validation_result': 'FAIL',
                'invalid_key': 'data_format', # error in column called data_format
                'schema_path': 'properties.data_format.enum',
                'validator': 'enum',
                'validator_value': ['wiff'],
                'validation_error': "True is not one of ['wiff']"
                },
                {'index': 0, # error in first row
                'validation_result': 'FAIL',
                'invalid_key': 'data_type', # error in column called data_type
                'schema_path': 'properties.data_type.enum',
                'validator': 'enum',
                'validator_value': ['MS', 'MS/MS'],
                'validation_error': "'1' is not one of ['MS', 'MS/MS']"
                }
            ]
        },
        {
            'index_1': [
                {
                    'index': 1, # error in second row
                    'validation_result': 'FAIL',
                    'invalid_key': 'data_format', # error in column called data_format
                    'schema_path': 'properties.data_format.enum',
                    'validator': 'enum',
                    'validator_value': ['wiff'],
                    'validation_error': "True is not one of ['wiff']"
                }
            ]
        }
    ]
}


     
```

Lets say we want to pull the validation results for a specific entity, at a specific row / index:
- `result_type` can either be `['ALL', 'FAIL', 'PASS']`
- This will return a list of json objects, each representing a validation result for a specific row in the entity


```python
validator.pull_index_of_entity(entity="sample", index_key=0, result_type="ALL")
```

You can print what entites were validated by using the `.list_entities` method.


```python
validator.list_entities()
```

if you want to see the row / index names of an entity you can use the `.list_index_by_entity` method:


```python
validator.list_index_by_entity("sample")
```

You can pull out a validation results for a specific entity with the `.pull_entity` method


```python
validator.pull_entity("sample")
```


```python
len(validator.pull_entity("sample"))
```

You can pull validation results for a specific entity and then a specific index / row with the `pull_index_of_entity` method.


```python
validator.pull_index_of_entity("sample", 0)
```

# Getting validation stats
- The `ValidateStats` class is used to get summary statistics and data frames of the validation results.

First we create a validator object and validate the data with the schema using the `validate_schema` method.


```python
import gen3_validator
from gen3_validator.logging_config import setup_logging
setup_logging(level="INFO")

resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
data = gen3_validator.ParseData(data_folder_path = "../tests/data/fail")
validator = gen3_validator.Validate(data_map=data.data_dict, resolved_schema=resolver.schema_resolved)
validator.validate_schema()
```

We then pass the validator instance to the `ValidateStats` class to get the summary statistics and data frames of the validation results which are stored in the `validation_result` attribute of the validator instance.


```python
validate_stats = gen3_validator.ValidateStats(validator)
```

To get a high level summary we can call the `.summary_stats` method on the `ValidateStats` instance.


```python
validate_stats.summary_stats()
```

There are several other methods in the `ValidateStats` class that provide detailed metrics about your validation results:

- `n_rows_with_errors(entity)`: Returns the number of rows (entries) with at least one validation error for a given entity.
- `n_errors_per_entry(entity, index_key)`: Returns the number of validation errors for a specific row (by index) within an entity.
- `count_results_by_entity(entity, result_type="FAIL")`: Counts the number of validation results of a specific type (e.g., "FAIL", "PASS", or "ALL") for an entity.
- `count_results_by_index(entity, index_key, result_type="FAIL")`: Counts the number of validation results of a specific type for a specific row (by index) within an entity.
- `total_validation_errors()`: Returns the total number of validation errors across all entities.
These methods allow you to drill down into the validation results and generate custom summaries or reports as needed.


```python

# Usage examples for ValidateStats methods

entity = "sample"

rows_with_errors = validate_stats.n_rows_with_errors(entity)
print(f"Number of rows with errors for entity '{entity}': {rows_with_errors}")

index_key = 0
errors_per_entry = validate_stats.n_errors_per_entry(entity, index_key)
print(f"Number of errors for entity '{entity}' at index {index_key}: {errors_per_entry}")

fail_count = validate_stats.count_results_by_entity(entity, result_type="FAIL")
print(f"Total number of FAIL results for entity '{entity}': {fail_count}")

pass_count = validate_stats.count_results_by_entity(entity, result_type="PASS")
print(f"Total number of PASS results for entity '{entity}': {pass_count}")

all_count = validate_stats.count_results_by_entity(entity, result_type="ALL")
print(f"Total number of validation results for entity '{entity}': {all_count}")

fail_count_index = validate_stats.count_results_by_index(entity, index_key, result_type="FAIL")
print(f"Number of FAIL results for entity '{entity}' at index {index_key}: {fail_count_index}")

total_errors = validate_stats.total_validation_errors()
print(f"Total number of validation errors: {total_errors}")

summary_df = validate_stats.summary_stats()
print("Summary statistics DataFrame:")
print(summary_df)

```

# Creating validation summary data
- We can also pass the validator instance to the `ValidateSummary` class to get a flattened summary of the validation results.

Creating ValidateSummary instance


```python
import gen3_validator
from gen3_validator.logging_config import setup_logging
setup_logging(level="INFO")

resolver = gen3_validator.ResolveSchema(schema_path = "../tests/schema/gen3_test_schema.json")
resolver.resolve_schema()
data = gen3_validator.ParseData(data_folder_path = "../tests/data/fail")
validator = gen3_validator.Validate(data_map=data.data_dict, resolved_schema=resolver.schema_resolved)
validator.validate_schema() # make sure validation has been run by calling .validate_schema()

summary = gen3_validator.ValidateSummary(validator) 

```

This returns the validation results in a flattened dictionary format.


```python
summary.flatten_validation_results()
```

This returns the validation results in a flattened pandas dataframe.


```python
summary.flattened_results_to_pd()
```

Finally you can also create an aggreated summary of the flattened validation results with:


```python
summary.collapse_flatten_results_to_pd()
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

