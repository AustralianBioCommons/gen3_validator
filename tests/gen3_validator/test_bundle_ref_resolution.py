"""Tests for bundle-aware ``$ref`` resolution in :class:`ResolveSchema`.

Background
----------
A Gen3 data dictionary is authored as one YAML file per node and bundled into
a single ``schema.json`` whose top-level keys are the *filenames*::

    {"case.yaml": {...}, "_definitions.yaml": {...}, "_terms.yaml": {...}}

References between files use a file-qualified form,
``{"$ref": "_terms.yaml#/some_term"}``, while references within the same file
are bare, ``{"$ref": "#/some_key"}``. The official Gen3 dictionary places
``term: {"$ref": "_terms.yaml#/..."}`` blocks directly inside node files.

Historically the resolver ignored the file part of a ``$ref`` and looked every
file-qualified reference up in a single "reference" document. Three real bugs
followed:

1. A node containing ``_terms.yaml#/x`` hit a ``KeyError`` (the key was looked
   up in ``_definitions.yaml``) and the whole node was silently dropped from
   the resolved schema — meaning that node's data was never validated, with no
   error surfaced to the caller.
2. When the same key existed in both ``_terms.yaml`` and ``_definitions.yaml``
   (``UUID`` does, in real dictionaries), the reference silently resolved to
   the wrong document's content.
3. A bare ``#/x`` reference inside a ``_definitions.yaml`` fragment that had
   been inlined into a node resolved against the node file instead of
   ``_definitions.yaml``.

These tests pin the fixed behaviour: every ``$ref`` resolves against the file
named in the reference (or the file it physically appears in, for bare refs),
and unresolvable references fail loudly with a typed exception instead of
silently dropping data.
"""

import copy
import json
from pathlib import Path

import pytest

from gen3_validator.resolve_schema import (
    CircularRefError,
    RefResolutionError,
    ResolveSchema,
    SchemaResolutionError,
)

REAL_FIXTURE = Path(__file__).resolve().parents[1] / "schema" / "gen3_test_schema.json"


def make_resolver(monkeypatch, bundle: dict) -> ResolveSchema:
    """Build a ResolveSchema whose file read returns ``bundle``.

    The class normally reads a schema.json from disk; monkeypatching
    ``read_json`` lets each test supply a small hand-written bundle instead,
    which keeps the inputs of every test visible in the test itself.
    """
    resolver = ResolveSchema("unused.json")
    monkeypatch.setattr(resolver, "read_json", lambda path: bundle)
    return resolver


@pytest.fixture
def mini_bundle() -> dict:
    """A minimal but complete Gen3-style schema bundle.

    Contents are chosen to exercise every resolution path:

    - ``sample.yaml`` references ``_terms.yaml`` directly (the shape the
      official dictionary uses and the old resolver crashed on);
    - ``UUID`` exists in BOTH ``_terms.yaml`` and ``_definitions.yaml`` with
      different content, so a file-blind resolver picks the wrong one;
    - ``_definitions.yaml#/wrapper`` contains a bare ``#/datetime_inner``
      reference, which must resolve against ``_definitions.yaml`` even after
      the fragment is inlined into a node;
    - ``_definitions.yaml#/with_term`` nests a reference into ``_terms.yaml``
      (transitive resolution across files);
    - ``sample.yaml``'s ``direct_term`` carries a sibling ``description`` next
      to its ``$ref``, pinning the merge rule that sibling keys win.
    """
    return {
        "_settings.yaml": {"_dict_version": "9.9.9"},
        "_terms.yaml": {
            "sample_term": {"description": "A term about samples"},
            "UUID": {"description": "terms-flavoured UUID"},
        },
        "_definitions.yaml": {
            "UUID": {"type": "string", "format": "uuid"},
            "datetime_inner": {"type": "string", "format": "date-time"},
            "wrapper": {"$ref": "#/datetime_inner"},
            "with_term": {
                "type": "number",
                "term": {"$ref": "_terms.yaml#/sample_term"},
            },
        },
        "sample.yaml": {
            "id": "sample",
            "properties": {
                "sample_id": {"$ref": "_definitions.yaml#/UUID"},
                "term_uuid": {"$ref": "_terms.yaml#/UUID"},
                "collected_at": {"$ref": "_definitions.yaml#/wrapper"},
                "measure": {"$ref": "_definitions.yaml#/with_term"},
                "direct_term": {
                    "$ref": "_terms.yaml#/sample_term",
                    "description": "override",
                },
            },
        },
    }


def resolved_sample(monkeypatch, bundle):
    """Run the full resolution pipeline and return sample.yaml's properties."""
    resolver = make_resolver(monkeypatch, bundle)
    resolver.resolve_schema()
    return resolver, resolver.schema_resolved["sample.yaml"]["properties"]


def test_node_ref_into_terms_resolves(monkeypatch, mini_bundle):
    """A node-level reference into _terms.yaml resolves and the node survives.

    This is the primary bug: the official Gen3 dictionary puts
    ``term: {"$ref": "_terms.yaml#/..."}`` inside node files, and the old
    resolver raised KeyError there and then silently dropped the node from
    ``schema_resolved`` — so the node's data was never validated at all.

    Input: sample.yaml/properties/term_uuid -> {"$ref": "_terms.yaml#/UUID"}.
    Expected: sample.yaml is present in schema_resolved and term_uuid equals
    the _terms.yaml entry.
    """
    resolver, props = resolved_sample(monkeypatch, mini_bundle)
    assert "sample.yaml" in resolver.schema_resolved
    assert props["term_uuid"] == {"description": "terms-flavoured UUID"}


def test_collision_key_resolves_against_named_file(monkeypatch, mini_bundle):
    """A key present in both _terms and _definitions resolves per the ref's file.

    Real dictionaries define ``UUID`` in both files with different content.
    The old resolver looked every file-qualified ref up in one document, so
    ``_terms.yaml#/UUID`` silently returned the _definitions flavour — wrong
    content with no error, which is worse than a crash.

    Input: sample_id refs _definitions.yaml#/UUID; term_uuid refs
    _terms.yaml#/UUID.
    Expected: each resolves to its own file's content.
    """
    _, props = resolved_sample(monkeypatch, mini_bundle)
    assert props["sample_id"] == {"type": "string", "format": "uuid"}
    assert props["term_uuid"] == {"description": "terms-flavoured UUID"}


def test_bare_ref_resolves_against_its_own_file(monkeypatch, mini_bundle):
    """A bare ``#/x`` ref inside a _definitions fragment resolves in _definitions.

    ``_definitions.yaml#/wrapper`` is ``{"$ref": "#/datetime_inner"}``. When a
    node references ``wrapper``, the bare inner ref must still resolve against
    ``_definitions.yaml`` — the file it physically lives in — not against the
    node that happened to pull it in (which is what the old closure-based
    resolver did).

    Expected: collected_at resolves through the chain to the date-time type.
    """
    _, props = resolved_sample(monkeypatch, mini_bundle)
    assert props["collected_at"] == {"type": "string", "format": "date-time"}


def test_transitive_terms_ref_through_definitions(monkeypatch, mini_bundle):
    """A defs entry nesting a _terms ref resolves transitively, and
    schema_def_resolved is still populated as a byproduct.

    Input: measure refs _definitions.yaml#/with_term, which itself contains
    term -> {"$ref": "_terms.yaml#/sample_term"}.
    Expected: the nested term resolves to the _terms content, both in the node
    and in the schema_def_resolved attribute the public API promises.
    """
    resolver, props = resolved_sample(monkeypatch, mini_bundle)
    assert props["measure"]["term"] == {"description": "A term about samples"}
    assert resolver.schema_def_resolved["with_term"]["term"] == {
        "description": "A term about samples"
    }


def test_sibling_keys_override_resolved_content(monkeypatch, mini_bundle):
    """Keys sitting next to a ``$ref`` override the resolved content.

    Gen3 schemas rely on this merge rule (e.g. overriding a description while
    reusing a shared definition), and downstream consumers depend on it — so
    the fix must not change it.

    Input: direct_term has both a $ref to sample_term (description "A term
    about samples") and its own description "override".
    Expected: the sibling wins.
    """
    _, props = resolved_sample(monkeypatch, mini_bundle)
    assert props["direct_term"]["description"] == "override"


def test_missing_file_raises_with_context(monkeypatch, mini_bundle):
    """A ref to a file absent from the bundle raises a clear, typed error.

    The old behaviour was a KeyError swallowed by resolve_all_references,
    which dropped the node silently. A validation platform must fail loudly:
    a missing file means the dictionary is broken, and the error must say
    which ref, in which file, could not be resolved.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["sample.yaml"]["properties"]["broken"] = {"$ref": "_nope.yaml#/x"}
    resolver = make_resolver(monkeypatch, bundle)
    with pytest.raises(RefResolutionError) as excinfo:
        resolver.resolve_schema()
    message = str(excinfo.value)
    assert "_nope.yaml#/x" in message
    assert "_nope.yaml" in message
    assert "sample.yaml" in message


def test_dangling_pointer_raises_with_segment(monkeypatch, mini_bundle):
    """A ref whose pointer path does not exist names the failing segment.

    Input: a ref to _definitions.yaml#/does_not_exist.
    Expected: RefResolutionError naming 'does_not_exist', the target file and
    the source file, so an operator can fix the dictionary from the message
    alone.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["sample.yaml"]["properties"]["broken"] = {
        "$ref": "_definitions.yaml#/does_not_exist"
    }
    resolver = make_resolver(monkeypatch, bundle)
    with pytest.raises(RefResolutionError) as excinfo:
        resolver.resolve_schema()
    message = str(excinfo.value)
    assert "does_not_exist" in message
    assert "_definitions.yaml" in message
    assert "sample.yaml" in message


def test_cycle_raises_circular_ref_error(monkeypatch, mini_bundle):
    """A circular ref chain raises CircularRefError, not RecursionError.

    The old resolver had no cycle detection, so ``a -> b -> a`` recursed until
    Python's stack limit. A typed error with the chain in the message makes
    the dictionary bug diagnosable.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["_definitions.yaml"]["a"] = {"$ref": "#/b"}
    bundle["_definitions.yaml"]["b"] = {"$ref": "#/a"}
    bundle["sample.yaml"]["properties"]["loop"] = {"$ref": "_definitions.yaml#/a"}
    resolver = make_resolver(monkeypatch, bundle)
    with pytest.raises(CircularRefError) as excinfo:
        resolver.resolve_schema()
    message = str(excinfo.value)
    assert "a" in message and "b" in message


def test_tilde_escaped_pointer_segments(monkeypatch, mini_bundle):
    """JSON-pointer escapes ``~1`` (/) and ``~0`` (~) are honoured (RFC 6901).

    Keys containing '/' or '~' are legal in JSON and must be addressable;
    the old two-line pointer walk never unescaped them.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["_definitions.yaml"]["a/b"] = {"type": "string"}
    bundle["_definitions.yaml"]["x~y"] = {"type": "integer"}
    bundle["sample.yaml"]["properties"]["slash"] = {"$ref": "_definitions.yaml#/a~1b"}
    bundle["sample.yaml"]["properties"]["tilde"] = {"$ref": "_definitions.yaml#/x~0y"}
    _, props = resolved_sample(monkeypatch, bundle)
    assert props["slash"] == {"type": "string"}
    assert props["tilde"] == {"type": "integer"}


def test_no_node_silently_dropped(monkeypatch, mini_bundle):
    """Every non-definitions/terms bundle entry appears in the resolved list.

    The silent-drop failure mode meant "resolution succeeded" and "every node
    was resolved" were different statements. Now they are the same statement:
    the resolved list must contain _settings.yaml plus every node.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["subject.yaml"] = {
        "id": "subject",
        "properties": {"note": {"$ref": "_terms.yaml#/sample_term"}},
    }
    resolver = make_resolver(monkeypatch, bundle)
    resolver.resolve_schema()
    # _settings.yaml + sample.yaml + subject.yaml (definitions/terms excluded)
    assert len(resolver.schema_list_resolved) == 3
    assert "sample.yaml" in resolver.schema_resolved
    assert "subject.yaml" in resolver.schema_resolved


def test_legacy_resolve_references_signature_still_works():
    """The two-argument resolve_references(schema, reference) call still works.

    resolve_references is star-exported from the package, so third-party code
    may call it directly on an instance that never loaded a bundle. In that
    case file-qualified refs must fall back to the supplied reference
    document, exactly as before the fix.
    """
    resolver = ResolveSchema("unused.json")
    schema = {
        "id": "subject",
        "properties": {"foo": {"$ref": "_definitions.yaml#/bar"}},
    }
    reference = {"bar": {"type": "string", "description": "A bar property"}}
    resolved = resolver.resolve_references(schema, reference)
    assert resolved["properties"]["foo"]["type"] == "string"
    assert resolved["properties"]["foo"]["description"] == "A bar property"
    assert resolved["id"] == "subject"


def test_resolved_nodes_do_not_share_mutable_state(monkeypatch, mini_bundle):
    """Two nodes resolving the same definition get independent copies.

    The resolver memoizes shared fragments for speed; the memo must hand out
    copies, otherwise mutating one resolved node (as downstream tooling does)
    would silently corrupt every other node that referenced the same
    definition.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["subject.yaml"] = {
        "id": "subject",
        "properties": {"subject_id": {"$ref": "_definitions.yaml#/UUID"}},
    }
    resolver = make_resolver(monkeypatch, bundle)
    resolver.resolve_schema()
    sample_props = resolver.schema_resolved["sample.yaml"]["properties"]
    subject_props = resolver.schema_resolved["subject.yaml"]["properties"]
    sample_props["sample_id"]["format"] = "MUTATED"
    assert subject_props["subject_id"]["format"] == "uuid"


def test_strict_false_restores_log_and_drop(monkeypatch, mini_bundle):
    """strict=False on resolve_all_references restores the legacy behaviour.

    Some callers may prefer a partial result over a hard failure while
    migrating. With strict=False a node with an unresolvable ref is logged
    and dropped (the pre-fix behaviour) instead of raising.
    """
    bundle = copy.deepcopy(mini_bundle)
    bundle["broken.yaml"] = {
        "id": "broken",
        "properties": {"x": {"$ref": "_nope.yaml#/x"}},
    }
    resolver = make_resolver(monkeypatch, bundle)
    resolver.parse_schema()
    resolver.schema_def = resolver.return_schema("_definitions.yaml")
    resolver.schema_term = resolver.return_schema("_terms.yaml")
    resolver.schema_def_resolved = resolver.resolve_references(
        resolver.schema["_definitions.yaml"]
    )
    resolved_list = resolver.resolve_all_references(strict=False)
    ids = {n.get("id") for n in resolved_list}
    assert "sample" in ids
    assert "broken" not in ids


def test_real_fixture_with_node_level_term_ref(monkeypatch, tmp_path):
    """Regression: the official-dictionary shape resolves end to end.

    The bundled 31-file test fixture never had node-level refs into
    _terms.yaml, which is exactly why the original bug survived the test
    suite. This test injects one (the shape the official Gen3 dictionary
    uses) into demographic.yaml and requires full resolution to succeed.
    """
    bundle = json.loads(REAL_FIXTURE.read_text())
    bundle["demographic.yaml"]["properties"]["regression_term_prop"] = {
        "$ref": "_terms.yaml#/age_at_diagnosis"
    }
    expected = bundle["_terms.yaml"]["age_at_diagnosis"]
    resolver = make_resolver(monkeypatch, bundle)
    resolver.resolve_schema()
    assert "demographic.yaml" in resolver.schema_resolved
    resolved_prop = resolver.schema_resolved["demographic.yaml"]["properties"][
        "regression_term_prop"
    ]
    assert resolved_prop == expected
    # 31 bundle files minus _definitions.yaml and _terms.yaml
    assert len(resolver.schema_list_resolved) == 29


def test_real_fixture_full_resolution():
    """The unmodified realistic fixture resolves without error.

    This is the first test to actually parse the 31-node fixture from disk
    (earlier tests always mocked the file read), so it also protects the
    fixture's 144 refs into _definitions.yaml, 27 bare refs, and the 11
    definitions-to-terms refs.
    """
    resolver = ResolveSchema(str(REAL_FIXTURE))
    resolver.resolve_schema()
    assert len(resolver.schema_list_resolved) == 29
    demographic = resolver.schema_resolved["demographic.yaml"]
    # ubiquitous_properties from _definitions.yaml must be inlined
    assert "submitter_id" in demographic["properties"]
    assert "$ref" not in demographic["properties"]
    assert resolver.get_schema_version() == "3.1.0"
