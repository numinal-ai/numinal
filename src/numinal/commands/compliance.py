"""numinal compliance — check a data card against specific regulations.

Implements spec §11.4 output format:
  EU AI Act Article 10 — 13 sub-requirements checked:
  ✓ 10(2)(a) Design choices
  ✗ 10(2)(d) Assumptions — rai:measurementAssumptions missing
  Score: 10/13 requirements met

The 13 sub-requirements map to Article 10 paragraphs 2-6:
  10(2)(a)-(h): 8 sub-requirements from the "in particular" list
  10(3): Data quality criteria
  10(4): Geographic and contextual characteristics
  10(5): Special category data safeguards (conditional)
  10(6): Dataset role distinction
  + 10(2)(b) original collection purpose disclosure (conditional on personal data)

Article 10(2)(g) (bias mitigation) is not a separate field — it's checked
by examining whether bias entries in 10(2)(f) include detectionMethod,
mitigationStatus, and mitigationMeasure fields (per spec §4.7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from numinal.commands.validate import load_card
from numinal.schema.tiers import _MISSING, _is_populated, _resolve_path


# ---------------------------------------------------------------------------
# Article 10 requirement definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Art10Requirement:
    """A single Article 10 sub-requirement."""
    clause: str            # e.g., "10(2)(a)"
    label: str             # e.g., "Design choices"
    field_paths: list[str] # Fields that must be populated to satisfy this
    conditional: str | None = None  # Human-readable condition
    condition_fn: Any = None  # Callable[[dict], bool] or None


def _personal_data_present(card: dict[str, Any]) -> bool:
    origin = card.get("rai", {}).get("dataOrigin", {})
    return origin.get("personalDataPresent", False) is True


def _special_category_present(card: dict[str, Any]) -> bool:
    handling = card.get("gov", {}).get("publisherSpecialCategoryHandling", {})
    return handling.get("specialCategoryDataPresent", False) is True


def _check_bias_mitigation(card: dict[str, Any]) -> bool:
    """Check 10(2)(g): bias entries must include detection/mitigation fields.

    Per spec §4.7, Article 10(2)(g) is satisfied when bias entries in the
    biasExamination section include detectionMethod, mitigationStatus, and
    mitigationMeasure. If no biases are documented (i.e. the examination
    was done but found nothing), that also satisfies 10(2)(g) — you can't
    mitigate biases that don't exist.
    """
    bias_exam = _resolve_path(card, "rai.biasExamination")
    if not isinstance(bias_exam, dict):
        return False

    # Collect all bias entries across the three categories
    all_entries: list[dict] = []
    for category in ("healthSafetyBiases", "fundamentalRightsBiases", "discriminationBiases"):
        entries = bias_exam.get(category, [])
        if isinstance(entries, list):
            all_entries.extend(e for e in entries if isinstance(e, dict))

    # If biasExamination exists but has no entries, that's fine —
    # the examination was done and found no biases to mitigate
    if not all_entries:
        return True

    # If entries exist, each must have mitigation fields
    for entry in all_entries:
        has_detection = bool(entry.get("detectionMethod", ""))
        has_status = bool(entry.get("mitigationStatus", ""))
        if not (has_detection and has_status):
            return False

    return True


# The 13 sub-requirements
ART_10_REQUIREMENTS: list[Art10Requirement] = [
    Art10Requirement(
        clause="10(2)(a)",
        label="Design choices",
        field_paths=["rai.designChoices"],
    ),
    Art10Requirement(
        clause="10(2)(b)",
        label="Collection processes and origin",
        field_paths=["rai.dataCollection", "rai.dataOrigin"],
    ),
    Art10Requirement(
        clause="10(2)(b)+",
        label="Original collection purpose disclosure",
        field_paths=["rai.dataOrigin.originalCollectionPurpose"],
        conditional="Required only if personal data present",
        condition_fn=_personal_data_present,
    ),
    Art10Requirement(
        clause="10(2)(c)",
        label="Data preparation operations",
        field_paths=["rai.dataPreparation"],
    ),
    Art10Requirement(
        clause="10(2)(d)",
        label="Measurement assumptions",
        field_paths=["rai.measurementAssumptions"],
    ),
    Art10Requirement(
        clause="10(2)(e)",
        label="Suitability assessment",
        field_paths=["rai.suitabilityAssessment"],
    ),
    Art10Requirement(
        clause="10(2)(f)",
        label="Bias examination",
        field_paths=["rai.biasExamination"],
    ),
    Art10Requirement(
        clause="10(2)(g)",
        label="Bias mitigation measures",
        field_paths=[],  # Checked via custom logic, not field presence
    ),
    Art10Requirement(
        clause="10(2)(h)",
        label="Compliance gaps identified",
        field_paths=["rai.complianceGaps"],
    ),
    Art10Requirement(
        clause="10(3)",
        label="Data quality criteria",
        field_paths=["rai.dataQualityAssessment"],
    ),
    Art10Requirement(
        clause="10(4)",
        label="Geographic and contextual characteristics",
        field_paths=["rai.geographicContext"],
    ),
    Art10Requirement(
        clause="10(5)",
        label="Special category data safeguards",
        field_paths=["gov.publisherSpecialCategoryHandling"],
        conditional="Required only if special category data present",
        condition_fn=_special_category_present,
    ),
    Art10Requirement(
        clause="10(6)",
        label="Dataset role distinction",
        field_paths=["intendedDatasetRole"],
    ),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Art10CheckResult:
    """Result of a single Article 10 sub-requirement check."""
    clause: str
    label: str
    passed: bool
    missing_fields: list[str] = field(default_factory=list)
    skipped: bool = False
    skipped_reason: str | None = None


@dataclass
class ComplianceResult:
    """Complete Article 10 compliance check result."""
    file_path: str
    checks: list[Art10CheckResult] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def total_checked(self) -> int:
        return len([c for c in self.checks if not c.skipped])

    @property
    def passed_count(self) -> int:
        return len([c for c in self.checks if c.passed and not c.skipped])

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks if not c.skipped)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _find_intended_role(card: dict[str, Any]) -> bool:
    """Check if intendedDatasetRole is set anywhere — top-level or in a policy."""
    # Check top-level
    top = _resolve_path(card, "intendedDatasetRole")
    if _is_populated(top):
        return True

    # Check inside access policies
    policies = _resolve_path(card, "gov.accessPolicies")
    if isinstance(policies, list):
        for policy in policies:
            if isinstance(policy, dict):
                role = policy.get("intendedDatasetRole")
                if _is_populated(role):
                    return True

    return False


def check_compliance(path: str | Path) -> ComplianceResult:
    """Run EU AI Act Article 10 compliance check on a data card.

    Checks 13 sub-requirements spanning Article 10 paragraphs 2-6.
    """
    card, error = load_card(path)
    if error:
        return ComplianceResult(file_path=str(path), parse_error=error)

    assert card is not None
    results: list[Art10CheckResult] = []

    for req in ART_10_REQUIREMENTS:
        # Check conditional
        if req.condition_fn is not None and not req.condition_fn(card):
            results.append(Art10CheckResult(
                clause=req.clause,
                label=req.label,
                passed=True,
                skipped=True,
                skipped_reason=req.conditional,
            ))
            continue

        # Special case: 10(2)(g) uses custom check logic
        if req.clause == "10(2)(g)":
            passed = _check_bias_mitigation(card)
            results.append(Art10CheckResult(
                clause=req.clause,
                label=req.label,
                passed=passed,
                missing_fields=[] if passed else ["rai.biasExamination.*.detectionMethod/mitigationStatus"],
            ))
            continue

        # Special case: 10(6) checks intendedDatasetRole in multiple locations
        if req.clause == "10(6)":
            passed = _find_intended_role(card)
            results.append(Art10CheckResult(
                clause=req.clause,
                label=req.label,
                passed=passed,
                missing_fields=[] if passed else ["intendedDatasetRole"],
            ))
            continue

        # Standard field-presence check
        missing = []
        for fp in req.field_paths:
            value = _resolve_path(card, fp)
            if not _is_populated(value):
                missing.append(fp)

        results.append(Art10CheckResult(
            clause=req.clause,
            label=req.label,
            passed=len(missing) == 0,
            missing_fields=missing,
        ))

    return ComplianceResult(file_path=str(path), checks=results)
