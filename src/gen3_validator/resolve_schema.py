import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from gen3_validator.dict import DataDictionary

logger = logging.getLogger(__name__)

# Label used for a document passed directly to resolve_references rather than
# looked up from the schema bundle by filename.
_INPUT_DOC = "<input>"
# Label used when a ref falls back to the caller-supplied reference document.
_FALLBACK_DOC = "<reference>"


class SchemaResolutionError(Exception):
    """Base class for all ``$ref`` resolution failures in a Gen3 schema bundle.

    Deliberately not a subclass of ``KeyError``: historic code swallowed
    ``KeyError`` during resolution, which silently dropped nodes from the
    resolved schema. A distinct hierarchy guarantees these errors stay loud.
    """


class RefResolutionError(SchemaResolutionError):
    """A ``$ref`` points at a file missing from the bundle or a dangling pointer."""


class CircularRefError(SchemaResolutionError):
    """A ``$ref`` chain loops back on itself."""


class _BundleResolver:
    """Resolve ``$ref`` entries against a filename-keyed Gen3 schema bundle.

    A Gen3 ``schema.json`` is a bundle keyed by source filename
    (``case.yaml``, ``_definitions.yaml``, ``_terms.yaml``, ...). A ``$ref``
    of the form ``"<file>#<pointer>"`` resolves against the named file;
    a bare ``"#<pointer>"`` resolves against the file the reference
    physically appears in. This class threads that file context through the
    recursion, memoizes resolved targets per ``(file, pointer)``, and detects
    circular chains.

    Resolved fragments are deep-copied on the way out so no two callers share
    mutable state. Cost is proportional to refs times fragment size, which is
    negligible for real dictionaries (tens of files).

    ``term``/``terms`` blocks are documentation-only in Gen3 schemas and the
    official dictionary ships some whose refs dangle (e.g.
    ``_terms.yaml#/file_format`` with no such key in ``_terms.yaml``). A
    dangling ref inside such a block is therefore tolerated with a warning —
    the block keeps whatever siblings resolve — while a dangling ref anywhere
    structural still raises.
    """

    _DOCUMENTATION_KEYS = ("term", "terms")

    def __init__(self, bundle: Optional[dict], fallback_reference: Optional[dict] = None):
        self.bundle = bundle if isinstance(bundle, dict) else {}
        self.fallback_reference = fallback_reference
        self._input_doc: Any = None
        self._memo: Dict[Tuple[str, str], Any] = {}
        self._stack: List[Tuple[str, str]] = []

    # -- public entry points -------------------------------------------------

    def resolve_document(self, filename: str) -> Any:
        """Resolve every ``$ref`` in one bundle file (e.g. ``_definitions.yaml``)."""
        document = self._get_document(filename, ref=filename, source_file=filename)
        return self.resolve_node(document, filename)

    def resolve_input(self, document: Any) -> Any:
        """Resolve a caller-supplied document; its bare refs resolve against itself."""
        self._input_doc = document
        return self.resolve_node(document, _INPUT_DOC)

    def resolve_node(self, node: Any, current_file: str, lenient: bool = False) -> Any:
        """Recursively resolve ``node``, treating ``current_file`` as its origin.

        ``lenient`` is set while inside a documentation-only ``term``/``terms``
        block, where a dangling ref is downgraded to a warning.
        """
        if isinstance(node, dict):
            if "$ref" in node:
                try:
                    resolved = self._resolve_ref(node["$ref"], current_file, lenient)
                except RefResolutionError:
                    if not lenient:
                        raise
                    logger.warning(
                        f"Ignoring dangling $ref '{node['$ref']}' in "
                        f"'{current_file}' inside a documentation-only "
                        f"term/terms block"
                    )
                    resolved = {}
                siblings = {
                    key: self.resolve_node(
                        value, current_file, lenient or key in self._DOCUMENTATION_KEYS
                    )
                    for key, value in node.items()
                    if key != "$ref"
                }
                if isinstance(resolved, dict):
                    # Sibling keys win over resolved content — the historic
                    # Gen3 merge rule downstream schemas depend on.
                    return {**resolved, **siblings}
                if not siblings:
                    return resolved
                raise SchemaResolutionError(
                    f"$ref '{node['$ref']}' in '{current_file}' resolves to a "
                    f"{type(resolved).__name__}, which cannot be merged with "
                    f"sibling keys {sorted(siblings)}"
                )
            return {
                key: self.resolve_node(
                    value, current_file, lenient or key in self._DOCUMENTATION_KEYS
                )
                for key, value in node.items()
            }
        if isinstance(node, list):
            return [self.resolve_node(item, current_file, lenient) for item in node]
        return node

    # -- internals -----------------------------------------------------------

    def _resolve_ref(self, ref: str, current_file: str, lenient: bool = False) -> Any:
        ref_file, _, pointer = ref.partition("#")
        ref_file = ref_file.strip()
        pointer = pointer.strip("/")

        target_file = ref_file or current_file
        document = self._get_document(target_file, ref=ref, source_file=current_file)
        if document is self.fallback_reference and target_file not in self.bundle:
            # Nested bare refs inside a fallback-resolved fragment must keep
            # resolving against the fallback document, not a bundle file.
            target_file = _FALLBACK_DOC

        key = (target_file, pointer)
        if key in self._stack:
            chain = " -> ".join(f"{f}#/{p}" for f, p in self._stack + [key])
            raise CircularRefError(
                f"Circular $ref detected in '{current_file}': {chain}"
            )
        if key in self._memo:
            return copy.deepcopy(self._memo[key])

        self._stack.append(key)
        try:
            target = self._walk_pointer(
                document, pointer, ref=ref, source_file=current_file, target_file=target_file
            )
            resolved = self.resolve_node(target, target_file, lenient)
        finally:
            self._stack.pop()

        self._memo[key] = resolved
        return copy.deepcopy(resolved)

    def _get_document(self, file_label: str, *, ref: str, source_file: str) -> Any:
        if file_label == _INPUT_DOC:
            return self._input_doc
        if file_label == _FALLBACK_DOC:
            return self.fallback_reference
        if file_label in self.bundle and self.bundle[file_label] is not None:
            return self.bundle[file_label]
        if self.fallback_reference is not None:
            return self.fallback_reference
        raise RefResolutionError(
            f"Cannot resolve $ref '{ref}' in '{source_file}': file "
            f"'{file_label}' is not in the schema bundle "
            f"(bundle files: {sorted(self.bundle)})"
        )

    @staticmethod
    def _walk_pointer(document: Any, pointer: str, *, ref: str, source_file: str, target_file: str) -> Any:
        if pointer == "":
            return document
        current = document
        walked: List[str] = []
        for raw_part in pointer.split("/"):
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
                current = current[int(part)]
            else:
                resolved_up_to = "/" + "/".join(walked) if walked else ""
                raise RefResolutionError(
                    f"Cannot resolve $ref '{ref}' in '{source_file}': pointer "
                    f"segment '{part}' not found in '{target_file}'"
                    + (f" (resolved up to '{resolved_up_to}')" if walked else "")
                )
            walked.append(part)
        return current


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
        self._resolver: Optional[_BundleResolver] = None

    def resolve_references(self, schema: dict, reference: dict = None) -> dict:
        """
        Recursively resolve all ``$ref`` references in a Gen3 JSON schema node.

        File-qualified references (``"<file>#<pointer>"``) resolve against the
        named file of the loaded schema bundle when one is loaded; ``reference``
        acts as a fallback document for files not present in the bundle (which
        preserves the historic behaviour of callers that pass a standalone
        reference document without loading a bundle). Bare references
        (``"#<pointer>"``) resolve against the document they appear in.

        :param schema: The JSON node to resolve references in.
        :type schema: dict
        :param reference: Fallback document for refs whose file is not in the
            bundle. Optional.
        :type reference: dict
        :return: The resolved JSON node with all references resolved.
        :rtype: dict
        :raises RefResolutionError: If a ref names a missing file or a dangling
            pointer and no fallback can satisfy it.
        :raises CircularRefError: If a reference chain loops.
        """
        logger.info("Resolving references in schema.")
        resolver = _BundleResolver(self.schema, fallback_reference=reference)
        return resolver.resolve_input(schema)

    def resolve_all_references(self, strict: bool = True) -> list:
        """
        Resolve references in all schema node dictionaries against the bundle.

        :param strict: When True (default), an unresolvable reference raises
            :class:`SchemaResolutionError` — a node is never silently dropped.
            When False, restores the legacy behaviour: the error is logged and
            the affected node is omitted from the result.
        :type strict: bool
        :return: A list of resolved schema dictionaries, one for each node.
        :rtype: list
        """
        logger.info("Resolving all references in schema list.")
        logger.info("=== Resolving Schema References ===")

        resolver = self._resolver or _BundleResolver(
            self.schema, fallback_reference=self.schema_def_resolved
        )

        resolved_schema_list = []
        for node in self.get_nodes():
            if node == "_definitions.yaml" or node == "_terms.yaml":
                continue

            try:
                resolved_schema_list.append(resolver.resolve_node(self.schema[node], node))
                logger.info(f"Resolved {node}")
            except SchemaResolutionError as e:
                logger.error(f"Error resolving {node}: {e}")
                if strict:
                    raise
                logger.warning(f"strict=False: dropping unresolvable node {node}")

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
            3. Resolves the definitions schema against the whole bundle (refs
               into ``_terms.yaml`` and bare refs resolve transparently).
            4. Resolves all references in each node schema, each ``$ref``
               against the bundle file it names.
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
        :raises SchemaResolutionError: If any reference cannot be resolved.
        """
        logger.info("Starting schema resolution process.")
        self.parse_schema()

        self.schema_def = self.return_schema("_definitions.yaml")
        logger.info("Retrieved definitions schema.")
        self.schema_term = self.return_schema("_terms.yaml")
        logger.info("Retrieved terms schema.")

        self._resolver = _BundleResolver(self.schema)
        if "_definitions.yaml" in self.schema and self.schema["_definitions.yaml"] is not None:
            self.schema_def_resolved = self._resolver.resolve_document("_definitions.yaml")
        else:
            self.schema_def_resolved = self.schema_def
        logger.info("Resolved references in definitions schema.")

        self.schema_list_resolved = self.resolve_all_references()
        logger.info("Resolved all references in schema list.")

        self.schema_resolved = self.schema_list_to_json(self.schema_list_resolved)
        logger.info("Converted resolved schema list to JSON format.")
