import json
from collections import defaultdict, deque
import logging

from gen3_validator.dict import DataDictionary

logger = logging.getLogger(__name__)

class ResolveSchema(DataDictionary):
    def __init__(self, schema_path: str):
        """
        Initialize the ResolveSchema class, inheriting from DataDictionary.

        :param schema_path: The path to the JSON schema file.
        :type schema_path: str
        """
        super().__init__(schema_path)
        logger.info(f"Initializing ResolveSchema with schema path: {schema_path}")
        self.schema_def_resolved = None
        self.schema_list_resolved = None
        self.schema_resolved = None

    def resolve_references(self, schema: dict, reference: dict) -> dict:
        """
        Recursively resolve all ``$ref`` references in a Gen3 JSON schema draft 4 node,
        using a reference schema that contains no references.

        :param schema: The JSON node to resolve references in.
        :type schema: dict
        :param reference: The schema containing the reference definitions.
        :type reference: dict
        :return: The resolved JSON node with all references resolved.
        :rtype: dict
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

                        # If a reference file is in the reference, load the pre-defined reference;
                        # if no file exists, then use the schema itself as reference.
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
        Resolve references in all schema node dictionaries using the resolved definitions schema.

        :return: A list of resolved schema dictionaries, one for each node.
        :rtype: list
        """
        logger.info("Resolving all references in schema list.")
        logger.info("=== Resolving Schema References ===")

        resolved_schema_list = []
        for node in self.get_nodes():
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

    def return_resolved_schema(self, schema_id: str) -> dict:
        """
        Retrieve the first dictionary from the resolved schema list where the ``id`` key matches ``schema_id``.

        :param schema_id: The value of the ``id`` key to match. May include or omit the ``.yaml`` extension.
        :type schema_id: str
        :return: The dictionary that matches the schema_id, or None if not found.
        :rtype: dict or None
        """
        logger.info(f"Retrieving resolved schema for schema ID: {schema_id}")
        try:
            if schema_id.endswith(".yaml"):
                schema_id = schema_id[:-5]

            result = next(
                (item for item in self.schema_list_resolved if item.get("id") == schema_id), None
            )
            if result is None:
                logger.error(f"{schema_id} not found in resolved schema list")
            return result
        except Exception as e:
            logger.error(f"Error retrieving resolved schema for {schema_id}: {e}")
            raise

    def resolve_schema(self):
        """
        Fully resolve and initialize all schema-related attributes for this instance.

        This method performs the following steps:

            1. Reads and parses the raw schema from file.
            2. Extracts the definitions and terms schemas.
            3. Resolves references within the definitions schema using the terms schema.
            4. Resolves all references in each node schema using the resolved definitions.
            5. Converts the fully resolved node schemas into a JSON dictionary format.

        After execution, the following instance attributes are set:

            - ``self.schema``: Raw schema dictionary loaded from file.
            - ``self.schema_list``: List of individual node schemas.
            - ``self.schema_def``: Definitions schema dictionary.
            - ``self.schema_term``: Terms schema dictionary.
            - ``self.schema_def_resolved``: Definitions schema with references resolved.
            - ``self.schema_list_resolved``: List of node schemas with all references resolved.
            - ``self.schema_resolved``: Dictionary of resolved node schemas in JSON format.

        :return: None
        """
        logger.info("Starting schema resolution process.")
        self.parse_schema()

        self.schema_def = self.return_schema("_definitions.yaml")
        logger.info("Retrieved definitions schema.")
        self.schema_term = self.return_schema("_terms.yaml")
        logger.info("Retrieved terms schema.")

        self.schema_def_resolved = self.resolve_references(
            self.schema_def, self.schema_term
        )
        logger.info("Resolved references in definitions schema.")

        self.schema_list_resolved = self.resolve_all_references()
        logger.info("Resolved all references in schema list.")

        self.schema_resolved = self.schema_list_to_json(self.schema_list_resolved)
        logger.info("Converted resolved schema list to JSON format.")
