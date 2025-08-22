import json
from collections import defaultdict, deque
import logging

from gen3_validator.dict import DataDictionary

logger = logging.getLogger(__name__)

class ResolveSchema(DataDictionary):
    def __init__(self, schema_path: str):
        """
        Initialize the ResolveSchema class.

        Parameters:
        - schema_path (str): The path to the JSON schema file.
        """
        super().__init__(schema_path)
        logger.info(f"Initializing ResolveSchema with schema path: {schema_path}")
        self.schema = None
        self.nodes = None
        self.schema_list = None
        self.schema_def = None
        self.schema_term = None
        self.schema_def_resolved = None
        self.schema_list_resolved = None
        self.schema_resolved = None
        self.schema_version = None

    def resolve_references(self, schema: dict, reference: dict) -> dict:
        """
        Takes a gen3 jsonschema draft 4 as a dictionary and recursively
        resolves any references using a reference schema which has no
        references.

        Parameters:
        - schema (dict): The JSON node to resolve references in.
        - reference (dict): The schema containing the references.

        Returns:
        - dict: The resolved JSON node with references resolved.
        """
        logger.info("Resolving references in schema.")
        ref_input_content = reference

        def resolve_node(node, manual_ref_content=ref_input_content):
            try:
                if isinstance(node, dict):
                    if "$ref" in node:
                        ref_path = node["$ref"]
                        ref_file, ref_key = ref_path.split("#")
                        ref_file = ref_file.strip()
                        ref_key = ref_key.strip("/")

                        # if a reference file is in the reference, load the pre-defined reference, if no file exists, then use the schema itself as reference
                        if ref_file:
                            ref_content = manual_ref_content
                        else:
                            ref_content = schema

                        for part in ref_key.split("/"):
                            ref_content = ref_content[part]

                        resolved_content = resolve_node(ref_content)
                        # Merge resolved content with the current node, excluding the $ref key
                        return {
                            **resolved_content,
                            **{k: resolve_node(v) for k, v in node.items() if k != "$ref"},
                        }
                    else:
                        return {k: resolve_node(v) for k, v in node.items()}
                elif isinstance(node, list):
                    return [resolve_node(item) for item in node]
                else:
                    return node
            except KeyError as e:
                logger.error(f"Missing key {e} while resolving references in node: {node}")
                raise
            except Exception as e:
                logger.error(f"Error resolving references in node: {e}")
                raise

        return resolve_node(schema)

    def resolve_all_references(self) -> list:
        """
        Resolves references in all other schema dictionaries using the resolved definitions schema.

        Returns:
        - list: A list of resolved schema dictionaries.
        """
        logger.info("Resolving all references in schema list.")
        logger.info("=== Resolving Schema References ===")

        resolved_schema_list = []
        for node in self.nodes:
            if node == "_definitions.yaml" or node == "_terms.yaml":
                continue

            try:
                resolved_schema = self.resolve_references(
                    self.schema[node], self.schema_def_resolved
                )
                resolved_schema_list.append(resolved_schema)
                logger.info(f"Resolved {node}")
            except KeyError as e:
                logger.error(f"Error resolving {node}: Missing key {e}")
            except Exception as e:
                logger.error(f"Error resolving {node}: {e}")

        return resolved_schema_list

    def schema_list_to_json(self, schema_list: list) -> dict:
        """
        Converts a list of JSON schemas to a dictionary where each key is the schema id
        with '.yaml' appended, and the value is the schema content.

        Parameters:
        - schema_list (list): A list of JSON schemas.

        Returns:
        - dict: A dictionary with schema ids as keys and schema contents as values.
        """
        logger.info("Converting schema list to JSON format.")
        try:
            schema_dict = {}
            for schema in schema_list:
                schema_id = schema.get("id")
                if schema_id:
                    schema_dict[f"{schema_id}.yaml"] = schema
            return schema_dict
        except Exception as e:
            logger.error(f"Error converting schema list to JSON: {e}")
            raise
        
    # INSERT_YOUR_CODE
    def return_resolved_schema(self, schema_id: str) -> dict:
        """
        Retrieves the first dictionary from the resolved schema list where the 'id' key matches the schema_id.

        Parameters:
        - schema_id (str): The value of the 'id' key to match.

        Returns:
        - dict: The dictionary that matches the schema_id, or None if not found.
        """
        logger.info(f"Retrieving resolved schema for schema ID: {schema_id}")
        try:
            if schema_id.endswith(".yaml"):
                schema_id = schema_id[:-5]

            result = next(
                (item for item in self.schema_list_resolved if item.get("id") == schema_id), None
            )
            if result is None:
                logger.warning(f"{schema_id} not found in resolved schema list")
            return result
        except Exception as e:
            logger.error(f"Error retrieving resolved schema for {schema_id}: {e}")
            raise

    def resolve_schema(self):
        """
        Resolves and initializes all schema-related attributes for the instance.
        This method reads the schema, extracts nodes and their relationships,
        splits and resolves references, and sets the schema version.
        """
        logger.info("Starting schema resolution process.")
        # Step 1: Read the main schema JSON
        self.schema = self.read_json(self.schema_path)
        logger.info("Successfully read JSON schema.")

        # Step 2: Extract node information
        self.nodes = self.get_nodes()
        logger.info(f"Retrieved {len(self.nodes)} nodes from schema.")

        # Step 4: Split schema into individual node schemas
        self.schema_list = self.split_json()
        logger.info("Split schema into individual node schemas.")

        # Step 5: Retrieve definitions and terms schemas
        self.schema_def = self.return_schema("_definitions.yaml")
        logger.info("Retrieved definitions schema.")
        self.schema_term = self.return_schema("_terms.yaml")
        logger.info("Retrieved terms schema.")

        # Step 6: Resolve references in definitions
        self.schema_def_resolved = self.resolve_references(
            self.schema_def, self.schema_term
        )
        logger.info("Resolved references in definitions schema.")

        # Step 7: Resolve all references in schema list
        self.schema_list_resolved = self.resolve_all_references()
        logger.info("Resolved all references in schema list.")

        # Step 8: Convert resolved schema list to JSON format
        self.schema_resolved = self.schema_list_to_json(self.schema_list_resolved)
        logger.info("Converted resolved schema list to JSON format.")