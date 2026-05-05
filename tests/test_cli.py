"""Tests for numinal CLI — init and validate commands."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from numinal.commands.validate import validate, load_card
from numinal.commands.init import run_init
from numinal.detection.auto import detect
from numinal.schema.vocabularies import (
    CONSUMER_TYPES,
    PURPOSES,
    PURPOSE_MODIFIERS,
    HIGH_RISK_DOMAINS,
    DATA_CLASSIFICATIONS,
    GOVERNANCE_MODELS,
    validate_term,
    is_custom_term,
)
from numinal.schema.tiers import (
    requirements_for_tier,
    _resolve_path,
    _is_populated,
    _MISSING,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dataset(tmp_path):
    """Create a minimal test dataset directory."""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,name,value\n1,Alice,10\n2,Bob,20\n3,,30\n")
    (tmp_path / "LICENSE").write_text("MIT License")
    (tmp_path / "README.md").write_text("# Test Dataset\n")
    return tmp_path


@pytest.fixture
def minimal_t1_card(tmp_path):
    """Create a minimal T1-passing data card."""
    card = {
        "name": "test-dataset",
        "description": "A test dataset",
        "version": "1.0.0",
        "license": "MIT",
        "creator": "Test Author",
        "distribution": [{"name": "data", "contentType": "text/csv"}],
        "gov": {
            "governanceModel": "open",
            "governanceVersion": "1.0.0",
        },
    }
    path = tmp_path / "numinal.yaml"
    path.write_text(yaml.dump(card), encoding="utf-8")
    return path, card


@pytest.fixture
def full_t3_card(tmp_path):
    """Create a comprehensive T3-passing data card."""
    card = {
        "name": "test-governed-dataset",
        "description": "A fully governed test dataset",
        "version": "1.0.0",
        "license": "OGL-UK-3.0",
        "creator": "Test Organisation",
        "datePublished": "2026-01-01",
        "distribution": [{"name": "data", "contentType": "text/csv"}],
        "recordSet": [{"name": "records", "fields": [{"name": "id", "dataType": "string"}]}],
        "gov": {
            "governanceModel": "controlled",
            "governanceVersion": "1.0.0",
            "dataController": {"name": "Test Org", "contactEmail": "dpo@test.org"},
            "dataClassification": "official",
            "legalBasis": "legitimate-interest",
            "regulatoryAlignment": ["eu-ai-act-art-10"],
            "lastGovernanceReview": "2026-01-01",
            "licenseGovernanceRelationship": {
                "relationship": "governance-supersedes",
                "explanation": "Governance policies control data access",
            },
            "accessPolicies": [
                {
                    "policyId": "test-policy",
                    "eligibility": {"consumerType": ["uk-university"]},
                    "permittedPurposes": ["model-training"],
                    "accessScope": {"scopeType": "full", "accessMethod": "bulk-download"},
                    "retention": {"maxRetentionDays": 365, "retentionType": "fixed"},
                    "redistribution": {"redistributionPermitted": False},
                    "prerequisites": [{"prerequisiteType": "agreement"}],
                    "intendedDatasetRole": ["training"],
                },
            ],
        },
        "rai": {
            "designChoices": {"designObjective": "Testing"},
            "dataCollection": "Collected for testing",
            "dataOrigin": {"sources": [{"name": "test"}], "personalDataPresent": False},
            "dataPreparation": {"cleaning": {"performed": True, "description": "Cleaned"}},
            "measurementAssumptions": [{"field": "id", "assumption": "Unique identifier"}],
            "suitabilityAssessment": {"quantityAssessment": "Sufficient"},
            "biasExamination": {"healthSafetyBiases": [], "discriminationBiases": []},
            "complianceGaps": [{"gap": "None identified", "severity": "low"}],
            "dataQualityAssessment": {"relevance": {"assessment": "Relevant"}},
            "geographicContext": {"dataOriginCountries": ["GB"]},
            "contextualCharacteristics": {"languageCharacteristics": "English"},
        },
    }
    path = tmp_path / "numinal.yaml"
    path.write_text(yaml.dump(card), encoding="utf-8")
    return path, card


# ---------------------------------------------------------------------------
# Vocabulary tests
# ---------------------------------------------------------------------------

class TestVocabularies:
    """Test controlled vocabulary definitions from spec §3."""

    def test_consumer_types_complete(self):
        """All consumer types from spec §3.1 are present."""
        # Spot-check key terms from each category
        assert "uk-ministerial-dept" in CONSUMER_TYPES
        assert "uk-nhs-trust" in CONSUMER_TYPES
        assert "uk-startup" in CONSUMER_TYPES
        assert "uk-university" in CONSUMER_TYPES
        assert "uk-charity" in CONSUMER_TYPES
        assert "eu-registered-entity" in CONSUMER_TYPES
        assert "individual-researcher" in CONSUMER_TYPES

    def test_purposes_complete(self):
        """All purposes from spec §3.2 are present."""
        # DUO-sourced
        assert "general-research" in PURPOSES
        assert "health-biomedical-research" in PURPOSES
        # numinal-defined
        assert "model-training" in PURPOSES
        assert "model-fine-tuning" in PURPOSES
        assert "bias-auditing" in PURPOSES
        assert "red-teaming" in PURPOSES
        assert "synthetic-data-generation" in PURPOSES

    def test_purpose_modifiers_complete(self):
        """All purpose modifiers from spec §3.2 are present."""
        assert "geographic-restriction" in PURPOSE_MODIFIERS
        assert "ethics-approval-required" in PURPOSE_MODIFIERS
        assert "publication-required" in PURPOSE_MODIFIERS

    def test_high_risk_domains_complete(self):
        """All Annex III domains from spec §3.3 are present."""
        assert len(HIGH_RISK_DOMAINS) == 9  # 8 Annex III + not-high-risk
        assert "biometrics" in HIGH_RISK_DOMAINS
        assert "not-high-risk" in HIGH_RISK_DOMAINS

    def test_data_classifications(self):
        """All GSCP classifications from spec §3.4 are present."""
        assert DATA_CLASSIFICATIONS == {
            "official", "official-sensitive", "secret", "top-secret", "unclassified"
        }

    def test_validate_term_valid(self):
        valid, msg = validate_term("uk-university", CONSUMER_TYPES, "test")
        assert valid is True
        assert msg is None

    def test_validate_term_invalid(self):
        valid, msg = validate_term("not-a-type", CONSUMER_TYPES, "test")
        assert valid is False
        assert "Invalid term" in msg

    def test_validate_term_custom(self):
        """Custom-prefixed terms are valid but produce warnings (spec §2.3 rule 2)."""
        valid, msg = validate_term("custom:my-org-type", CONSUMER_TYPES, "test")
        assert valid is True
        assert "Custom term" in msg

    def test_is_custom_term(self):
        assert is_custom_term("custom:something") is True
        assert is_custom_term("uk-university") is False


# ---------------------------------------------------------------------------
# Tier logic tests
# ---------------------------------------------------------------------------

class TestTiers:
    """Test tier requirement definitions from spec §10."""

    def test_tier_hierarchy(self):
        """T3 ⊇ T2 ⊇ T1 (spec §2.4)."""
        t1 = {r.field_path for r in requirements_for_tier(1)}
        t2 = {r.field_path for r in requirements_for_tier(2)}
        t3 = {r.field_path for r in requirements_for_tier(3)}
        assert t1.issubset(t2), f"T1 not subset of T2: {t1 - t2}"
        assert t2.issubset(t3), f"T2 not subset of T3: {t2 - t3}"

    def test_t1_required_fields(self):
        """T1 requires exactly the fields listed in spec §10 first table."""
        t1_paths = {r.field_path for r in requirements_for_tier(1)}
        expected = {
            "name", "description", "version", "license", "creator",
            "distribution", "gov.governanceModel", "gov.governanceVersion",
        }
        assert t1_paths == expected

    def test_resolve_path(self):
        data = {"a": {"b": {"c": 42}}}
        assert _resolve_path(data, "a.b.c") == 42
        assert isinstance(_resolve_path(data, "a.b.d"), type(_MISSING))
        assert isinstance(_resolve_path(data, "x.y"), type(_MISSING))

    def test_is_populated(self):
        assert _is_populated("hello") is True
        assert _is_populated(0) is True  # Zero is valid
        assert _is_populated(False) is True  # False is valid
        assert _is_populated([1]) is True
        assert _is_populated("") is False
        assert _is_populated("  ") is False
        assert _is_populated([]) is False
        assert _is_populated({}) is False
        assert _is_populated(None) is False
        assert _is_populated(_MISSING) is False


# ---------------------------------------------------------------------------
# Validate command tests
# ---------------------------------------------------------------------------

class TestValidate:
    """Test the validate command."""

    def test_t1_pass(self, minimal_t1_card):
        path, _ = minimal_t1_card
        result = validate(path)
        assert result.parse_error is None
        assert result.tiers[0].passed is True  # T1
        assert result.tiers[0].tier_name == "discovery"

    def test_t2_fail_missing_rai(self, minimal_t1_card):
        """T1 card should fail T2 because RAI fields are missing."""
        path, _ = minimal_t1_card
        result = validate(path)
        t2 = result.tiers[1]
        assert t2.passed is False
        missing_paths = {m.field_path for m in t2.missing}
        assert "rai.designChoices" in missing_paths
        assert "rai.dataCollection" in missing_paths

    def test_t3_pass(self, full_t3_card):
        path, _ = full_t3_card
        result = validate(path)
        for tr in result.tiers:
            assert tr.passed is True, f"Tier {tr.tier} failed: {[m.field_path for m in tr.missing]}"

    def test_vocab_error_detected(self, tmp_path):
        """Invalid vocabulary terms produce errors."""
        card = {
            "name": "test",
            "description": "test",
            "version": "1.0.0",
            "license": "MIT",
            "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "invalid-model",  # Not in vocabulary
                "governanceVersion": "1.0.0",
            },
        }
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(card))
        result = validate(path)
        errors = [w for w in result.vocab_warnings if w.is_error]
        assert len(errors) >= 1
        assert any("invalid-model" in e.term for e in errors)

    def test_custom_term_warning(self, tmp_path):
        """Custom-prefixed terms produce warnings, not errors."""
        card = {
            "name": "test",
            "description": "test",
            "version": "1.0.0",
            "license": "MIT",
            "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "custom:my-model",
                "governanceVersion": "1.0.0",
            },
        }
        path = tmp_path / "custom.yaml"
        path.write_text(yaml.dump(card))
        result = validate(path)
        warnings = [w for w in result.vocab_warnings if not w.is_error]
        assert len(warnings) >= 1
        assert any("custom:my-model" in w.term for w in warnings)

    def test_invalid_file(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("not: [valid: yaml: {{")
        result = validate(path)
        assert result.parse_error is not None

    def test_missing_file(self):
        result = validate("/nonexistent/path.yaml")
        assert result.parse_error is not None

    def test_json_input(self, tmp_path):
        """Validate can read JSON files too."""
        card = {
            "name": "test",
            "description": "test",
            "version": "1.0.0",
            "license": "MIT",
            "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
        }
        path = tmp_path / "card.json"
        path.write_text(json.dumps(card))
        result = validate(path)
        assert result.parse_error is None
        assert result.tiers[0].passed is True

    def test_conditional_personal_data(self, tmp_path):
        """legalBasis is only required at T2 if personal data present."""
        # Without personal data — should not require legalBasis at T2
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test", "datePublished": "2026-01-01",
            "distribution": [{"name": "d"}],
            "recordSet": [{"name": "r"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "dataController": {"name": "x"}, "dataClassification": "unclassified",
            },
            "rai": {
                "designChoices": {"designObjective": "test"},
                "dataCollection": "test",
                "dataOrigin": {"sources": [{"name": "s"}], "personalDataPresent": False},
                "dataPreparation": {"cleaning": {"performed": True}},
                "measurementAssumptions": [{"field": "x"}],
                "suitabilityAssessment": {"quantityAssessment": "ok"},
                "biasExamination": {"healthSafetyBiases": [{"bias": "x"}]},
                "complianceGaps": [{"gap": "none"}],
                "dataQualityAssessment": {"relevance": {"assessment": "ok"}},
                "geographicContext": {"dataOriginCountries": ["GB"]},
            },
        }
        path = tmp_path / "no-pd.yaml"
        path.write_text(yaml.dump(card))
        result = validate(path)
        t2 = result.tiers[1]
        missing_paths = {m.field_path for m in t2.missing}
        assert "gov.legalBasis" not in missing_paths


# ---------------------------------------------------------------------------
# Auto-detection tests
# ---------------------------------------------------------------------------

class TestDetection:
    """Test auto-detection of dataset properties."""

    def test_detect_files(self, tmp_dataset):
        result = detect(tmp_dataset)
        assert len(result.files) == 3
        assert ".csv" in result.file_type_counts

    def test_detect_metadata(self, tmp_dataset):
        result = detect(tmp_dataset)
        assert result.has_existing_license
        assert result.has_existing_readme

    def test_checksums(self, tmp_dataset):
        result = detect(tmp_dataset)
        for f in result.files:
            assert len(f.sha256) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# Init command tests
# ---------------------------------------------------------------------------

class TestInit:
    """Test the init command."""

    def test_init_creates_file(self, tmp_dataset):
        output = run_init(str(tmp_dataset), non_interactive=True)
        assert output.exists()
        assert output.name == "numinal.yaml"

    def test_init_valid_yaml(self, tmp_dataset):
        output = run_init(str(tmp_dataset), non_interactive=True)
        card = yaml.safe_load(output.read_text())
        assert isinstance(card, dict)
        assert card["name"] == tmp_dataset.name

    def test_init_t1_validates(self, tmp_dataset):
        """A generated T1 card should pass T1 validation."""
        output = run_init(str(tmp_dataset), non_interactive=True, tier=1)
        result = validate(output)
        assert result.tiers[0].passed is True

    def test_init_t2_scaffolds_rai(self, tmp_dataset):
        """A T2 init should scaffold RAI fields."""
        output = run_init(str(tmp_dataset), non_interactive=True, tier=2)
        card = yaml.safe_load(output.read_text())
        assert "rai" in card
        assert "designChoices" in card["rai"]
        assert "biasExamination" in card["rai"]

    def test_init_t3_scaffolds_gov(self, tmp_dataset):
        """A T3 init should scaffold access policies."""
        output = run_init(str(tmp_dataset), non_interactive=True, tier=3)
        card = yaml.safe_load(output.read_text())
        assert "accessPolicies" in card["gov"]
        assert len(card["gov"]["accessPolicies"]) >= 1

    def test_init_has_file_manifest(self, tmp_dataset):
        output = run_init(str(tmp_dataset), non_interactive=True)
        card = yaml.safe_load(output.read_text())
        assert "_fileManifest" in card
        assert len(card["_fileManifest"]) == 3
        for f in card["_fileManifest"]:
            assert "sha256" in f
            assert "sizeBytes" in f

    def test_init_t1_omits_record_set(self, tmp_dataset):
        """T1 init should not include a recordSet — schema is publisher-supplied at T2+."""
        output = run_init(str(tmp_dataset), non_interactive=True, tier=1)
        card = yaml.safe_load(output.read_text())
        assert "recordSet" not in card

    def test_init_t2_scaffolds_empty_record_set(self, tmp_dataset):
        """T2 init scaffolds an empty recordSet for the publisher to fill in."""
        output = run_init(str(tmp_dataset), non_interactive=True, tier=2)
        card = yaml.safe_load(output.read_text())
        assert card.get("recordSet") == []


# ---------------------------------------------------------------------------
# Croissant bootstrap tests
# ---------------------------------------------------------------------------

class TestCroissantBootstrap:
    """Test the Croissant JSON-LD loader and field extractor."""

    @pytest.fixture
    def croissant_doc(self):
        """A minimal Croissant JSON-LD document covering the fields we map."""
        return {
            "@context": {
                "@vocab": "https://schema.org/",
                "cr": "http://mlcommons.org/croissant/",
                "sc": "https://schema.org/",
            },
            "@type": "sc:Dataset",
            "name": "uk-health-corpus",
            "description": "Anonymised NHS corpus for AI research.",
            "version": "2.1.0",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "creator": {"@type": "sc:Organization", "name": "NHS England"},
            "datePublished": "2025-09-01",
            "distribution": [
                {
                    "@type": "cr:FileObject",
                    "name": "records.csv",
                    "encodingFormat": "text/csv",
                    "contentSize": "10485760",
                    "sha256": "abc123",
                },
            ],
            "recordSet": [
                {
                    "@type": "cr:RecordSet",
                    "name": "patients",
                    "description": "One row per encounter.",
                    "field": [
                        {"@type": "cr:Field", "name": "patient_id", "dataType": "sc:Text"},
                        {"@type": "cr:Field", "name": "age", "dataType": "sc:Integer"},
                    ],
                },
            ],
        }

    def test_load_croissant_from_file(self, tmp_path, croissant_doc):
        from numinal.detection.croissant import load_croissant
        path = tmp_path / "croissant.json"
        path.write_text(json.dumps(croissant_doc), encoding="utf-8")
        loaded = load_croissant(str(path))
        assert loaded["name"] == "uk-health-corpus"

    def test_load_croissant_missing_file(self, tmp_path):
        from numinal.detection.croissant import load_croissant
        with pytest.raises(FileNotFoundError):
            load_croissant(str(tmp_path / "nope.json"))

    def test_load_croissant_invalid_json(self, tmp_path):
        from numinal.detection.croissant import load_croissant
        path = tmp_path / "bad.json"
        path.write_text("{ not valid", encoding="utf-8")
        with pytest.raises(RuntimeError, match="not valid JSON"):
            load_croissant(str(path))

    def test_extract_bootstrap_top_level_fields(self, croissant_doc):
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap(croissant_doc)
        assert bootstrap["name"] == "uk-health-corpus"
        assert bootstrap["description"].startswith("Anonymised")
        assert bootstrap["version"] == "2.1.0"
        assert bootstrap["license"].startswith("https://creativecommons.org")
        assert bootstrap["creator"] == "NHS England"
        assert bootstrap["datePublished"] == "2025-09-01"

    def test_extract_bootstrap_distribution(self, croissant_doc):
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap(croissant_doc)
        dist = bootstrap["distribution"]
        assert len(dist) == 1
        assert dist[0]["name"] == "records.csv"
        assert dist[0]["contentType"] == "text/csv"
        assert dist[0]["totalSizeBytes"] == 10485760
        assert dist[0]["sha256"] == "abc123"

    def test_extract_bootstrap_record_set(self, croissant_doc):
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap(croissant_doc)
        rs = bootstrap["recordSet"]
        assert len(rs) == 1
        assert rs[0]["name"] == "patients"
        field_names = {f["name"] for f in rs[0]["fields"]}
        assert field_names == {"patient_id", "age"}

    def test_extract_bootstrap_creator_as_string(self):
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap({"creator": "Solo Author"})
        assert bootstrap["creator"] == "Solo Author"

    def test_extract_bootstrap_creator_list(self):
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap({
            "creator": [
                {"name": "Alice"},
                {"name": "Bob"},
            ],
        })
        assert bootstrap["creator"] == "Alice, Bob"

    def test_extract_bootstrap_prefixed_keys(self):
        """sc:-prefixed keys should be picked up when @context omits the prefix mapping."""
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap({
            "sc:name": "PrefixedName",
            "sc:description": "Prefixed description",
        })
        assert bootstrap["name"] == "PrefixedName"
        assert bootstrap["description"] == "Prefixed description"

    def test_extract_bootstrap_value_objects(self):
        """JSON-LD `{"@value": ...}` shape unwraps to the underlying string."""
        from numinal.detection.croissant import extract_bootstrap
        bootstrap = extract_bootstrap({
            "name": {"@value": "WrappedName"},
            "license": {"@id": "https://example.com/license"},
        })
        assert bootstrap["name"] == "WrappedName"
        assert bootstrap["license"] == "https://example.com/license"

    def test_extract_bootstrap_empty_doc(self):
        from numinal.detection.croissant import extract_bootstrap
        assert extract_bootstrap({}) == {}

    def test_init_from_croissant_uses_bootstrap_fields(self, tmp_dataset, croissant_doc):
        path = tmp_dataset / "croissant.json"
        path.write_text(json.dumps(croissant_doc), encoding="utf-8")
        output = run_init(
            str(tmp_dataset), non_interactive=True, tier=1,
            from_croissant=str(path),
        )
        card = yaml.safe_load(output.read_text())
        assert card["name"] == "uk-health-corpus"
        assert card["version"] == "2.1.0"
        assert card["creator"] == "NHS England"
        assert card["license"].startswith("https://creativecommons.org")

    def test_init_from_croissant_preserves_record_set_at_t1(self, tmp_dataset, croissant_doc):
        """A Croissant-supplied recordSet survives even at T1."""
        path = tmp_dataset / "croissant.json"
        path.write_text(json.dumps(croissant_doc), encoding="utf-8")
        output = run_init(
            str(tmp_dataset), non_interactive=True, tier=1,
            from_croissant=str(path),
        )
        card = yaml.safe_load(output.read_text())
        assert card.get("recordSet")
        assert card["recordSet"][0]["name"] == "patients"

    def test_init_from_croissant_uses_croissant_distribution(self, tmp_dataset, croissant_doc):
        path = tmp_dataset / "croissant.json"
        path.write_text(json.dumps(croissant_doc), encoding="utf-8")
        output = run_init(
            str(tmp_dataset), non_interactive=True, tier=1,
            from_croissant=str(path),
        )
        card = yaml.safe_load(output.read_text())
        names = {d.get("name") for d in card["distribution"]}
        assert "records.csv" in names

    def test_init_from_croissant_keeps_file_manifest(self, tmp_dataset, croissant_doc):
        """File manifest still comes from the directory scan, not the Croissant."""
        path = tmp_dataset / "croissant.json"
        path.write_text(json.dumps(croissant_doc), encoding="utf-8")
        output = run_init(
            str(tmp_dataset), non_interactive=True, tier=1,
            from_croissant=str(path),
        )
        card = yaml.safe_load(output.read_text())
        manifest_paths = {f["path"] for f in card["_fileManifest"]}
        assert "data.csv" in manifest_paths


# ---------------------------------------------------------------------------
# Compliance command tests
# ---------------------------------------------------------------------------

class TestCompliance:
    """Test the EU AI Act Article 10 compliance checker."""

    def test_full_card_passes(self, full_t3_card):
        from numinal.commands.compliance import check_compliance
        path, _ = full_t3_card
        result = check_compliance(path)
        assert result.parse_error is None
        assert result.all_passed

    def test_minimal_card_fails(self, minimal_t1_card):
        from numinal.commands.compliance import check_compliance
        path, _ = minimal_t1_card
        result = check_compliance(path)
        assert not result.all_passed
        # Should fail most Art 10 requirements since no RAI fields
        failed = [c for c in result.checks if not c.passed and not c.skipped]
        assert len(failed) >= 5

    def test_13_requirements_defined(self):
        from numinal.commands.compliance import ART_10_REQUIREMENTS
        assert len(ART_10_REQUIREMENTS) == 13

    def test_conditional_skipping(self, tmp_path):
        """10(5) skipped when no special category data; 10(2)(b)+ skipped when no personal data."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "dataOrigin": {"personalDataPresent": False},
                "biasExamination": {"healthSafetyBiases": []},
            },
        }
        path = tmp_path / "no-pd.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        skipped_clauses = {c.clause for c in result.checks if c.skipped}
        assert "10(2)(b)+" in skipped_clauses
        assert "10(5)" in skipped_clauses

    def test_bias_mitigation_check(self, tmp_path):
        """10(2)(g) passes when bias entries have detectionMethod and mitigationStatus."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "biasExamination": {
                    "healthSafetyBiases": [
                        {
                            "bias": "test bias",
                            "detectionMethod": "statistical analysis",
                            "mitigationStatus": "mitigated",
                            "mitigationMeasure": "resampling",
                        }
                    ],
                    "discriminationBiases": [],
                },
            },
        }
        path = tmp_path / "mitigation.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        g_check = next(c for c in result.checks if c.clause == "10(2)(g)")
        assert g_check.passed

    def test_bias_mitigation_fails_without_fields(self, tmp_path):
        """10(2)(g) fails when bias entries lack mitigation fields."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "biasExamination": {
                    "healthSafetyBiases": [
                        {"bias": "test bias"}  # No detectionMethod or mitigationStatus
                    ],
                },
            },
        }
        path = tmp_path / "no-mitigation.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        g_check = next(c for c in result.checks if c.clause == "10(2)(g)")
        assert not g_check.passed

    def test_dataset_role_in_policy(self, tmp_path):
        """10(6) passes when intendedDatasetRole is inside an access policy."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "accessPolicies": [
                    {"policyId": "p1", "intendedDatasetRole": ["training"]},
                ],
            },
        }
        path = tmp_path / "role-in-policy.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        role_check = next(c for c in result.checks if c.clause == "10(6)")
        assert role_check.passed

    def test_dataset_role_at_gov_level(self, tmp_path):
        """10(6) passes when gov.intendedDatasetRole is set without access policies."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "intendedDatasetRole": ["training"],
            },
        }
        path = tmp_path / "role-at-gov.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        role_check = next(c for c in result.checks if c.clause == "10(6)")
        assert role_check.passed

    def test_dataset_role_missing(self, tmp_path):
        """10(6) fails when intendedDatasetRole is set neither on gov nor in any policy."""
        from numinal.commands.compliance import check_compliance
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
        }
        path = tmp_path / "role-missing.yaml"
        path.write_text(yaml.dump(card))
        result = check_compliance(path)
        role_check = next(c for c in result.checks if c.clause == "10(6)")
        assert not role_check.passed


# ---------------------------------------------------------------------------
# Render command tests
# ---------------------------------------------------------------------------

class TestRender:
    """Test the markdown rendering command."""

    def test_render_minimal(self, minimal_t1_card):
        from numinal.commands.render import render_markdown
        path, _ = minimal_t1_card
        md, error = render_markdown(path)
        assert error is None
        assert md is not None
        assert "# test-dataset" in md
        assert "MIT" in md

    def test_render_full(self, full_t3_card):
        from numinal.commands.render import render_markdown
        path, _ = full_t3_card
        md, error = render_markdown(path)
        assert error is None
        assert "## Governance" in md
        assert "## Access Policies" in md
        assert "test-policy" in md

    def test_render_contains_art10_refs(self):
        """Rendered markdown includes Article 10 clause references."""
        from numinal.commands.render import render_markdown
        example = Path(__file__).parent.parent / "examples" / "uk-health-ai-corpus.yaml"
        if not example.exists():
            pytest.skip("Example file not available")
        md, error = render_markdown(example)
        assert error is None
        assert "Art. 10(2)(a)" in md
        assert "Art. 10(2)(b)" in md
        assert "Art. 10(2)(f)" in md
        assert "Art. 10(3)" in md

    def test_render_file_output(self, minimal_t1_card, tmp_path):
        from numinal.commands.render import render_markdown
        path, _ = minimal_t1_card
        md, _ = render_markdown(path)
        out = tmp_path / "output.md"
        out.write_text(md)
        assert out.exists()
        assert "# test-dataset" in out.read_text()

    def test_render_skips_todos(self, tmp_path):
        """TODO markers should not appear in rendered output."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "designChoices": {
                    "designObjective": "TODO: fill this in",
                    "populationScope": "Actual population description",
                },
            },
        }
        path = tmp_path / "todos.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "TODO:" not in md
        assert "Actual population description" in md

    def test_render_includes_measurement_assumptions(self, tmp_path):
        """rai.measurementAssumptions renders an Art. 10(2)(d) section."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "measurementAssumptions": [
                    {
                        "field": "toa",
                        "assumption": "Perfect timing of arrival",
                        "knownLimitations": "Real-world ToA jitter not modelled",
                    },
                ],
            },
        }
        path = tmp_path / "ma.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Art. 10(2)(d)" in md
        assert "Measurement Assumptions" in md
        assert "`toa`" in md
        assert "Perfect timing of arrival" in md

    def test_render_includes_suitability(self, tmp_path):
        """rai.suitabilityAssessment renders an Art. 10(2)(e) section."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "suitabilityAssessment": {
                    "quantityAssessment": "450k records is sufficient",
                    "availabilityAssessment": "Mental-health trust data unavailable",
                    "suitabilityAssessment": "Suitable for general adult pathways only",
                    "additionalDataNeeded": "Mental-health and primary-care records",
                },
            },
        }
        path = tmp_path / "sa.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Art. 10(2)(e)" in md
        assert "Suitability Assessment" in md
        assert "**Quantity:**" in md
        assert "450k records" in md
        assert "Mental-health and primary-care records" in md

    def test_render_skips_empty_sections(self, tmp_path):
        """Empty measurementAssumptions/suitabilityAssessment should not render headers."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {"governanceModel": "open", "governanceVersion": "1.0.0"},
            "rai": {
                "measurementAssumptions": [],
                "suitabilityAssessment": {
                    "quantityAssessment": "",
                    "availabilityAssessment": "",
                    "suitabilityAssessment": "TODO: fill this in",
                    "additionalDataNeeded": "",
                },
                "contextualCharacteristics": {
                    "languageCharacteristics": "",
                    "culturalConsiderations": "",
                    "temporalCoverage": "",
                    "functionalContext": "",
                },
            },
        }
        path = tmp_path / "empty.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Measurement Assumptions" not in md
        assert "Suitability Assessment" not in md
        assert "Contextual Characteristics" not in md
        assert "Art. 10(2)(d)" not in md
        assert "Art. 10(2)(e)" not in md
        assert "TODO" not in md

    def test_render_includes_special_category_handling(self, tmp_path):
        """gov.publisherSpecialCategoryHandling renders an Art. 10(5) section with conditions."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "controlled", "governanceVersion": "1.0.0",
                "publisherSpecialCategoryHandling": {
                    "specialCategoryDataPresent": True,
                    "categories": ["health-data"],
                    "processingPurpose": "bias-detection-correction",
                    "processingJustification": "Required to detect outcome disparities",
                    "conditions": {
                        "a_alternativeDataInsufficient": {
                            "met": True, "evidence": "Synthetic data tested and insufficient",
                        },
                        "d_noThirdPartyTransfer": {"met": False, "enforcement": ""},
                    },
                },
            },
            "rai": {"designChoices": {"designObjective": "ok"}},
        }
        path = tmp_path / "scd.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Art. 10(5)" in md
        assert "Special Category Data" in md
        assert "health-data" in md
        assert "bias-detection-correction" in md
        assert "✓" in md
        assert "✗" in md

    def test_render_special_category_skipped_when_absent(self, tmp_path):
        """specialCategoryDataPresent: false should suppress the section."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "publisherSpecialCategoryHandling": {
                    "specialCategoryDataPresent": False,
                    "categories": [],
                },
            },
            "rai": {"designChoices": {"designObjective": "ok"}},
        }
        path = tmp_path / "no-scd.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Art. 10(5)" not in md
        assert "Special Category Data" not in md

    def test_render_includes_funding_and_dpo(self, tmp_path):
        """gov.fundingSource and gov.dataProtectionOfficer render in the Governance block."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "dataController": {"name": "Test Org", "contactEmail": "dc@example.org"},
                "dataProtectionOfficer": {"name": "Dana Officer", "contactEmail": "dpo@example.org"},
                "fundingSource": {
                    "funderName": "UKRI",
                    "programmeName": "AI for Public Good",
                    "fundingTrack": "non-commercial",
                },
                "impactReporting": {
                    "metricsRequired": ["unique-consumer-organisations", "total-api-calls"],
                    "reportingFrequency": "quarterly",
                },
            },
        }
        path = tmp_path / "funding.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "Data protection officer" in md
        assert "Dana Officer" in md
        assert "dpo@example.org" in md
        assert "**Funder:** UKRI" in md
        assert "AI for Public Good" in md
        assert "Impact reporting" in md
        assert "quarterly" in md
        assert "unique-consumer-organisations" in md

    def test_render_includes_derived_from(self, tmp_path):
        """gov.derivedFrom renders a top-level provenance section."""
        from numinal.commands.render import render_markdown
        card = {
            "name": "test", "description": "test", "version": "1.0.0",
            "license": "MIT", "creator": "test",
            "distribution": [{"name": "d"}],
            "gov": {
                "governanceModel": "open", "governanceVersion": "1.0.0",
                "derivedFrom": [
                    {
                        "sourceDataset": {"name": "source-dataset", "version": "1.0"},
                        "accessPolicyUsed": "policy-id",
                        "accessDate": "2026-01-01",
                        "derivationMethod": "Filtered to UK records only",
                        "inheritedConstraints": [
                            {
                                "constraint": "no-redistribution",
                                "inherited": True,
                                "howAddressed": "Same prohibition carried into derived policy",
                            },
                        ],
                    },
                ],
            },
        }
        path = tmp_path / "derived.yaml"
        path.write_text(yaml.dump(card))
        md, _ = render_markdown(path)
        assert "## Derived From" in md
        assert "**source-dataset** (v1.0)" in md
        assert "accessed under policy-id" in md
        assert "on 2026-01-01" in md
        assert "Filtered to UK records only" in md
        assert "no-redistribution" in md
