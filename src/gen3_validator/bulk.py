import os
import glob
import json
import logging

from gen3_validator.validate import validate_list_dict
from gen3_validator.resolve_schema import ResolveSchema

logger = logging.getLogger(__name__)

__all__ = [
    "parse_import_order",
    "load_node_records",
    "validate_data_folder",
    "validate_data_folder_from_schema",
]

DEFAULT_IMPORT_ORDER_FILENAME = "DataImportOrder.txt"


def parse_import_order(order_file_path: str) -> list:
    """
    Parse a data import order file into an ordered list of node names.

    The import order file lists the nodes (entities) in the sequence they should be
    processed. Two formats are tolerated:

    - Plain node names, one per line (the format produced by the synthetic data
      pipeline), e.g.::

          project
          acknowledgement
          subject

    - Numbered rows where each line is ``<number><whitespace><node>`` (whitespace may be
      a tab or spaces), e.g.::

          1   project
          2   acknowledgement

    Blank lines and lines beginning with ``#`` are ignored. A stray ``.json``/``.yaml``
    extension on a node name is stripped defensively.

    :param order_file_path: Path to the import order file.
    :type order_file_path: str

    :raises FileNotFoundError: If the import order file does not exist. This file is
        mandatory, so we fail fast rather than silently validating nothing.

    :return: Node names in import order.
    :rtype: list
    """
    logger.info(f"Parsing import order file: {order_file_path}")
    ordered = []
    seen = set()
    with open(order_file_path, encoding="utf-8") as f:
        for line_index, raw in enumerate(f):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) >= 2 and parts[0].lstrip("-").isdigit():
                sort_key = int(parts[0])
                name = parts[1]
            else:
                sort_key = line_index
                name = parts[0]

            name = os.path.splitext(name)[0]
            if name in seen:
                logger.warning(
                    f"Duplicate node '{name}' in import order file; keeping first occurrence."
                )
                continue
            seen.add(name)
            ordered.append((sort_key, name))

    ordered.sort(key=lambda pair: pair[0])
    return [name for _, name in ordered]


def load_node_records(file_path: str) -> list:
    """
    Load a single node's JSON file and normalise it to a list of record dictionaries.

    Most node files contain a JSON array of records, but some (e.g. ``project.json``)
    contain a single JSON object. Both are normalised to a list so downstream validation
    can treat every node the same way.

    :param file_path: Path to the ``<node>.json`` file.
    :type file_path: str

    :raises FileNotFoundError: If the file does not exist.
    :raises json.JSONDecodeError: If the file is not valid JSON.
    :raises ValueError: If the top-level JSON is neither an object nor an array.

    :return: A list of record dictionaries.
    :rtype: list
    """
    logger.info(f"Loading node records from: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(
        f"{file_path}: expected a JSON object or array of records, got {type(data).__name__}"
    )


def _problem_record(node: str, filename: str, message: str) -> dict:
    """
    Build a report row representing a node that could not be loaded or validated.

    Shaped like a validation FAIL record so it slots into the same flat report, but with
    ``validation_result`` set to ``"ERROR"`` to distinguish structural/load problems from
    schema validation failures.

    :param node: The node name.
    :param filename: The source filename for the node.
    :param message: A human-readable description of the problem.
    :return: A report row dictionary.
    :rtype: dict
    """
    return {
        "node": node,
        "index": None,
        "validation_result": "ERROR",
        "invalid_key": None,
        "schema_path": None,
        "validator": None,
        "validator_value": None,
        "validation_error": message,
        "source_file": filename,
    }


def validate_data_folder(
    folder_path: str,
    resolved_schema: dict,
    import_order_filename: str = DEFAULT_IMPORT_ORDER_FILENAME,
) -> list:
    """
    Validate a folder of per-node JSON files against a resolved Gen3 schema, in import order.

    For each node listed in the import order file, the matching ``<node>.json`` file is
    loaded and its records are validated against the resolved schema using the existing
    :func:`gen3_validator.validate.validate_list_dict`. Results are concatenated in import
    order, and every failure record is augmented with the ``source_file`` it came from.

    Behaviour for non-ideal inputs:

    - A node listed in the import order with no matching file is logged as a warning and
      skipped (its absence is expected, not an error).
    - A ``*.json`` file present in the folder but not listed in the import order is logged
      as a warning and ignored.
    - If a node's file cannot be loaded or validated (invalid JSON, malformed records,
      missing schema), a single ``ERROR`` record is emitted for that node and processing
      continues, so one bad file never aborts the whole run.

    :param folder_path: Path to the folder containing the ``<node>.json`` files and the
        import order file.
    :type folder_path: str
    :param resolved_schema: A resolved schema dict (e.g.
        ``ResolveSchema(...).schema_resolved``), keyed by ``"<node>.yaml"``.
    :type resolved_schema: dict
    :param import_order_filename: Name of the import order file within ``folder_path``.
    :type import_order_filename: str

    :raises FileNotFoundError: If the import order file is missing.

    :return: A flat list of validation result dictionaries, ordered by import order. Each
        FAIL record includes the standard validation keys plus ``source_file``; load/
        structural problems appear as ``ERROR`` records.
    :rtype: list
    """
    order_path = os.path.join(folder_path, import_order_filename)
    node_order = parse_import_order(order_path)
    logger.info(f"Validating {len(node_order)} node(s) from folder: {folder_path}")

    results = []
    processed_files = set()
    for node in node_order:
        filename = f"{node}.json"
        file_path = os.path.join(folder_path, filename)
        processed_files.add(filename)

        if not os.path.isfile(file_path):
            logger.warning(
                f"Node '{node}' is in the import order but {filename} was not found; skipping."
            )
            continue

        try:
            records = load_node_records(file_path)
            node_results = validate_list_dict(records, resolved_schema)
        except Exception as e:
            logger.error(f"Failed to validate node '{node}' ({filename}): {e}")
            results.append(_problem_record(node, filename, str(e)))
            continue

        for record in node_results:
            record["source_file"] = filename
        results.extend(node_results)

    for path in sorted(glob.glob(os.path.join(folder_path, "*.json"))):
        basename = os.path.basename(path)
        if basename not in processed_files:
            logger.warning(
                f"File {basename} is present but not listed in the import order; ignored."
            )

    return results


def validate_data_folder_from_schema(
    folder_path: str,
    schema_path: str,
    import_order_filename: str = DEFAULT_IMPORT_ORDER_FILENAME,
) -> list:
    """
    Resolve a Gen3 schema from disk, then validate a folder of per-node JSON files.

    Convenience wrapper that resolves ``schema_path`` with
    :class:`gen3_validator.resolve_schema.ResolveSchema` and delegates to
    :func:`validate_data_folder`.

    :param folder_path: Path to the folder containing the ``<node>.json`` files and the
        import order file.
    :type folder_path: str
    :param schema_path: Path to the (unresolved) Gen3 JSON schema file.
    :type schema_path: str
    :param import_order_filename: Name of the import order file within ``folder_path``.
    :type import_order_filename: str

    :return: A flat list of validation result dictionaries, ordered by import order.
    :rtype: list
    """
    resolver = ResolveSchema(schema_path)
    resolver.resolve_schema()
    return validate_data_folder(folder_path, resolver.schema_resolved, import_order_filename)
