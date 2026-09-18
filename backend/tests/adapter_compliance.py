import json
import re

from app.ingestion.base import CanonicalDocument, FormatAdapter


def assert_adapter_capabilities(adapter: FormatAdapter) -> None:
    """Reusable contract check that every future format adapter must pass."""
    capabilities = adapter.capabilities
    assert capabilities.extensions
    assert all(value.startswith(".") for value in capabilities.extensions)
    assert capabilities.media_types
    assert capabilities.unit_kinds
    assert adapter.source_format
    assert adapter.adapter_id
    assert adapter.adapter_version


def assert_canonical_document_contract(result: CanonicalDocument) -> None:
    assert result.outcome in {"COMPLETE", "PARTIAL"}
    assert result.units
    assert [unit.ordinal for unit in result.units] == list(range(len(result.units)))
    assert len({unit.ordinal for unit in result.units}) == len(result.units)
    for unit in result.units:
        assert unit.kind
        assert unit.content_type
        assert unit.status in {"USABLE", "SKIPPED", "FAILED"}
        assert unit.locator.get("v") == 1
        assert unit.extraction_method
        assert unit.character_count == len(unit.text)
        if unit.status == "USABLE":
            assert unit.text
            assert unit.issue_code is None
        else:
            assert unit.issue_code
    assert result.diagnostics["unit_count"] == len(result.units)
    assert result.diagnostics["usable_unit_count"] == sum(
        unit.status == "USABLE" for unit in result.units
    )
    assert result.diagnostics["failed_unit_count"] == sum(
        unit.status == "FAILED" for unit in result.units
    )
    serialized_diagnostics = json.dumps(
        result.diagnostics, ensure_ascii=False, sort_keys=True
    )
    assert not re.search(r"[A-Za-z]:\\", serialized_diagnostics)
    assert "traceback" not in serialized_diagnostics.casefold()
    assert "api_key" not in serialized_diagnostics.casefold()
    assert "credential" not in serialized_diagnostics.casefold()
    for unit in result.units:
        # Counts, codes, and structural summaries belong in diagnostics; source
        # text does not. Ignore tiny values that can naturally equal labels.
        if len(unit.text) >= 24:
            assert unit.text not in serialized_diagnostics
