from jsonschema import Draft4Validator
from functools import wraps
from datetime import datetime
from functools import wraps
from time import time
import pandas as pd
import json
import uuid
import logging
import os

logger = logging.getLogger(__name__)

def validate_object(obj: dict, idx: int, validator) -> list:
    """
    Validates a single JSON object against a provided JSON schema validator.

    :param dict obj: The JSON object to validate.
    :param int idx: The index of the object in the dataset.
    :param Draft4Validator validator: The JSON schema validator to use for validation.

    :returns: A list of dictionaries containing validation results and log messages.
    :rtype: list
    """
    validation_results = []
    try:
        errors = list(validator.iter_errors(obj))
        logger.debug(f"Object at index {idx} validated with {len(errors)} errors.")
    except Exception as e:
        logger.error(f"Error in validate_object during object validation at index {idx}: {e}")
        return validation_results
    
    if "type" in obj:
        node = obj["type"]
        logger.debug(f"Validating object at index {idx} of type '{node}'.")
    else:
        node = None
        logger.debug(f"Object at index {idx} missing 'type' key.")

    if errors:
        logger.debug(f"Found {len(errors)} validation error(s) for object at index {idx} (type: '{node}').")
        for error in errors:
            invalid_key = ".".join(str(k) for k in error.path) if error.path else "root"
            schema_path = ".".join(str(k) for k in error.schema_path)
            logger.debug(
                f"Validation error in object at index {idx}, node '{node}': "
                f"invalid_key='{invalid_key}', schema_path='{schema_path}', "
                f"validator='{error.validator}', validator_value='{error.validator_value}', "
                f"error='{error.message}'"
            )
            result = {
                "node": node,
                "index": idx,
                "validation_result": "FAIL",
                "invalid_key": invalid_key,
                "schema_path": schema_path,
                "validator": error.validator,
                "validator_value": error.validator_value,
                "validation_error": error.message
            }
            validation_results.append(result)

    else:
        logger.debug(f"No validation errors for object at index {idx} (type: '{node}').")

    return validation_results


def pull_schema(node: str, schema: dict) -> dict:
    """
    Retrieve the schema object for a given node from the schema dictionary.

    :param node: The name of the node to retrieve.
    :param schema: The dictionary containing schema objects.
    :return: The matched schema object, or None if not found.
    """
    return schema.get(node) or schema.get(f"{node}.yaml")

def validate_list_dict(data_list: list[dict], resolved_schema: dict) -> list[dict]:
    """
    Validates a list of JSON objects against a provided JSON schema.

    :param list[dict] data_list: The list of JSON objects to validate.
    :param dict resolved_schema: The resolved JSON schema to use for validation.

    :returns: A list of dictionaries containing validation results and log messages.
    :rtype: list
    """
    validation_results = []
    for idx, obj in enumerate(data_list):
        
        if "type" not in obj:
            logger.error(
                f"Error in validate_list_dict during object validation at index {idx}, key 'type' not found in object: {obj}"
            )
            raise Exception(
                f"Error in validate_list_dict during object validation at index {idx}, key 'type' not found in {obj}"
            )
        node = obj["type"]
        
        schema = pull_schema(os.path.splitext(node)[0], resolved_schema)
        if schema is None:
            logger.error(
                f"Error in validate_list_dict during object validation at index {idx}, key '{node}' not found in resolved schema"
            )
            raise Exception(
                f"Error in validate_list_dict during object validation at index {idx}, key '{node}' not found in resolved schema"
            )
        
        validator = Draft4Validator(schema)
        validation_results.extend(validate_object(obj, idx, validator))
        
    return validation_results