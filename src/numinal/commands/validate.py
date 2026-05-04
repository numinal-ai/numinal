"""numinal validate — validate a data card against all three tiers.

Implements spec §11.3 output format:
  Tier 1 (discovery):        ✓ PASS — 12/12 required fields
  Tier 2 (regulatory):       ✗ FAIL — 9/14 required fields
    Missing: ...
  Tier 3 (governed sharing): ✗ FAIL — 14/23 required fields
    Missing: ...
  Completeness: 67% (35/52 total fields)

Also validates vocabulary terms against §3 controlled vocabularies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from numinal.schema.tiers import (
    ACCESS_POLICY_SUBFIELDS,
    ALL_REQUIREMENTS,
    FieldRequirement,
    _MISSING,
    _MissingSentinel,
    _is_populated,
    _resolve_path,
    requirements_for_tier,
)
from numinal.schema.vocabularies import (
    ACCESS_METHODS,
    ACCESS_SCOPE_TYPES,
    AUDIT_FREQUENCIES,
    BIAS_SEVERITIES,
    CITATION_FORMATS,
    CONSUMER_TYPES,
    DATA_CLASSIFICATIONS,
    DATASET_ROLES,
    DELETION_METHODS,
    FUNDING_TRACKS,
    GOVERNANCE_MODELS,
    HIGH_RISK_DOMAINS,
    LICENSE_GOVERNANCE_RELATIONSHIPS,
    MITIGATION_STATUSES,
    PREREQUISITE_TYPES,
    PURPOSE_MODIFIERS,
    PURPOSES,
    REPORTING_FREQUENCIES,
    RETENTION_TYPES,
    SUBPROCESSOR_SHARING,
    VERIFICATION_METHODS,
    is_custom_term,
    validate_term,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FieldResult:
    """Validation result for a single field."""
    field_path: str
    description: str
    present: bool
    article_10_clause: str | None = None
    skipped_reason: str | None = None  # e.g. "conditional: personal data not present"


@dataclass
class TierResult:
    """Validation result for a single tier."""
    tier: int
    tier_name: str
    passed: bool
    required_count: int
    present_count: int
    missing: list[FieldResult] = field(default_factory=list)
    skipped: list[FieldResult] = field(default_factory=list)


@dataclass
class VocabWarning:
    """Warning for non-canonical vocabulary usage."""
    field_path: str
    term: str
    message: str
    is_error: bool = False  # True for invalid terms, False for custom: warnings


@dataclass
class PolicyValidationResult:
    """Validation result for access policy sub-fields."""
    policy_id: str
    missing_subfields: list[str]


@dataclass
class ValidationResult:
    """Complete validation result."""
    file_path: str
    tiers: list[TierResult]
    vocab_warnings: list[VocabWarning] = field(default_factory=list)
    policy_results: list[PolicyValidationResult] = field(default_factory=list)
    parse_error: str | None = None

    @property
    def total_fields(self) -> int:
        return len(ALL_REQUIREMENTS)

    @property
    def populated_fields(self) -> int:
        """Count of unique fields that are populated across all tiers."""
        # Deduplicate by field_path across tiers
        populated_paths = set()
        for tier_result in self.tiers:
            for req in requirements_for_tier(tier_result.tier):
                if req.field_path not in populated_paths:
                    # Check if it was present in this tier's results
                    for missing in tier_result.missing:
                        if missing.field_path == req.field_path:
                            break
                    else:
                        # Not in missing and not skipped = present
                        for skipped in tier_result.skipped:
                            if skipped.field_path == req.field_path:
                                break
                        else:
                            populated_paths.add(req.field_path)
        return len(populated_paths)

    @property
    def completeness_pct(self) -> float:
        total = self.total_fields
        return (self.populated_fields / total * 100) if total > 0 else 0.0


# ---------------------------------------------------------------------------
# Tier names (spec §2.4)
# ---------------------------------------------------------------------------

TIER_NAMES = {
    1: "discovery",
    2: "regulatory",
    3: "governed sharing",
}


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------

def _check_requirement(req: FieldRequirement, card: dict[str, Any], tier: int) -> FieldResult:
    """Check a single requirement against the card data."""
    # Check conditional requirements
    if req.condition_fn is not None:
        # For the legalBasis special case: required at T2 only if personal data,
        # but always required at T3
        if tier == 2 and req.field_path == "gov.legalBasis":
            if not _personal_data_present(card):
                return FieldResult(
                    field_path=req.field_path,
                    description=req.description,
                    present=True,  # Mark as passing since condition not met
                    article_10_clause=req.article_10_clause,
                    skipped_reason="Conditional: personal data not present",
                )
        elif not req.condition_fn(card):
            return FieldResult(
                field_path=req.field_path,
                description=req.description,
                present=True,  # Mark as passing since condition not met
                article_10_clause=req.article_10_clause,
                skipped_reason=req.conditional,
            )

    value = _resolve_path(card, req.field_path)
    present = _is_populated(value)

    return FieldResult(
        field_path=req.field_path,
        description=req.description,
        present=present,
        article_10_clause=req.article_10_clause,
    )


def _personal_data_present(card: dict[str, Any]) -> bool:
    """Check if the card declares personal data."""
    origin = card.get("rai", {}).get("dataOrigin", {})
    return origin.get("personalDataPresent", False) is True


def _validate_tier(tier: int, card: dict[str, Any]) -> TierResult:
    """Validate a card against a single tier."""
    requirements = requirements_for_tier(tier)
    results = [_check_requirement(req, card, tier) for req in requirements]

    missing = [r for r in results if not r.present]
    skipped = [r for r in results if r.skipped_reason is not None]
    present_count = len(requirements) - len(missing)

    return TierResult(
        tier=tier,
        tier_name=TIER_NAMES[tier],
        passed=len(missing) == 0,
        required_count=len(requirements),
        present_count=present_count,
        missing=missing,
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Vocabulary validation
# ---------------------------------------------------------------------------

def _validate_vocab_terms(card: dict[str, Any]) -> list[VocabWarning]:
    """Validate all vocabulary terms in the card against §3 vocabularies."""
    warnings: list[VocabWarning] = []

    # gov.governanceModel → GOVERNANCE_MODELS
    _check_single_term(card, "gov.governanceModel", GOVERNANCE_MODELS, warnings)

    # gov.dataClassification → DATA_CLASSIFICATIONS
    _check_single_term(card, "gov.dataClassification", DATA_CLASSIFICATIONS, warnings)

    # gov.licenseGovernanceRelationship.relationship → LICENSE_GOVERNANCE_RELATIONSHIPS
    lgr = _resolve_path(card, "gov.licenseGovernanceRelationship")
    if isinstance(lgr, dict) and "relationship" in lgr:
        _check_term(lgr["relationship"], "gov.licenseGovernanceRelationship.relationship",
                     LICENSE_GOVERNANCE_RELATIONSHIPS, warnings)

    # gov.fundingSource.fundingTrack → FUNDING_TRACKS
    fs = _resolve_path(card, "gov.fundingSource")
    if isinstance(fs, dict) and "fundingTrack" in fs:
        _check_term(fs["fundingTrack"], "gov.fundingSource.fundingTrack",
                     FUNDING_TRACKS, warnings)

    # gov.impactReporting.reportingFrequency → REPORTING_FREQUENCIES
    ir = _resolve_path(card, "gov.impactReporting")
    if isinstance(ir, dict) and "reportingFrequency" in ir:
        _check_term(ir["reportingFrequency"], "gov.impactReporting.reportingFrequency",
                     REPORTING_FREQUENCIES, warnings)

    # Access policy vocabulary checks
    policies = _resolve_path(card, "gov.accessPolicies")
    if isinstance(policies, list):
        for i, policy in enumerate(policies):
            prefix = f"gov.accessPolicies[{i}]"
            _validate_policy_vocab(policy, prefix, warnings)

    return warnings


def _validate_policy_vocab(policy: dict[str, Any], prefix: str,
                           warnings: list[VocabWarning]) -> None:
    """Validate vocabulary terms within a single access policy."""
    # eligibility.consumerType → CONSUMER_TYPES
    elig = policy.get("eligibility", {})
    for ct in elig.get("consumerType", []):
        _check_term(ct, f"{prefix}.eligibility.consumerType", CONSUMER_TYPES, warnings)

    # permittedPurposes / prohibitedPurposes → PURPOSES
    for pp in policy.get("permittedPurposes", []):
        _check_term(pp, f"{prefix}.permittedPurposes", PURPOSES, warnings)
    for pp in policy.get("prohibitedPurposes", []):
        _check_term(pp, f"{prefix}.prohibitedPurposes", PURPOSES, warnings)

    # purposeModifiers → PURPOSE_MODIFIERS
    for pm in policy.get("purposeModifiers", []):
        _check_term(pm, f"{prefix}.purposeModifiers", PURPOSE_MODIFIERS, warnings)

    # accessScope.scopeType → ACCESS_SCOPE_TYPES
    scope = policy.get("accessScope", {})
    if "scopeType" in scope:
        _check_term(scope["scopeType"], f"{prefix}.accessScope.scopeType",
                     ACCESS_SCOPE_TYPES, warnings)
    if "accessMethod" in scope:
        _check_term(scope["accessMethod"], f"{prefix}.accessScope.accessMethod",
                     ACCESS_METHODS, warnings)

    # retention fields
    ret = policy.get("retention", {})
    if "retentionType" in ret:
        _check_term(ret["retentionType"], f"{prefix}.retention.retentionType",
                     RETENTION_TYPES, warnings)
    if "deletionMethod" in ret:
        _check_term(ret["deletionMethod"], f"{prefix}.retention.deletionMethod",
                     DELETION_METHODS, warnings)

    # redistribution.sharingWithSubprocessors
    redist = policy.get("redistribution", {})
    if "sharingWithSubprocessors" in redist:
        _check_term(redist["sharingWithSubprocessors"],
                     f"{prefix}.redistribution.sharingWithSubprocessors",
                     SUBPROCESSOR_SHARING, warnings)

    # attribution.citationFormat
    attr = policy.get("attribution", {})
    if "citationFormat" in attr:
        _check_term(attr["citationFormat"], f"{prefix}.attribution.citationFormat",
                     CITATION_FORMATS, warnings)

    # auditRequirements.auditFrequency
    audit = policy.get("auditRequirements", {})
    if "auditFrequency" in audit:
        _check_term(audit["auditFrequency"], f"{prefix}.auditRequirements.auditFrequency",
                     AUDIT_FREQUENCIES, warnings)

    # prerequisites[].prerequisiteType, verificationMethod
    for j, prereq in enumerate(policy.get("prerequisites", [])):
        if "prerequisiteType" in prereq:
            _check_term(prereq["prerequisiteType"],
                         f"{prefix}.prerequisites[{j}].prerequisiteType",
                         PREREQUISITE_TYPES, warnings)
        if "verificationMethod" in prereq:
            _check_term(prereq["verificationMethod"],
                         f"{prefix}.prerequisites[{j}].verificationMethod",
                         VERIFICATION_METHODS, warnings)

    # intendedDatasetRole
    for role in policy.get("intendedDatasetRole", []):
        _check_term(role, f"{prefix}.intendedDatasetRole", DATASET_ROLES, warnings)


def _check_single_term(card: dict[str, Any], path: str, vocab: set[str],
                        warnings: list[VocabWarning]) -> None:
    """Check a single term at a given path."""
    value = _resolve_path(card, path)
    if isinstance(value, str) and value.strip():
        _check_term(value, path, vocab, warnings)


def _check_term(term: str, field_path: str, vocab: set[str],
                warnings: list[VocabWarning]) -> None:
    """Validate a single term and append any warning/error."""
    if not term or not term.strip():
        return
    valid, msg = validate_term(term, vocab, field_path)
    if msg:
        warnings.append(VocabWarning(
            field_path=field_path,
            term=term,
            message=msg,
            is_error=not valid,
        ))


# ---------------------------------------------------------------------------
# Access policy sub-field validation (T3)
# ---------------------------------------------------------------------------

def _validate_access_policies(card: dict[str, Any]) -> list[PolicyValidationResult]:
    """Validate that T3 access policies have all required sub-fields."""
    results: list[PolicyValidationResult] = []
    policies = _resolve_path(card, "gov.accessPolicies")
    if not isinstance(policies, list):
        return results

    for policy in policies:
        if not isinstance(policy, dict):
            continue
        pid = policy.get("policyId", "<unnamed>")
        missing = []
        for subfield in ACCESS_POLICY_SUBFIELDS:
            value = policy.get(subfield)
            if not _is_populated(value):
                missing.append(subfield)
        if missing:
            results.append(PolicyValidationResult(policy_id=pid, missing_subfields=missing))

    return results


# ---------------------------------------------------------------------------
# Bias field vocabulary checks
# ---------------------------------------------------------------------------

def _validate_bias_vocab(card: dict[str, Any], warnings: list[VocabWarning]) -> None:
    """Check bias-specific vocabulary (severity, mitigationStatus)."""
    bias_exam = _resolve_path(card, "rai.biasExamination")
    if not isinstance(bias_exam, dict):
        return

    for category in ("healthSafetyBiases", "fundamentalRightsBiases", "discriminationBiases"):
        biases = bias_exam.get(category, [])
        if not isinstance(biases, list):
            continue
        for i, entry in enumerate(biases):
            prefix = f"rai.biasExamination.{category}[{i}]"
            if "severity" in entry:
                _check_term(entry["severity"], f"{prefix}.severity",
                             BIAS_SEVERITIES, warnings)
            if "mitigationStatus" in entry:
                _check_term(entry["mitigationStatus"], f"{prefix}.mitigationStatus",
                             MITIGATION_STATUSES, warnings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_card(path: str | Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load a data card from YAML or JSON.

    Returns (card_data, error_message).
    """
    p = Path(path)
    if not p.exists():
        return None, f"File not found: {p}"

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"Cannot read file: {e}"

    if p.suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return None, f"YAML parse error: {e}"
    elif p.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return None, f"JSON parse error: {e}"
    else:
        return None, f"Unsupported file format: {p.suffix} (expected .yaml, .yml, or .json)"

    if not isinstance(data, dict):
        return None, "Data card must be a YAML/JSON mapping (dict), not a scalar or list"

    return data, None


def validate(path: str | Path) -> ValidationResult:
    """Validate a data card file against all three tiers.

    Returns a complete ValidationResult with tier results,
    vocabulary warnings, and policy sub-field checks.
    """
    card, error = load_card(path)
    if error:
        return ValidationResult(
            file_path=str(path),
            tiers=[],
            parse_error=error,
        )

    assert card is not None

    # Run tier validation
    tier_results = [_validate_tier(tier, card) for tier in (1, 2, 3)]

    # Run vocabulary validation
    vocab_warnings = _validate_vocab_terms(card)
    _validate_bias_vocab(card, vocab_warnings)

    # Run access policy sub-field validation
    policy_results = _validate_access_policies(card)

    return ValidationResult(
        file_path=str(path),
        tiers=tier_results,
        vocab_warnings=vocab_warnings,
        policy_results=policy_results,
    )
