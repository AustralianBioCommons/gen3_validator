from typing import Dict, Any, List
from pydantic import create_model
import logging

# Set up module-level logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class Linkage:
    def __init__(self, root_node: List[str] = None):
        """
        Initializes the Linkage class with injected dependencies.

        :param root_node: List of root node names. These are entities that are allowed to have unmatched foreign keys. Defaults to ['subject'].
        :type root_node: list[str], optional
        """
        if root_node is None:
            root_node = ['subject']
        self.root_node = root_node
        logger.debug(f"Initialized Linkage with root_node: {self.root_node}")
        self.link_validation_results = None

    def _find_fk(self, data: dict) -> str:
        """
        Identifies the foreign key in a given data dictionary.

        This method iterates over the key-value pairs in the provided data dictionary
        and checks if any value is a dictionary containing a 'submitter_id' key. If such
        a dictionary is found, the corresponding key is returned as the foreign key.

        :param data: A dictionary representing a single data record.
        :type data: dict

        :return: The key corresponding to the foreign key if found, otherwise None.
        :rtype: str
        """
        for key, value in data.items():
            if isinstance(value, dict) and 'submitter_id' in value:
                logger.debug(f"Foreign key found: {key} in data: {data}")
                return key
        logger.debug(f"No foreign key found in data: {data}")
        return None

    def generate_config(self, data_map, link_suffix: str = 's') -> dict:
        """
        Generates a configuration dictionary for entities based on the data map.

        This method creates a configuration dictionary where each key is an entity name
        and the value is a dictionary containing 'primary_key' and 'foreign_key' for that
        entity. The primary key is constructed using the entity name and the provided link
        suffix. The foreign key is determined by searching for a key in the data that
        contains a 'submitter_id'.

        :param data_map: A dictionary where each key is an entity name and the value is a list of data records for that entity.
        :type data_map: dict
        :param link_suffix: A suffix to append to the primary key. Defaults to 's'.
        :type link_suffix: str, optional

        :return: A configuration dictionary with primary and foreign keys for each entity.
        :rtype: dict
        """
        config = {}
        logger.info("Generating config for data_map entities.")
        for node, data in data_map.items():
            fk = self._find_fk(data[0])
            if fk:
                config[node] = {
                    "primary_key": f"{node}{link_suffix}",
                    "foreign_key": f"{fk}"
                }
                logger.debug(f"Config for node '{node}': primary_key='{node}{link_suffix}', foreign_key='{fk}'")
            else:
                config[node] = {
                    "primary_key": f"{node}{link_suffix}",
                    "foreign_key": None
                }
                logger.debug(f"Config for node '{node}': primary_key='{node}{link_suffix}', foreign_key=None")
        logger.info(f"Generated config: {config}")
        return config

    def test_config_links(self, config_map: Dict[str, Any], root_node: List[str] = None) -> dict:
        """
        Validates the configuration map by checking the foreign key links between entities.

        This method checks if the foreign key of each entity in the config map matches
        the primary key of any other entity. If a match is not found and the entity is
        not a root node, it records the broken link. Root nodes are allowed to have
        unmatched foreign keys.

        :param config_map: A dictionary containing the configuration of entities, where each key is an entity name and the value is a dictionary with 'primary_key' and 'foreign_key'.
        :type config_map: Dict[str, Any]
        :param root_node: A list of root node names that are allowed to have unmatched foreign keys. Defaults to ['subject'].
        :type root_node: List[str], optional

        :return: A dictionary of entities with broken links and their foreign keys if any are found. Returns "valid" if no broken links are detected.
        :rtype: dict

        :raises KeyError: If a required key ('primary_key' or 'foreign_key') is missing in the config for any entity.
        :raises TypeError: If config_map is not a dictionary or its values are not dictionaries.
        """
        if root_node is None:
            root_node = ['subject']
        broken_links = {}

        print("=== Validating Config Map ===")
        print(f"Root Node = {root_node}")
        logger.info("=== Validating Config Map ===")
        logger.info(f"Root Node = {root_node}")

        try:
            if not isinstance(config_map, dict):
                raise TypeError(
                    f"config_map must be a dictionary, got {type(config_map).__name__}."
                )
            for key, value in config_map.items():
                if not isinstance(value, dict):
                    raise TypeError(
                        f"Config for entity '{key}' must be a dictionary, got {type(value).__name__}."
                    )
                if 'foreign_key' not in value:
                    raise KeyError(
                        f"Missing 'foreign_key' in config for entity '{key}'. "
                        f"Check your configuration dictionary."
                    )
                if 'primary_key' not in value:
                    raise KeyError(
                        f"Missing 'primary_key' in config for entity '{key}'. "
                        f"Check your configuration dictionary."
                    )

                fk = value['foreign_key']

                # Check if fk of the current key matches with the primary key of any
                # of the other entities
                match_found = any(
                    fk == v['primary_key']
                    for k, v in config_map.items() if k != key
                )

                if not match_found and fk is not None:
                    # If the key is a root node, ignore the broken link
                    if key not in root_node:
                        broken_links[key] = fk
                        logger.warning(
                            f"Broken link found: entity '{key}' with foreign key '{fk}' does not match any primary key."
                        )
                    else:
                        print(
                            f"WARNING: Ignoring broken link for root node '{key}' "
                            f"with foreign key '{fk}'"
                        )
                        logger.info(
                            f"Ignoring broken link for root node '{key}' with foreign key '{fk}'"
                        )

        except KeyError as e:
            logger.error(f"Configuration error: {e}")
            print(f"Configuration error: {e}")
            raise
        except TypeError as e:
            logger.error(f"Type error in configuration: {e}")
            print(f"Type error in configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during config validation: {e}")
            print(f"Unexpected error during config validation: {e}")
            raise

        if len(broken_links) == 0:
            print("Config Map Validated")
            logger.info("Config Map Validated")
            return "valid"
        else:
            print("Config Map Invalid ('entity': 'foreign_key')")
            print("Broken links:", broken_links)
            logger.error("Config Map Invalid ('entity': 'foreign_key')")
            logger.error(f"Broken links: {broken_links}")
            return broken_links

    def get_foreign_keys(
        self, data_map: Dict[str, List[Dict[str, Any]]], config: Dict[str, Any]
    ) -> dict:
        """
        Extracts all foreign key values for each entity from the provided data map,
        using the foreign key field specified in the config for each entity.

        :param data_map: A dictionary where each key is an entity name (e.g., "sample", "subject"), and each value is a list of records (dictionaries) for that entity. Each record should contain the foreign key field as specified in the config.
        :type data_map: Dict[str, List[Dict[str, Any]]]
        :param config: A dictionary where each key is an entity name, and each value is a dictionary containing at least the key 'foreign_key', which specifies the field name in the records to use as the foreign key.
        :type config: Dict[str, Any]

        :return: A dictionary mapping each entity name to a list of extracted foreign key values. If an entity has no foreign key specified in the config, its value will be an empty list.
        :rtype: Dict[str, List[Any]]

        :raises KeyError: If an entity specified in the config is missing from the data_map.
        :raises Exception: If an unexpected error occurs during extraction for any entity.

        .. note::
            - If a record's foreign key field is missing, that record is skipped with a warning.
            - If the foreign key value is a dictionary containing a 'submitter_id', that value is used.
            - Otherwise, the value of the foreign key field is used directly.
            - If the foreign key field is None in the config, extraction is skipped for that entity.

        **Example:**

        .. code-block:: python

            data_map = {
                "sample": [
                    {"subjects": {"submitter_id": "subject_1"}, ...},
                    {"subjects": "subject_2", ...}
                ]
            }
            config = {
                "sample": {"foreign_key": "subjects", ...}
            }
            # Returns: {"sample": ["subject_1", "subject_2"]}
        """
        logger.info("Extracting foreign keys from data_map using config.")

        def extract_fk_values(entity, records, fk_field):
            fk_values = []
            for idx, record in enumerate(records):
                if fk_field not in record:
                    logger.warning(
                        f"Record {idx} in entity '{entity}' is missing the foreign key field '{fk_field}'."
                    )
                    continue
                fk = record.get(fk_field)
                if not fk:
                    continue
                if isinstance(fk, dict) and 'submitter_id' in fk:
                    fk_values.append(fk['submitter_id'])
                    logger.debug(
                        f"Entity '{entity}': extracted foreign key '{fk['submitter_id']}' from dict."
                    )
                else:
                    fk_values.append(fk)
                    logger.debug(
                        f"Entity '{entity}': extracted foreign key '{fk}'."
                    )
            return fk_values

        fk_entities = {}
        for entity, keys in config.items():
            if entity not in data_map:
                msg = (
                    f"Entity '{entity}' specified in config is missing from data_map. "
                    f"Available entities: {list(data_map.keys())}"
                )
                logger.error(msg)
                raise KeyError(msg)

            fk_field = keys.get('foreign_key')
            if fk_field is None:
                logger.info(f"No foreign key specified for entity '{entity}'. Skipping extraction.")
                fk_entities[entity] = []
                continue

            records = data_map[entity]
            try:
                fk_values = extract_fk_values(entity, records, fk_field)
                fk_entities[entity] = fk_values
                logger.info(f"Foreign keys for entity '{entity}': {fk_values}")
            except Exception as e:
                logger.error(f"Unexpected error while extracting foreign keys for entity '{entity}': {e}")
                raise Exception(
                    f"An unexpected error occurred while extracting foreign keys for entity '{entity}': {e}"
                ) from e

        return fk_entities

    def get_primary_keys(
        self, data_map: Dict[str, List[Dict[str, Any]]], config: Dict[str, Any]
    ) -> dict:
        """
        Extracts all primary key values for each entity from the provided data map,
        using the primary key field specified in the config for each entity.

        :param data_map: A dictionary where each key is an entity name (e.g., "sample", "subject"), and each value is a list of records (dictionaries) for that entity. Each record should contain the primary key field as specified in the config.
        :type data_map: Dict[str, List[Dict[str, Any]]]
        :param config: A dictionary where each key is an entity name, and each value is a dictionary containing at least the key 'primary_key', which specifies the field name in the records to use as the primary key.
        :type config: Dict[str, Any]

        :return: A dictionary mapping each entity name to a list of extracted primary key values. If an entity has no primary key specified in the config, its value will be an empty list.
        :rtype: Dict[str, List[Any]]

        :raises KeyError: If an entity specified in the config is missing from the data_map.
        :raises Exception: If an unexpected error occurs during extraction for any entity.

        .. note::
            - If a record's primary key field is missing, that record is skipped with a warning.
            - If the primary key value is a dictionary containing a 'submitter_id', that value is used.
            - Otherwise, the value of the primary key field is used directly.
            - If the primary key field is None in the config, extraction is skipped for that entity.

        **Example:**

        .. code-block:: python

            data_map = {
                "subject": [
                    {"subjects": "subject_1", ...},
                    {"subjects": {"submitter_id": "subject_2"}, ...}
                ]
            }
            config = {
                "subject": {"primary_key": "subjects", ...}
            }
            # Returns: {"subject": ["subject_1", "subject_2"]}
        """
        logger.info("Extracting primary keys from data_map using config.")

        def extract_pk_values(entity, records, pk_field):
            pk_values = []
            for idx, record in enumerate(records):
                if pk_field not in record:
                    logger.warning(
                        f"Record {idx} in entity '{entity}' is missing the primary key field '{pk_field}'."
                    )
                    continue
                pk = record.get(pk_field)
                if not pk:
                    continue
                if isinstance(pk, dict) and 'submitter_id' in pk:
                    pk_values.append(pk['submitter_id'])
                    logger.debug(
                        f"Entity '{entity}': extracted primary key '{pk['submitter_id']}' from dict."
                    )
                else:
                    pk_values.append(pk)
                    logger.debug(
                        f"Entity '{entity}': extracted primary key '{pk}'."
                    )
            return pk_values

        pk_entities = {}
        for entity, keys in config.items():
            if entity not in data_map:
                msg = (
                    f"Entity '{entity}' specified in config is missing from data_map. "
                    f"Available entities: {list(data_map.keys())}"
                )
                logger.error(msg)
                raise KeyError(msg)

            pk_field = keys.get('primary_key')
            if pk_field is None:
                logger.info(f"No primary key specified for entity '{entity}'. Skipping extraction.")
                pk_entities[entity] = []
                continue

            records = data_map[entity]
            try:
                pk_values = extract_pk_values(entity, records, pk_field)
                pk_entities[entity] = pk_values
                logger.info(f"Primary keys for entity '{entity}': {pk_values}")
            except Exception as e:
                logger.error(f"Unexpected error while extracting primary keys for entity '{entity}': {e}")
                raise Exception(
                    f"An unexpected error occurred while extracting primary keys for entity '{entity}': {e}"
                ) from e

        return pk_entities

    def validate_links(
        self, data_map: Dict[str, List[Dict[str, Any]]], config: Dict[str, Any],
        root_node: List[str] = None
    ) -> Dict[str, List[str]]:
        """
        Verifies Config file, then extracts primary and foreign key values
        from the data map. Then uses the foreign key values to validate the
        primary key values.

        First, validates the config map for correct foreign/primary key relationships.
        Then, for each entity, checks that all its foreign key values exist among the
        primary key values of any entity. Returns a dictionary mapping each entity to
        a list of invalid (unmatched) foreign key values.

        :param data_map: Contains the data for each entity.
        :type data_map: Dict[str, List[Dict[str, Any]]]
        :param config: The entity linkage configx.
        :type config: Dict[str, Any]
        :param root_node: List of root node names that are allowed to have unmatched foreign keys. Defaults to ['subject'].
        :type root_node: List[str], optional

        :return: Dictionary of entities and their validation results. If the config is invalid, returns the config validation result.
        :rtype: Dict[str, List[str]]
        """
        if root_node is None:
            root_node = ['subject']

        # validating config map
        logger.info("Validating config map before link validation.")
        valid_config = self.test_config_links(config, root_node=root_node)
        if valid_config != "valid":
            print("Invalid Config Map")
            print(config)
            logger.error("Invalid Config Map")
            logger.error(f"Config: {config}")
            return valid_config

        fk_entities = self.get_foreign_keys(data_map, config)
        pk_entities = self.get_primary_keys(data_map, config)

        print("=== Validating Links ===")
        logger.info("=== Validating Links ===")

        validation_results = {}
        for entity, fk_values in fk_entities.items():
            invalid_keys = [
                fk for fk in fk_values if all(
                    fk not in pk_values for pk_values in pk_entities.values()
                )
            ]
            validation_results[entity] = invalid_keys
            print(
                f"Entity '{entity}' has {len(invalid_keys)} invalid foreign keys: "
                f"{invalid_keys}"
            )
            if invalid_keys:
                logger.warning(
                    f"Entity '{entity}' has {len(invalid_keys)} invalid foreign keys: {invalid_keys}"
                )
            else:
                logger.info(
                    f"Entity '{entity}' has no invalid foreign keys."
                )
        self.link_validation_results = validation_results
        return validation_results
