"""Tier requirement definitions from numinal data card specification §10.

Each requirement specifies:
  - field_path: dot-separated path into the YAML structure
  - tiers: which tiers require this field (1=T1, 2=T2, 3=T3)
  - conditional: optional function that checks whether the requirement applies
  - article_10_clause: EU AI Act mapping (if applicable)
  - description: human-readable label for validation output

The tier model is hierarchical: T3 ⊇ T2 ⊇ T1 (spec §2.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class FieldRequirement:
    """A single field requirement for tier validation."""

    field_path: str
    tiers: frozenset[int]  # {1}, {2, 3}, {1, 2, 3}, etc.
    description: str
    article_10_clause: str | None = None
    conditional: str | None = None  # human-readable condition description
    condition_fn: Callable[[dict[str, Any]], bool] | None = None


def _personal_data_present(card: dict[str, Any]) -> bool:
    """Check if the card declares personal data."""
    origin = card.get("rai", {}).get("dataOrigin", {})
    return origin.get("personalDataPresent", False) is True


def _special_category_present(card: dict[str, Any]) -> bool:
    """Check if special category data is present."""
    handling = card.get("gov", {}).get("publisherSpecialCategoryHandling", {})
    return handling.get("specialCategoryDataPresent", False) is True


def _is_derived(card: dict[str, Any]) -> bool:
    """Check if the dataset is derived from another governed dataset."""
    derived = card.get("gov", {}).get("derivedFrom", [])
    return isinstance(derived, list) and len(derived) > 0


# ---------------------------------------------------------------------------
# Dataset-level requirements (§10, first table)
# ---------------------------------------------------------------------------

DATASET_LEVEL: list[FieldRequirement] = [
    FieldRequirement("name",                          frozenset({1, 2, 3}), "Dataset name"),
    FieldRequirement("description",                   frozenset({1, 2, 3}), "Dataset description"),
    FieldRequirement("version",                       frozenset({1, 2, 3}), "Dataset version"),
    FieldRequirement("license",                       frozenset({1, 2, 3}), "License"),
    FieldRequirement("creator",                       frozenset({1, 2, 3}), "Creator"),
    FieldRequirement("datePublished",                 frozenset({2, 3}),    "Date published"),
    FieldRequirement("distribution",                  frozenset({1, 2, 3}), "Distribution"),
    FieldRequirement("recordSet",                     frozenset({2, 3}),    "Record set definitions"),
    FieldRequirement("gov.governanceModel",           frozenset({1, 2, 3}), "Governance model"),
    FieldRequirement("gov.governanceVersion",         frozenset({1, 2, 3}), "Governance version"),
    FieldRequirement("gov.dataController",            frozenset({2, 3}),    "Data controller"),
    FieldRequirement("gov.dataClassification",        frozenset({2, 3}),    "Data classification"),
    FieldRequirement(
        "gov.legalBasis", frozenset({2, 3}), "Legal basis",
        conditional="Required at T2 only if personal data present",
        condition_fn=lambda card: _personal_data_present(card) if 2 in {2} else True,
        # Note: at T3 it's always required. The condition only gates T2.
        # We handle this by including it in {2,3} and checking condition at T2.
    ),
    FieldRequirement("gov.regulatoryAlignment",       frozenset({3}),       "Regulatory alignment"),
    FieldRequirement("gov.lastGovernanceReview",       frozenset({3}),       "Last governance review date"),
    FieldRequirement("gov.licenseGovernanceRelationship", frozenset({3}),    "License-governance relationship"),
]


# ---------------------------------------------------------------------------
# RAI / Article 10 requirements (§10, second table)
# ---------------------------------------------------------------------------

RAI_FIELDS: list[FieldRequirement] = [
    FieldRequirement(
        "rai.designChoices", frozenset({2, 3}),
        "Design choices", article_10_clause="10(2)(a)",
    ),
    FieldRequirement(
        "rai.dataCollection", frozenset({2, 3}),
        "Data collection description", article_10_clause="10(2)(b)",
    ),
    FieldRequirement(
        "rai.dataOrigin", frozenset({2, 3}),
        "Data origin", article_10_clause="10(2)(b)",
    ),
    FieldRequirement(
        "rai.dataOrigin.originalCollectionPurpose", frozenset({2, 3}),
        "Original collection purpose",
        article_10_clause="10(2)(b)",
        conditional="Required only if personal data present",
        condition_fn=_personal_data_present,
    ),
    FieldRequirement(
        "rai.dataPreparation", frozenset({2, 3}),
        "Data preparation operations", article_10_clause="10(2)(c)",
    ),
    FieldRequirement(
        "rai.measurementAssumptions", frozenset({2, 3}),
        "Measurement assumptions", article_10_clause="10(2)(d)",
    ),
    FieldRequirement(
        "rai.suitabilityAssessment", frozenset({2, 3}),
        "Suitability assessment", article_10_clause="10(2)(e)",
    ),
    FieldRequirement(
        "rai.biasExamination", frozenset({2, 3}),
        "Bias examination", article_10_clause="10(2)(f)",
    ),
    FieldRequirement(
        "rai.complianceGaps", frozenset({2, 3}),
        "Compliance gaps", article_10_clause="10(2)(h)",
    ),
    FieldRequirement(
        "rai.dataQualityAssessment", frozenset({2, 3}),
        "Data quality assessment", article_10_clause="10(3)",
    ),
    FieldRequirement(
        "rai.geographicContext", frozenset({2, 3}),
        "Geographic context", article_10_clause="10(4)",
    ),
    FieldRequirement(
        "rai.contextualCharacteristics", frozenset({3}),
        "Contextual characteristics", article_10_clause="10(4)",
    ),
    FieldRequirement(
        "gov.publisherSpecialCategoryHandling", frozenset({2, 3}),
        "Special category data handling",
        article_10_clause="10(5)",
        conditional="Required only if special category data present",
        condition_fn=_special_category_present,
    ),
]


# ---------------------------------------------------------------------------
# Governance fields (§10, third table)
# ---------------------------------------------------------------------------

GOVERNANCE_FIELDS: list[FieldRequirement] = [
    FieldRequirement("gov.accessPolicies",            frozenset({3}),       "Access policies (≥1)"),
    FieldRequirement("gov.derivedFrom", frozenset({3}), "Derived dataset provenance",
                     conditional="Required at T3 only if dataset is derived",
                     condition_fn=_is_derived),
]

# Sub-fields of access policies — checked per-policy when policies exist
ACCESS_POLICY_SUBFIELDS: list[str] = [
    "eligibility",
    "permittedPurposes",
    "accessScope",
    "retention",
    "redistribution",
    "prerequisites",
    "intendedDatasetRole",
]

# intendedDatasetRole is required at T2 and T3 (even without full access policies)
INTENDED_ROLE_REQ = FieldRequirement(
    "intendedDatasetRole", frozenset({2, 3}),
    "Intended dataset role (training/validation/testing)",
)


# ---------------------------------------------------------------------------
# All requirements combined
# ---------------------------------------------------------------------------

ALL_REQUIREMENTS: list[FieldRequirement] = DATASET_LEVEL + RAI_FIELDS + GOVERNANCE_FIELDS


def requirements_for_tier(tier: int) -> list[FieldRequirement]:
    """Get all requirements that apply at a given tier."""
    return [r for r in ALL_REQUIREMENTS if tier in r.tiers]


def _resolve_path(data: dict[str, Any], path: str) -> Any:
    """Resolve a dot-separated path into a nested dict.

    Returns the value if found, or a sentinel _MISSING if not.
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


class _MissingSentinel:
    """Sentinel for missing values (distinct from None, which is a valid value)."""
    def __repr__(self) -> str:
        return "<MISSING>"

_MISSING = _MissingSentinel()


def _is_populated(value: Any) -> bool:
    """Check if a value counts as 'populated' for tier validation.

    Empty strings, empty lists, empty dicts, None, and the MISSING sentinel
    all count as unpopulated. Zero is considered populated (it's a valid value
    for numeric fields).
    """
    if isinstance(value, _MissingSentinel):
        return False
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True
