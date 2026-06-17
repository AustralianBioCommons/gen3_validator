import os
import glob
import json
import logging

from gen3_validator.validate import validate_list_dict, pull_schema
from gen3_validator.resolve_schema import ResolveSchema

logger = logging.getLogger(__name__)

__all__ = [
    "parse_import_order",
    "load_node_records",
    "extract_links",
    "build_identifier_index",
    "validate_record_links",
    "validate_data_folder",
    "validate_data_folder_from_schema",
]

DEFAULT_IMPORT_ORDER_FILENAME = "DataImportOrder.txt"

# Identifier keys a reference object may use to point at a target record. Most nodes are
# referenced by ``submitter_id``; ``project`` is referenced by ``code`` (project records
# have no ``submitter_id``). ``id`` is accepted defensively.
IDENTIFIER_KEYS = ("submitter_id", "code", "id")


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


def extract_links(node_schema: dict) -> list:
    """
    Flatten a resolved node schema's ``links`` into a simple list of link descriptors.

    In a Gen3 schema each node declares its parent relationships in a top-level ``links``
    array. A link is the parent seen from the child: its ``name`` is the property key used
    in the data (often the parent's name pluralised, e.g. ``samples``) and its
    ``target_type`` is the parent node's id (e.g. ``sample``). Links may be grouped inside a
    ``subgroup`` wrapper (used when a node may attach to one of several parents); both plain
    links and subgroup members are flattened here.

    :param node_schema: A resolved node schema (the value of ``schema_resolved["<node>.yaml"]``).
    :type node_schema: dict

    :return: A list of ``{"name": <property key>, "target_type": <parent node>}`` dicts.
        Returns an empty list if the node has no usable links.
    :rtype: list
    """
    links = (node_schema or {}).get("links") or []
    flattened = []
    for entry in links:
        if not isinstance(entry, dict):
            continue
        members = entry["subgroup"] if "subgroup" in entry else [entry]
        for member in members:
            if not isinstance(member, dict):
                continue
            name = member.get("name")
            target_type = member.get("target_type")
            if name and target_type:
                flattened.append({"name": name, "target_type": target_type})
    return flattened


def build_identifier_index(node_records: dict, id_keys: tuple = IDENTIFIER_KEYS) -> dict:
    """
    Build a lookup of the identifier values present in each loaded node's records.

    The index lets link validation answer "does a record with this identifier exist in the
    target node?" in constant time. Every loaded node gets an entry (even one with no
    records), so a node that is *present but empty* is distinguishable from a node that is
    *absent from the folder*.

    :param node_records: Mapping of node name to its list of record dicts.
    :type node_records: dict
    :param id_keys: The identifier keys to collect from each record.
    :type id_keys: tuple

    :return: ``{node: {id_key: {values}}}`` — for each node, the set of values seen for each
        identifier key that actually appears in its records.
    :rtype: dict
    """
    index = {}
    for node, records in node_records.items():
        key_to_values = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in id_keys:
                value = record.get(key)
                if value is not None:
                    key_to_values.setdefault(key, set()).add(value)
        index[node] = key_to_values
    return index


def _iter_references(value):
    """
    Yield the reference dicts contained in a link property value.

    A link value is either a single reference object ``{"submitter_id": ...}`` or a list of
    them. Null/missing values and non-dict shapes yield nothing (those are schema-type
    concerns handled elsewhere, not referential integrity).
    """
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def validate_record_links(
    record: dict,
    idx: int,
    node_name: str,
    links: list,
    index: dict,
    warned: set = None,
) -> list:
    """
    Check that every link reference in a single record points to an existing record.

    For each declared link whose property is present in ``record``, each reference is
    resolved against ``index``: the reference passes if any identifier it carries
    (``submitter_id``/``code``/``id``) matches a value in the target node. A reference to a
    target node that is not present in the folder is skipped with a (deduplicated) warning
    rather than failed, since there is no data to check against.

    :param record: The data record whose links are being checked.
    :type record: dict
    :param idx: The record's index within its node file (shared with schema-validation rows).
    :type idx: int
    :param node_name: The node the record belongs to (matches its ``source_file``).
    :type node_name: str
    :param links: Flattened links for this node, from :func:`extract_links`.
    :type links: list
    :param index: Identifier index from :func:`build_identifier_index`.
    :type index: dict
    :param warned: A set used to deduplicate absent-target warnings across records.
    :type warned: set

    :return: A list of link FAIL rows (empty when all references resolve).
    :rtype: list
    """
    if warned is None:
        warned = set()

    results = []
    for link in links:
        name = link["name"]
        target_type = link["target_type"]
        if name not in record:
            continue

        for ref in _iter_references(record[name]):
            present_keys = {k: ref[k] for k in IDENTIFIER_KEYS if ref.get(k) is not None}
            if not present_keys:
                continue  # not a recognisable reference; leave to schema validation

            if target_type not in index:
                warn_key = (node_name, name, target_type)
                if warn_key not in warned:
                    warned.add(warn_key)
                    logger.warning(
                        f"Link '{name}' on node '{node_name}' points to '{target_type}', "
                        f"which has no data in the folder; skipping reference checks for it."
                    )
                continue

            target_index = index[target_type]
            resolved = any(
                value in target_index.get(key, set())
                for key, value in present_keys.items()
            )
            if not resolved:
                id_key, id_value = next(iter(present_keys.items()))
                results.append(
                    {
                        "node": node_name,
                        "index": idx,
                        "validation_result": "FAIL",
                        "invalid_key": name,
                        "schema_path": "links",
                        "validator": "link",
                        "validator_value": target_type,
                        "validation_error": (
                            f"Link '{name}' references {target_type} '{id_value}' "
                            f"(by {id_key}) but no matching record exists in {target_type}.json"
                        ),
                    }
                )
    return results


def validate_data_folder(
    folder_path: str,
    resolved_schema: dict,
    import_order_filename: str = DEFAULT_IMPORT_ORDER_FILENAME,
    check_links: bool = True,
) -> list:
    """
    Validate a folder of per-node JSON files against a resolved Gen3 schema, in import order.

    For each node listed in the import order file, the matching ``<node>.json`` file is
    loaded and its records are validated against the resolved schema using the existing
    :func:`gen3_validator.validate.validate_list_dict`. When ``check_links`` is true (the
    default), the references between nodes are also checked for referential integrity: every
    link reference in a record must point to a record that exists in the target node's data.
    Results are concatenated in import order, and every result row is augmented with the
    ``source_file`` it came from.

    Behaviour for non-ideal inputs:

    - A node listed in the import order with no matching file is logged as a warning and
      skipped (its absence is expected, not an error).
    - A ``*.json`` file present in the folder but not listed in the import order is logged
      as a warning and ignored.
    - If a node's file cannot be loaded or validated (invalid JSON, malformed records,
      missing schema), a single ``ERROR`` record is emitted for that node and processing
      continues, so one bad file never aborts the whole run.
    - A link whose target node has no data in the folder is skipped with a warning (there is
      nothing to validate against); a link into a node that is present but empty fails.

    :param folder_path: Path to the folder containing the ``<node>.json`` files and the
        import order file.
    :type folder_path: str
    :param resolved_schema: A resolved schema dict (e.g.
        ``ResolveSchema(...).schema_resolved``), keyed by ``"<node>.yaml"``.
    :type resolved_schema: dict
    :param import_order_filename: Name of the import order file within ``folder_path``.
    :type import_order_filename: str
    :param check_links: Whether to also validate cross-node reference integrity.
    :type check_links: bool

    :raises FileNotFoundError: If the import order file is missing.

    :return: A flat list of validation result dictionaries, ordered by import order. Schema
        failures have ``validator`` set by jsonschema; link failures have
        ``validator == "link"``; load/structural problems appear as ``ERROR`` rows. Every
        row includes ``source_file``.
    :rtype: list
    """
    order_path = os.path.join(folder_path, import_order_filename)
    node_order = parse_import_order(order_path)
    logger.info(f"Validating {len(node_order)} node(s) from folder: {folder_path}")

    # Pass 1: load every present node's records once. Emit no rows here so that, in pass 2,
    # every row (including load errors) appears at its node's correct import-order position.
    loaded = {}
    load_errors = {}
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
            loaded[node] = load_node_records(file_path)
        except Exception as e:
            logger.error(f"Failed to load node '{node}' ({filename}): {e}")
            load_errors[node] = str(e)

    index = build_identifier_index(loaded) if check_links else {}
    warned = set()

    # Pass 2: validate and emit rows in import order.
    results = []
    for node in node_order:
        filename = f"{node}.json"

        if node in load_errors:
            results.append(_problem_record(node, filename, load_errors[node]))
            continue
        if node not in loaded:
            continue

        records = loaded[node]

        try:
            schema_results = validate_list_dict(records, resolved_schema)
        except Exception as e:
            logger.error(f"Failed to validate node '{node}' ({filename}): {e}")
            results.append(_problem_record(node, filename, str(e)))
            continue  # structurally broken node; skip link checks

        for record in schema_results:
            record["source_file"] = filename
        results.extend(schema_results)

        if check_links:
            links = extract_links(pull_schema(node, resolved_schema) or {})
            for idx, record in enumerate(records):
                link_results = validate_record_links(
                    record, idx, node, links, index, warned
                )
                for row in link_results:
                    row["source_file"] = filename
                results.extend(link_results)

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
    check_links: bool = True,
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
    :param check_links: Whether to also validate cross-node reference integrity.
    :type check_links: bool

    :return: A flat list of validation result dictionaries, ordered by import order.
    :rtype: list
    """
    resolver = ResolveSchema(schema_path)
    resolver.resolve_schema()
    return validate_data_folder(
        folder_path,
        resolver.schema_resolved,
        import_order_filename,
        check_links=check_links,
    )
