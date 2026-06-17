import argparse
import json
import logging
import sys

from gen3_validator import bulk

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen3-validate",
        description=(
            "Validate a folder of per-node Gen3 JSON files against a Gen3 schema, "
            "processing each node in the sequence given by the data import order file."
        ),
    )
    parser.add_argument(
        "folder",
        help="Path to the folder containing the <node>.json files and the import order file.",
    )
    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        help="Path to the (unresolved) Gen3 JSON schema file.",
    )
    parser.add_argument(
        "--order-file",
        default=bulk.DEFAULT_IMPORT_ORDER_FILENAME,
        help=(
            "Name of the import order file within the folder "
            f"(default: {bulk.DEFAULT_IMPORT_ORDER_FILENAME})."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to write the JSON report. If omitted, the report is printed to stdout.",
    )
    parser.add_argument(
        "--no-link-check",
        action="store_true",
        help=(
            "Disable cross-node reference integrity checks (validate each node's records "
            "against the schema only)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (INFO-level) logging.",
    )
    return parser


def main(argv=None) -> int:
    """
    Command-line entry point for bulk folder validation.

    Resolves the schema, validates the folder in import order (schema validation plus
    cross-node reference integrity unless ``--no-link-check`` is given), emits the flat JSON
    report (to a file with ``-o`` or to stdout otherwise), prints a summary to stderr, and
    returns an exit code: ``1`` if any record is a FAIL or ERROR, ``0`` if the folder is
    clean, and ``2`` for input errors (e.g. a missing import order file or unreadable schema).

    :param argv: Optional argument list (defaults to ``sys.argv[1:]``).
    :return: Process exit code.
    :rtype: int
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        report = bulk.validate_data_folder_from_schema(
            args.folder,
            args.schema,
            args.order_file,
            check_links=not args.no_link_check,
        )
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    report_json = json.dumps(report, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_json)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report_json)

    fail_count = sum(1 for r in report if r.get("validation_result") == "FAIL")
    error_count = sum(1 for r in report if r.get("validation_result") == "ERROR")
    print(
        f"Bulk validation complete: {fail_count} failure(s), {error_count} error(s).",
        file=sys.stderr,
    )

    return 1 if (fail_count or error_count) else 0


if __name__ == "__main__":
    sys.exit(main())
