import json
import os

import pytest

from gen3_validator import cli


@pytest.fixture
def fixture_schema_path() -> str:
    """Path to the bundled test schema (the same one used by the other test modules)."""
    current_dir = os.path.dirname(__file__)
    return os.path.join(current_dir, "..", "schema", "gen3_test_schema.json")


def _write(folder, name, content) -> str:
    """Write a node JSON file (dict/list) or the import order file (str) into ``folder``."""
    path = os.path.join(str(folder), name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f)
    return path


MH_VALID = {
    "submitter_id": "medical_history_1",
    "atrial_fibrillation": "yes",
    "cabg": "yes",
    "type": "medical_history",
}
MH_INVALID = {
    "submitter_id": "medical_history_2",
    "atrial_fibrillation": "NOPE",  # not in the ['yes', 'no'] enum
    "cabg": "yes",
    "type": "medical_history",
}


def test_cli_exit_code_clean(tmp_path, fixture_schema_path, capsys):
    """
    A folder with only valid records prints an empty JSON report to stdout and exits 0,
    so the command can be used as a pass/fail gate in scripts and CI.
    """
    _write(tmp_path, "medical_history.json", [MH_VALID])
    _write(tmp_path, "DataImportOrder.txt", "medical_history\n")
    code = cli.main([str(tmp_path), "-s", fixture_schema_path])
    out = capsys.readouterr().out
    assert json.loads(out) == []
    assert code == 0


def test_cli_exit_code_failure(tmp_path, fixture_schema_path, capsys):
    """
    A folder containing an invalid record prints the failures as JSON (each tagged with
    its source_file) and exits 1.
    """
    _write(tmp_path, "medical_history.json", [MH_INVALID])
    _write(tmp_path, "DataImportOrder.txt", "medical_history\n")
    code = cli.main([str(tmp_path), "-s", fixture_schema_path])
    report = json.loads(capsys.readouterr().out)
    assert report[0]["source_file"] == "medical_history.json"
    assert code == 1


def test_cli_missing_order_file_exit_2(tmp_path, fixture_schema_path, capsys):
    """
    Input errors (here, a missing import order file) exit with code 2 and an error message
    on stderr, distinct from the validation-failure exit code 1.
    """
    code = cli.main([str(tmp_path), "-s", fixture_schema_path])
    err = capsys.readouterr().err
    assert code == 2
    assert "error" in err.lower()


def test_cli_writes_output_file(tmp_path, fixture_schema_path):
    """
    With ``-o``, the JSON report is written to the given file instead of stdout, while the
    failure exit code is still returned.
    """
    folder = tmp_path / "data"
    folder.mkdir()
    _write(folder, "medical_history.json", [MH_INVALID])
    _write(folder, "DataImportOrder.txt", "medical_history\n")
    out_path = tmp_path / "report.json"

    code = cli.main([str(folder), "-s", fixture_schema_path, "-o", str(out_path)])
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written[0]["node"] == "medical_history"
    assert code == 1


def test_cli_no_link_check_disables_link_validation(tmp_path, fixture_schema_path, capsys):
    """
    A folder with a dangling cross-node reference exits 1 by default (the broken link is
    reported), but exits 0 with --no-link-check, which validates schemas only.

    The sample points at a clinical_descriptor that does not exist; the records themselves
    are otherwise schema-valid, so link checking is the only thing that can fail here.
    """
    _write(tmp_path, "clinical_descriptor.json", [
        {"submitter_id": "clinical_descriptor_1", "type": "clinical_descriptor"},
    ])
    _write(tmp_path, "sample.json", [
        {
            "submitter_id": "sample_1",
            "type": "sample",
            "clinical_descriptors": {"submitter_id": "clinical_descriptor_MISSING"},
        },
    ])
    _write(tmp_path, "DataImportOrder.txt", "clinical_descriptor\nsample\n")

    code_default = cli.main([str(tmp_path), "-s", fixture_schema_path])
    report_default = json.loads(capsys.readouterr().out)
    assert any(r["validator"] == "link" for r in report_default)
    assert code_default == 1

    code_no_links = cli.main([str(tmp_path), "-s", fixture_schema_path, "--no-link-check"])
    report_no_links = json.loads(capsys.readouterr().out)
    assert not any(r["validator"] == "link" for r in report_no_links)
    assert code_no_links == 0
