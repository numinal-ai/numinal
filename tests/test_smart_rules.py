"""Tests for smart cross-field validation rules.

Each rule has at least two tests: a positive case (rule fires) and a negative
case (rule does not fire). Helpers build a baseline card and let each test
mutate just the parts relevant to its rule, so unrelated rules stay quiet
and assertions can pinpoint the rule under test.
"""

from __future__ import annotations

import copy
import datetime
from typing import Any

import pytest

from numinal.commands.smart_rules import SmartDiagnostic, run_all_rules


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline() -> dict[str, Any]:
    """Build a comprehensive, internally consistent baseline card.

    The baseline is designed to fire NO smart-rule diagnostics. Tests mutate
    a deep copy and then assert their target rule fires (or not) without
    interference from siblings.
    """
    return {
        "name": "baseline-dataset",
        "description": "A baseline test dataset",
        "version": "1.0.0",
        "license": "OGL-UK-3.0",
        "creator": "Baseline Org",
        "datePublished": "2026-01-01",
        "distribution": [
            {"name": "csv-files", "contentType": "text/csv",
             "fileCount": 1, "totalSizeBytes": 100},
        ],
        "recordSet": [
            {
                "name": "records",
                "source": "data.csv",
                "fields": [
                    {"name": "record_id", "dataType": "string"},
                    {"name": "value", "dataType": "integer"},
                ],
            },
        ],
        "_fileManifest": [
            {"path": "data.csv", "sizeBytes": 100, "sha256": "x" * 64},
        ],
        "gov": {
            "governanceModel": "controlled",
            "governanceVersion": "1.0.0",
            "dataController": {
                "name": "Baseline Org",
                "contactEmail": "dpo@baseline.example",
                "url": "",
            },
            "dataClassification": "official",
            "legalBasis": "public-task",
            "regulatoryAlignment": ["eu-ai-act-art-10"],
            "lastGovernanceReview": "2026-01-01",
            "licenseGovernanceRelationship": {
                "relationship": "governance-supersedes",
                "explanation": "x",
            },
            "publisherSpecialCategoryHandling": {
                "specialCategoryDataPresent": False,
                "categories": [],
            },
            "fundingSource": {
                "funderName": "",
                "fundingTrack": "",
            },
            "impactReporting": {
                "metricsRequired": [],
                "reportingFrequency": "",
            },
            "accessPolicies": [
                {
                    "policyId": "baseline-policy",
                    "policyVersion": "1.0.0",
                    "eligibility": {"consumerType": ["uk-university"]},
                    "permittedPurposes": ["model-training"],
                    "prohibitedPurposes": [],
                    "accessScope": {"scopeType": "full", "accessMethod": "bulk-download"},
                    "retention": {
                        "maxRetentionDays": 365,
                        "retentionType": "fixed",
                        "deletionMethod": "cryptographic-erasure",
                    },
                    "redistribution": {
                        "redistributionPermitted": False,
                        "derivativeWorksPermitted": False,
                        "derivativeWorkConditions": "",
                    },
                    "auditRequirements": {
                        "auditRightGranted": False,
                    },
                    "prerequisites": [{"prerequisiteType": "agreement"}],
                    "intendedDatasetRole": ["training"],
                    "effectiveFrom": "2026-01-01",
                    "expiresAt": None,
                    "highRiskDomainAdvisory": "",
                },
            ],
        },
        "rai": {
            "designChoices": {"designObjective": "x"},
            "dataCollection": "x",
            "dataOrigin": {
                "sources": [{"name": "src", "extractionDate": "2025-06-01"}],
                "originalCollectionPurpose": "Direct service delivery",
                "consentBasis": "public-task",
                "personalDataPresent": False,
                "personalDataCategories": [],
            },
            "dataPreparation": {
                "annotation": {"performed": False, "description": ""},
                "labelling": {"performed": False, "description": ""},
                "cleaning": {"performed": False, "description": ""},
                "updating": {"performed": False, "description": ""},
                "enrichment": {"performed": False, "description": ""},
                "aggregation": {"performed": False, "description": ""},
            },
            "measurementAssumptions": [
                {"field": "record_id", "assumption": "unique"},
                {"field": "value", "assumption": "non-negative"},
            ],
            "suitabilityAssessment": {"quantityAssessment": "ok"},
            "biasExamination": {
                "healthSafetyBiases": [],
                "fundamentalRightsBiases": [],
                "discriminationBiases": [],
            },
            "complianceGaps": [],
            "dataQualityAssessment": {
                "relevance": {"assessment": "ok"},
                "representativeness": {"assessment": "ok", "knownGaps": ""},
                "completeness": {"missingDataByField": {}},
            },
            "geographicContext": {"dataOriginCountries": ["GB"]},
        },
    }


def _ids(diagnostics: list[SmartDiagnostic]) -> list[str]:
    return [d.rule_id for d in diagnostics]


def _has(diagnostics: list[SmartDiagnostic], rule_id: str) -> bool:
    return rule_id in _ids(diagnostics)


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_empty_card(self):
        # No KeyError, no exceptions
        diags = run_all_rules({})
        assert isinstance(diags, list)

    def test_minimal_card(self):
        diags = run_all_rules({"name": "x", "version": "1.0.0"})
        assert isinstance(diags, list)

    def test_baseline_silent(self):
        """Baseline card should fire none of the tested rules."""
        diags = run_all_rules(_baseline())
        # Baseline should be clean — assert no errors and no warnings
        assert not [d for d in diags if d.severity == "error"], _ids(diags)
        assert not [d for d in diags if d.severity == "warning"], _ids(diags)

    def test_non_dict_input(self):
        assert run_all_rules("not a dict") == []  # type: ignore[arg-type]
        assert run_all_rules(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Category 1: Dataset-Aware
# ---------------------------------------------------------------------------


class TestDatasetAware:
    def test_ds001_demographic_column_without_bias(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "ethnicity", "dataType": "string"})
        diags = run_all_rules(card)
        assert _has(diags, "DS-001")

    def test_ds001_does_not_fire_when_documented(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "ethnicity", "dataType": "string"})
        card["rai"]["biasExamination"]["discriminationBiases"] = [{
            "bias": "ethnic skew",
            "protectedCharacteristic": "ethnicity",
            "legalBasis": "Equality Act 2010",
        }]
        diags = run_all_rules(card)
        assert not _has(diags, "DS-001")

    def test_ds002_pii_column_without_pdp(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "email", "dataType": "string"})
        diags = run_all_rules(card)
        assert _has(diags, "DS-002")

    def test_ds002_silent_when_pdp_true(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "email", "dataType": "string"})
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["contact-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "DS-002")

    def test_ds003_health_column_without_special_category(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "diagnosis_code", "dataType": "string"})
        diags = run_all_rules(card)
        assert _has(diags, "DS-003")

    def test_ds003_silent_when_special_category_true(self):
        card = _baseline()
        card["recordSet"][0]["fields"].append({"name": "diagnosis_code", "dataType": "string"})
        card["gov"]["publisherSpecialCategoryHandling"]["specialCategoryDataPresent"] = True
        card["gov"]["publisherSpecialCategoryHandling"]["categories"] = ["health-data"]
        # Avoid SC-002 — also flip personalDataPresent
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "DS-003")

    def test_ds004_high_null_rate_undocumented(self):
        card = _baseline()
        card["recordSet"][0]["fields"][1]["nullRate"] = 0.10
        diags = run_all_rules(card)
        assert _has(diags, "DS-004")

    def test_ds004_silent_when_documented(self):
        card = _baseline()
        card["recordSet"][0]["fields"][1]["nullRate"] = 0.10
        card["rai"]["dataQualityAssessment"]["completeness"]["missingDataByField"] = {
            "value": 10
        }
        diags = run_all_rules(card)
        assert not _has(diags, "DS-004")

    def test_ds004_silent_below_threshold(self):
        card = _baseline()
        card["recordSet"][0]["fields"][1]["nullRate"] = 0.04
        diags = run_all_rules(card)
        assert not _has(diags, "DS-004")

    def test_ds005_manifest_distribution_mismatch(self):
        card = _baseline()
        # Manifest has 1 file but distribution claims 100 files
        card["distribution"][0]["fileCount"] = 100
        diags = run_all_rules(card)
        assert _has(diags, "DS-005")

    def test_ds005_silent_when_aligned(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DS-005")

    def test_ds006_low_measurement_coverage(self):
        card = _baseline()
        # Many fields, but only one measurement assumption -> coverage well under 25%
        for i in range(10):
            card["recordSet"][0]["fields"].append({"name": f"col{i}", "dataType": "string"})
        card["rai"]["measurementAssumptions"] = [
            {"field": "record_id", "assumption": "unique"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "DS-006")

    def test_ds006_silent_with_full_coverage(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DS-006")

    def test_ds007_content_type_mismatch(self):
        card = _baseline()
        # Manifest has .json but distribution only declares text/csv
        card["_fileManifest"].append({
            "path": "data.json", "sizeBytes": 100, "sha256": "y" * 64,
        })
        diags = run_all_rules(card)
        assert _has(diags, "DS-007")

    def test_ds007_silent_when_aligned(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DS-007")

    def test_ds008_aggregation_with_one_data_file(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["aggregation"]["performed"] = True
        # README and LICENSE should not count as data files
        card["_fileManifest"].extend([
            {"path": "README.md", "sizeBytes": 10, "sha256": "z" * 64},
            {"path": "LICENSE", "sizeBytes": 10, "sha256": "z" * 64},
        ])
        diags = run_all_rules(card)
        assert _has(diags, "DS-008")

    def test_ds008_silent_with_multiple_data_files(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["aggregation"]["performed"] = True
        card["rai"]["dataPreparation"]["aggregation"]["sourceCount"] = 2
        card["_fileManifest"].append(
            {"path": "data2.csv", "sizeBytes": 100, "sha256": "y" * 64},
        )
        # Update distribution so DS-005 doesn't fire
        card["distribution"][0]["fileCount"] = 2
        card["distribution"][0]["totalSizeBytes"] = 200
        diags = run_all_rules(card)
        assert not _has(diags, "DS-008")


# ---------------------------------------------------------------------------
# Category 2: Personal Data
# ---------------------------------------------------------------------------


class TestPersonalData:
    def test_pd001_pdp_true_no_categories(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        diags = run_all_rules(card)
        assert _has(diags, "PD-001")

    def test_pd001_silent_with_categories(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "PD-001")

    def test_pd002_pdp_true_no_legal_basis(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        card["gov"]["legalBasis"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "PD-002")

    def test_pd002_silent_with_legal_basis(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        # legalBasis is set in baseline
        diags = run_all_rules(card)
        assert not _has(diags, "PD-002")

    def test_pd003_categories_listed_but_pdp_false(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = False
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert _has(diags, "PD-003")

    def test_pd003_silent_when_consistent(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "PD-003")

    def test_pd004_pdp_true_no_consent_basis(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        card["rai"]["dataOrigin"]["consentBasis"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "PD-004")

    def test_pd004_silent_with_consent_basis(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        diags = run_all_rules(card)
        assert not _has(diags, "PD-004")

    def test_pd005_pdp_true_no_purpose(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        card["rai"]["dataOrigin"]["originalCollectionPurpose"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "PD-005")

    def test_pd005_fires_for_todo_marker(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        card["rai"]["dataOrigin"]["originalCollectionPurpose"] = "TODO: fill in"
        diags = run_all_rules(card)
        assert _has(diags, "PD-005")

    def test_pd005_silent_when_documented(self):
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["x"]
        diags = run_all_rules(card)
        assert not _has(diags, "PD-005")


# ---------------------------------------------------------------------------
# Category 3: Special Category Data
# ---------------------------------------------------------------------------


class TestSpecialCategory:
    def test_sc001_present_no_categories(self):
        card = _baseline()
        card["gov"]["publisherSpecialCategoryHandling"]["specialCategoryDataPresent"] = True
        # Trigger SC-002 separately by also fixing personalDataPresent
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert _has(diags, "SC-001")

    def test_sc001_silent_with_categories(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = True
        sch["categories"] = ["health-data"]
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "SC-001")

    def test_sc002_special_without_personal(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = True
        sch["categories"] = ["health-data"]
        # personalDataPresent stays False -> SC-002 fires
        diags = run_all_rules(card)
        assert _has(diags, "SC-002")

    def test_sc002_silent_when_pdp_true(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = True
        sch["categories"] = ["health-data"]
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "SC-002")

    def test_sc003_condition_not_addressed(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = True
        sch["categories"] = ["health-data"]
        sch["conditions"] = {
            "a_alternativeDataInsufficient": {"met": False, "evidence": ""},
        }
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert _has(diags, "SC-003")

    def test_sc003_silent_when_explained(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = True
        sch["categories"] = ["health-data"]
        sch["conditions"] = {
            "a_alternativeDataInsufficient": {"met": True, "evidence": "tested"},
            "b_technicalReuseLimitations": {"met": True, "measures": "TRE"},
            "c_accessControlAndConfidentiality": {"met": True, "measures": "RBAC"},
            "d_noThirdPartyTransfer": {"met": True, "enforcement": "DUA"},
            "e_deletionOnCompletion": {"met": True, "mechanism": "auto-delete"},
            "f_processingRecords": {"met": True, "ropaReference": "ROPA-1"},
        }
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        card["rai"]["dataOrigin"]["personalDataCategories"] = ["health-data"]
        diags = run_all_rules(card)
        assert not _has(diags, "SC-003")

    def test_sc004_categories_but_present_false(self):
        card = _baseline()
        sch = card["gov"]["publisherSpecialCategoryHandling"]
        sch["specialCategoryDataPresent"] = False
        sch["categories"] = ["health-data"]
        diags = run_all_rules(card)
        assert _has(diags, "SC-004")

    def test_sc004_silent_when_consistent(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "SC-004")


# ---------------------------------------------------------------------------
# Category 4: Bias Examination
# ---------------------------------------------------------------------------


class TestBiasExamination:
    def test_bx001_all_not_assessed(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "a", "mitigationStatus": "not-assessed"},
            {"bias": "b", "mitigationStatus": "not-assessed"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "BX-001")

    def test_bx001_silent_when_some_mitigated(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "a", "mitigationStatus": "mitigated"},
            {"bias": "b", "mitigationStatus": "not-assessed"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "BX-001")

    def test_bx002_high_severity_not_mitigated(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "x", "severity": "high", "mitigationStatus": "documented"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "BX-002")

    def test_bx002_silent_when_high_mitigated(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "x", "severity": "high", "mitigationStatus": "mitigated"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "BX-002")

    def test_bx003_discrimination_missing_protected(self):
        card = _baseline()
        card["rai"]["biasExamination"]["discriminationBiases"] = [
            {"bias": "x", "legalBasis": "Equality Act 2010"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "BX-003")

    def test_bx003_silent_when_protected_set(self):
        card = _baseline()
        card["rai"]["biasExamination"]["discriminationBiases"] = [
            {"bias": "x", "protectedCharacteristic": "age",
             "legalBasis": "Equality Act 2010", "mitigationStatus": "mitigated"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "BX-003")

    def test_bx004_discrimination_missing_legal_basis(self):
        card = _baseline()
        card["rai"]["biasExamination"]["discriminationBiases"] = [
            {"bias": "x", "protectedCharacteristic": "age",
             "mitigationStatus": "mitigated"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "BX-004")

    def test_bx004_silent_with_legal_basis(self):
        card = _baseline()
        card["rai"]["biasExamination"]["discriminationBiases"] = [
            {"bias": "x", "protectedCharacteristic": "age",
             "legalBasis": "Equality Act 2010", "mitigationStatus": "mitigated"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "BX-004")

    def test_bx005_detection_without_status(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "x", "detectionMethod": "statistical analysis"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "BX-005")

    def test_bx005_silent_when_status_set(self):
        card = _baseline()
        card["rai"]["biasExamination"]["healthSafetyBiases"] = [
            {"bias": "x", "detectionMethod": "stat", "mitigationStatus": "mitigated"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "BX-005")


# ---------------------------------------------------------------------------
# Category 5: Access Policy
# ---------------------------------------------------------------------------


class TestAccessPolicy:
    def test_ap001_no_permitted(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["permittedPurposes"] = []
        diags = run_all_rules(card)
        assert _has(diags, "AP-001")

    def test_ap001_silent_with_permitted(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-001")

    def test_ap002_purpose_in_both(self):
        card = _baseline()
        p = card["gov"]["accessPolicies"][0]
        p["prohibitedPurposes"] = ["model-training"]
        diags = run_all_rules(card)
        assert _has(diags, "AP-002")

    def test_ap002_silent_disjoint(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-002")

    def test_ap003_no_effective_from(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["effectiveFrom"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "AP-003")

    def test_ap003_silent_with_date(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-003")

    def test_ap004_effective_after_expires(self):
        card = _baseline()
        p = card["gov"]["accessPolicies"][0]
        p["effectiveFrom"] = "2027-01-01"
        p["expiresAt"] = "2026-06-01"
        diags = run_all_rules(card)
        assert _has(diags, "AP-004")

    def test_ap004_silent_when_consistent(self):
        card = _baseline()
        p = card["gov"]["accessPolicies"][0]
        p["effectiveFrom"] = "2026-01-01"
        p["expiresAt"] = "2030-01-01"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-004")

    def test_ap005_expired(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["expiresAt"] = "2020-01-01"
        diags = run_all_rules(card)
        assert _has(diags, "AP-005")

    def test_ap005_silent_when_future(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["expiresAt"] = "2099-01-01"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-005")

    def test_ap006_zero_retention(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["retention"]["maxRetentionDays"] = 0
        diags = run_all_rules(card)
        assert _has(diags, "AP-006")

    def test_ap006_silent_with_positive(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-006")

    def test_ap007_long_retention(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["retention"]["maxRetentionDays"] = 5000
        diags = run_all_rules(card)
        assert _has(diags, "AP-007")

    def test_ap007_silent_under_threshold(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-007")

    def test_ap008_retention_no_deletion_method(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["retention"]["deletionMethod"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "AP-008")

    def test_ap008_silent_with_method(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-008")

    def test_ap009_derivative_no_conditions(self):
        card = _baseline()
        r = card["gov"]["accessPolicies"][0]["redistribution"]
        r["derivativeWorksPermitted"] = True
        r["derivativeWorkConditions"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "AP-009")

    def test_ap009_silent_with_conditions(self):
        card = _baseline()
        r = card["gov"]["accessPolicies"][0]["redistribution"]
        r["derivativeWorksPermitted"] = True
        r["derivativeWorkConditions"] = "Must attribute"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-009")

    def test_ap010_audit_no_frequency(self):
        card = _baseline()
        a = card["gov"]["accessPolicies"][0]["auditRequirements"]
        a["auditRightGranted"] = True
        a["auditScope"] = "full"
        diags = run_all_rules(card)
        assert _has(diags, "AP-010")

    def test_ap010_silent_with_frequency(self):
        card = _baseline()
        a = card["gov"]["accessPolicies"][0]["auditRequirements"]
        a["auditRightGranted"] = True
        a["auditFrequency"] = "annual"
        a["auditScope"] = "full"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-010")

    def test_ap011_audit_no_scope(self):
        card = _baseline()
        a = card["gov"]["accessPolicies"][0]["auditRequirements"]
        a["auditRightGranted"] = True
        a["auditFrequency"] = "annual"
        diags = run_all_rules(card)
        assert _has(diags, "AP-011")

    def test_ap011_silent_with_scope(self):
        card = _baseline()
        a = card["gov"]["accessPolicies"][0]["auditRequirements"]
        a["auditRightGranted"] = True
        a["auditFrequency"] = "annual"
        a["auditScope"] = "operations"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-011")

    def test_ap012_partial_no_recordsets(self):
        card = _baseline()
        s = card["gov"]["accessPolicies"][0]["accessScope"]
        s["scopeType"] = "partial"
        s["includedRecordSets"] = []
        diags = run_all_rules(card)
        assert _has(diags, "AP-012")

    def test_ap012_silent_with_recordsets(self):
        card = _baseline()
        s = card["gov"]["accessPolicies"][0]["accessScope"]
        s["scopeType"] = "partial"
        s["includedRecordSets"] = ["records"]
        diags = run_all_rules(card)
        assert not _has(diags, "AP-012")

    def test_ap013_sample_no_limit(self):
        card = _baseline()
        s = card["gov"]["accessPolicies"][0]["accessScope"]
        s["scopeType"] = "sample"
        s["sampleLimit"] = None
        diags = run_all_rules(card)
        assert _has(diags, "AP-013")

    def test_ap013_silent_with_limit(self):
        card = _baseline()
        s = card["gov"]["accessPolicies"][0]["accessScope"]
        s["scopeType"] = "sample"
        s["sampleLimit"] = 1000
        diags = run_all_rules(card)
        assert not _has(diags, "AP-013")

    def test_ap014_no_eligibility(self):
        card = _baseline()
        e = card["gov"]["accessPolicies"][0]["eligibility"]
        e["consumerType"] = []
        diags = run_all_rules(card)
        assert _has(diags, "AP-014")

    def test_ap014_silent_with_eligibility(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-014")

    def test_ap015_duplicate_ids(self):
        card = _baseline()
        # Add a second policy with the same ID
        first = card["gov"]["accessPolicies"][0]
        card["gov"]["accessPolicies"].append(copy.deepcopy(first))
        diags = run_all_rules(card)
        assert _has(diags, "AP-015")

    def test_ap015_silent_when_unique(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "AP-015")

    def test_ap016_high_risk_purpose_no_advisory(self):
        card = _baseline()
        p = card["gov"]["accessPolicies"][0]
        p["permittedPurposes"] = ["clinical-decision-support"]
        p["highRiskDomainAdvisory"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "AP-016")

    def test_ap016_silent_with_advisory(self):
        card = _baseline()
        p = card["gov"]["accessPolicies"][0]
        p["permittedPurposes"] = ["clinical-decision-support"]
        p["highRiskDomainAdvisory"] = "Advisory text here"
        diags = run_all_rules(card)
        assert not _has(diags, "AP-016")


# ---------------------------------------------------------------------------
# Category 6: Compliance Gaps
# ---------------------------------------------------------------------------


class TestComplianceGaps:
    def test_cg001_past_remediation(self):
        card = _baseline()
        card["rai"]["complianceGaps"] = [
            {"gap": "x", "severity": "low", "remediationTimeline": "2020-01-01",
             "remediationPlan": "plan"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "CG-001")

    def test_cg001_silent_for_future_date(self):
        card = _baseline()
        card["rai"]["complianceGaps"] = [
            {"gap": "x", "severity": "low", "remediationTimeline": "2099-01-01",
             "remediationPlan": "plan"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "CG-001")

    def test_cg002_high_severity_no_plan(self):
        card = _baseline()
        card["rai"]["complianceGaps"] = [
            {"gap": "big issue", "severity": "high"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "CG-002")

    def test_cg002_silent_with_plan(self):
        card = _baseline()
        card["rai"]["complianceGaps"] = [
            {"gap": "x", "severity": "high", "remediationPlan": "plan"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "CG-002")

    def test_cg003_repr_gaps_not_in_compliance(self):
        card = _baseline()
        card["rai"]["dataQualityAssessment"]["representativeness"]["knownGaps"] = (
            "Mental health trusts not included"
        )
        card["rai"]["complianceGaps"] = [
            {"gap": "Other unrelated thing"},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "CG-003")

    def test_cg003_silent_when_overlapping(self):
        card = _baseline()
        card["rai"]["dataQualityAssessment"]["representativeness"]["knownGaps"] = (
            "Mental health trusts not included"
        )
        card["rai"]["complianceGaps"] = [
            {"gap": "Mental health trust data not included"},
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "CG-003")


# ---------------------------------------------------------------------------
# Category 7: Temporal
# ---------------------------------------------------------------------------


class TestTemporal:
    def test_dt001_future_published(self):
        card = _baseline()
        card["datePublished"] = "2099-01-01"
        diags = run_all_rules(card)
        assert _has(diags, "DT-001")

    def test_dt001_silent_for_past(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DT-001")

    def test_dt002_old_review(self):
        card = _baseline()
        # A date >365 days before today (today=2026-05-04 in test context
        # but always relative to datetime.date.today() at runtime)
        old = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
        card["gov"]["lastGovernanceReview"] = old
        diags = run_all_rules(card)
        assert _has(diags, "DT-002")

    def test_dt002_silent_for_recent_review(self):
        card = _baseline()
        recent = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        card["gov"]["lastGovernanceReview"] = recent
        diags = run_all_rules(card)
        assert not _has(diags, "DT-002")

    def test_dt003_future_review(self):
        card = _baseline()
        future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        card["gov"]["lastGovernanceReview"] = future
        diags = run_all_rules(card)
        assert _has(diags, "DT-003")

    def test_dt003_silent_for_past_review(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DT-003")

    def test_dt004_future_extraction(self):
        card = _baseline()
        future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        card["rai"]["dataOrigin"]["sources"] = [
            {"name": "X", "extractionDate": future},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "DT-004")

    def test_dt004_silent_for_past_extraction(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DT-004")


# ---------------------------------------------------------------------------
# Category 8: Version Format
# ---------------------------------------------------------------------------


class TestVersionFormat:
    def test_vf001_non_semver(self):
        card = _baseline()
        card["version"] = "1.0"
        diags = run_all_rules(card)
        assert _has(diags, "VF-001")

    def test_vf001_silent_for_semver(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "VF-001")

    def test_vf002_non_semver_governance(self):
        card = _baseline()
        card["gov"]["governanceVersion"] = "v1"
        diags = run_all_rules(card)
        assert _has(diags, "VF-002")

    def test_vf002_silent_for_semver(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "VF-002")

    def test_vf003_non_semver_policy(self):
        card = _baseline()
        card["gov"]["accessPolicies"][0]["policyVersion"] = "1"
        diags = run_all_rules(card)
        assert _has(diags, "VF-003")

    def test_vf003_silent_for_semver(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "VF-003")


# ---------------------------------------------------------------------------
# Category 9: License-Governance Relationship
# ---------------------------------------------------------------------------


class TestLicenseGovernance:
    def test_lg001_license_only_with_policies(self):
        card = _baseline()
        card["gov"]["licenseGovernanceRelationship"]["relationship"] = "license-only"
        diags = run_all_rules(card)
        assert _has(diags, "LG-001")

    def test_lg001_silent_when_consistent(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "LG-001")

    def test_lg002_governance_supersedes_no_policies(self):
        card = _baseline()
        card["gov"]["accessPolicies"] = []
        diags = run_all_rules(card)
        assert _has(diags, "LG-002")

    def test_lg002_silent_when_consistent(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "LG-002")


# ---------------------------------------------------------------------------
# Category 10: Governance Model
# ---------------------------------------------------------------------------


class TestGovernanceModel:
    def test_gm001_secret_with_open_model(self):
        card = _baseline()
        card["gov"]["dataClassification"] = "secret"
        card["gov"]["governanceModel"] = "open"
        diags = run_all_rules(card)
        assert _has(diags, "GM-001")

    def test_gm001_silent_with_controlled(self):
        card = _baseline()
        card["gov"]["dataClassification"] = "secret"
        diags = run_all_rules(card)
        assert not _has(diags, "GM-001")

    def test_gm002_official_sensitive_open(self):
        card = _baseline()
        card["gov"]["dataClassification"] = "official-sensitive"
        card["gov"]["governanceModel"] = "open"
        diags = run_all_rules(card)
        assert _has(diags, "GM-002")

    def test_gm002_silent_with_controlled(self):
        card = _baseline()
        card["gov"]["dataClassification"] = "official-sensitive"
        diags = run_all_rules(card)
        assert not _has(diags, "GM-002")

    def test_gm003_controlled_no_controller(self):
        card = _baseline()
        card["gov"]["dataController"]["name"] = ""
        diags = run_all_rules(card)
        assert _has(diags, "GM-003")

    def test_gm003_silent_with_controller(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "GM-003")


# ---------------------------------------------------------------------------
# Category 11: Derived Datasets
# ---------------------------------------------------------------------------


class TestDerivedDataset:
    def test_dd001_derived_no_constraints(self):
        card = _baseline()
        card["gov"]["derivedFrom"] = [
            {"source": "parent-dataset", "inheritedConstraints": []},
        ]
        diags = run_all_rules(card)
        assert _has(diags, "DD-001")

    def test_dd001_silent_with_constraints_documented(self):
        card = _baseline()
        card["gov"]["derivedFrom"] = [
            {
                "source": "parent-dataset",
                "inheritedConstraints": [
                    {"constraint": "no commercial use", "inherited": False,
                     "howAddressed": "n/a"},
                ],
            },
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "DD-001")

    def test_dd002_inherited_no_how_addressed(self):
        card = _baseline()
        card["gov"]["derivedFrom"] = [
            {
                "source": "parent",
                "inheritedConstraints": [
                    {"constraint": "no commercial use", "inherited": True,
                     "howAddressed": ""},
                ],
            },
        ]
        diags = run_all_rules(card)
        assert _has(diags, "DD-002")

    def test_dd002_silent_when_addressed(self):
        card = _baseline()
        card["gov"]["derivedFrom"] = [
            {
                "source": "parent",
                "inheritedConstraints": [
                    {"constraint": "no commercial use", "inherited": True,
                     "howAddressed": "documented in licence"},
                ],
            },
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "DD-002")


# ---------------------------------------------------------------------------
# Category 12: Data Preparation
# ---------------------------------------------------------------------------


class TestDataPreparation:
    def test_dp001_annotation_zero_count(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["annotation"] = {
            "performed": True, "annotatorCount": 0,
        }
        diags = run_all_rules(card)
        assert _has(diags, "DP-001")

    def test_dp001_silent_with_count(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["annotation"] = {
            "performed": True, "annotatorCount": 1,
        }
        diags = run_all_rules(card)
        assert not _has(diags, "DP-001")

    def test_dp002_multi_annotator_no_iaa(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["annotation"] = {
            "performed": True, "annotatorCount": 5,
            "interAnnotatorAgreement": {"metric": ""},
        }
        diags = run_all_rules(card)
        assert _has(diags, "DP-002")

    def test_dp002_silent_with_iaa(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["annotation"] = {
            "performed": True, "annotatorCount": 5,
            "interAnnotatorAgreement": {"metric": "Cohen's kappa", "value": 0.9},
        }
        diags = run_all_rules(card)
        assert not _has(diags, "DP-002")

    def test_dp003_aggregation_zero_sources(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["aggregation"] = {
            "performed": True, "sourceCount": 0,
        }
        # Add another data file so DS-008 doesn't fire (we want to isolate DP-003)
        card["_fileManifest"].append(
            {"path": "data2.csv", "sizeBytes": 100, "sha256": "y" * 64},
        )
        card["distribution"][0]["fileCount"] = 2
        card["distribution"][0]["totalSizeBytes"] = 200
        diags = run_all_rules(card)
        assert _has(diags, "DP-003")

    def test_dp003_silent_with_sources(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["aggregation"] = {
            "performed": True, "sourceCount": 5,
        }
        card["_fileManifest"].append(
            {"path": "data2.csv", "sizeBytes": 100, "sha256": "y" * 64},
        )
        card["distribution"][0]["fileCount"] = 2
        card["distribution"][0]["totalSizeBytes"] = 200
        diags = run_all_rules(card)
        assert not _has(diags, "DP-003")

    def test_dp004_enrichment_no_source(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["enrichment"] = {
            "performed": True, "enrichmentSource": "",
        }
        diags = run_all_rules(card)
        assert _has(diags, "DP-004")

    def test_dp004_silent_with_source(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["enrichment"] = {
            "performed": True, "enrichmentSource": "ONS demographics",
        }
        diags = run_all_rules(card)
        assert not _has(diags, "DP-004")

    def test_dp005_cleaning_no_metrics(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["cleaning"] = {
            "performed": True,
            "recordsRemovedCount": 0,
            "recordsRemovedPercentage": 0,
        }
        diags = run_all_rules(card)
        assert _has(diags, "DP-005")

    def test_dp005_silent_with_metrics(self):
        card = _baseline()
        card["rai"]["dataPreparation"]["cleaning"] = {
            "performed": True,
            "recordsRemovedCount": 100,
            "recordsRemovedPercentage": 1.0,
        }
        diags = run_all_rules(card)
        assert not _has(diags, "DP-005")


# ---------------------------------------------------------------------------
# Category 13: Funding & Impact
# ---------------------------------------------------------------------------


class TestFundingImpact:
    def test_fi001_funder_no_reporting(self):
        card = _baseline()
        card["gov"]["fundingSource"] = {"funderName": "UKRI"}
        diags = run_all_rules(card)
        assert _has(diags, "FI-001")

    def test_fi001_silent_with_reporting(self):
        card = _baseline()
        card["gov"]["fundingSource"] = {"funderName": "UKRI"}
        card["gov"]["impactReporting"] = {
            "metricsRequired": ["downloads"],
            "reportingFrequency": "annual",
        }
        diags = run_all_rules(card)
        assert not _has(diags, "FI-001")

    def test_fi002_commercial_no_product_purpose(self):
        card = _baseline()
        card["gov"]["fundingSource"]["fundingTrack"] = "commercial"
        diags = run_all_rules(card)
        assert _has(diags, "FI-002")

    def test_fi002_silent_with_product_purpose(self):
        card = _baseline()
        card["gov"]["fundingSource"]["fundingTrack"] = "commercial"
        card["gov"]["accessPolicies"][0]["permittedPurposes"] = [
            "model-training", "product-development",
        ]
        diags = run_all_rules(card)
        assert not _has(diags, "FI-002")


# ---------------------------------------------------------------------------
# Category 14: Data Controller
# ---------------------------------------------------------------------------


class TestDataController:
    def test_dc001_todo_in_email(self):
        card = _baseline()
        card["gov"]["dataController"]["contactEmail"] = "TODO"
        diags = run_all_rules(card)
        assert _has(diags, "DC-001")

    def test_dc001_silent_with_real_email(self):
        card = _baseline()
        diags = run_all_rules(card)
        assert not _has(diags, "DC-001")


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCliIntegration:
    """End-to-end checks that the validate command surfaces smart diagnostics."""

    def _write(self, tmp_path, card):
        import yaml
        path = tmp_path / "card.yaml"
        path.write_text(yaml.dump(card))
        return path

    def test_validate_includes_smart_diagnostics(self, tmp_path):
        from numinal.commands.validate import validate
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        # personalDataCategories empty -> PD-001
        path = self._write(tmp_path, card)
        result = validate(path)
        assert _has(result.smart_diagnostics, "PD-001")

    def test_no_smart_checks_flag(self, tmp_path):
        from numinal.commands.validate import validate
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        path = self._write(tmp_path, card)
        result = validate(path, include_smart_checks=False)
        assert result.smart_diagnostics == []

    def test_strict_flag_treats_warnings_as_errors(self, tmp_path):
        """Strict mode must elevate smart-rule warnings into a non-zero exit code."""
        from click.testing import CliRunner
        from numinal.cli import cli
        card = _baseline()
        card["version"] = "1.0"  # VF-001 warning
        path = self._write(tmp_path, card)

        runner = CliRunner()
        # Non-strict: warnings only, exit 0 (when only checking T1)
        result_default = runner.invoke(cli, ["validate", str(path), "--tier", "1"])
        assert result_default.exit_code == 0
        # Strict: warnings cause exit 1
        result_strict = runner.invoke(cli, ["validate", str(path), "--tier", "1", "--strict"])
        assert result_strict.exit_code == 1

    def test_smart_errors_affect_exit_code(self, tmp_path):
        from click.testing import CliRunner
        from numinal.cli import cli
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        # Empty categories -> PD-001 (error)
        path = self._write(tmp_path, card)

        runner = CliRunner()
        # Tier 1 alone passes; the only reason exit_code should be 1 is the smart error.
        result = runner.invoke(cli, ["validate", str(path), "--tier", "1"])
        assert result.exit_code == 1

    def test_no_smart_checks_silences_errors(self, tmp_path):
        from click.testing import CliRunner
        from numinal.cli import cli
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        path = self._write(tmp_path, card)

        runner = CliRunner()
        result = runner.invoke(cli, [
            "validate", str(path), "--tier", "1", "--no-smart-checks",
        ])
        assert result.exit_code == 0

    def test_json_output_includes_smart_checks(self, tmp_path):
        import json
        from click.testing import CliRunner
        from numinal.cli import cli
        card = _baseline()
        card["rai"]["dataOrigin"]["personalDataPresent"] = True
        path = self._write(tmp_path, card)

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(path), "--json-output"])
        # JSON output is emitted on stdout even with non-zero exit code
        data = json.loads(result.output)
        assert "smartChecks" in data
        rule_ids = {c["ruleId"] for c in data["smartChecks"]}
        assert "PD-001" in rule_ids
