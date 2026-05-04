"""numinal smart validation rules.

Cross-references fields within a data card and against the auto-detected
dataset structure (`recordSet`, `_fileManifest`) to surface logical
contradictions, likely omissions, and contextual observations beyond simple
field-presence checks.

Each rule has a unique ID, severity ("error", "warning", "info"), and a
human-readable message. Rules are organised by category and exposed through
``run_all_rules(card)``.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class SmartDiagnostic:
    """A single smart-rule finding."""

    rule_id: str
    severity: str  # "error", "warning", "info"
    message: str
    field_path: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _get(card: dict[str, Any], *path: str, default: Any = None) -> Any:
    """Safe nested dict lookup. Returns default if any key is missing or not a dict."""
    cur: Any = card
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _ensure_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_truthy_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _record_sets(card: dict[str, Any]) -> list[dict[str, Any]]:
    rs = card.get("recordSet")
    if isinstance(rs, list):
        return [r for r in rs if isinstance(r, dict)]
    return []


def _record_set_fields(rs: dict[str, Any]) -> list[dict[str, Any]]:
    fields = rs.get("fields")
    if isinstance(fields, list):
        return [f for f in fields if isinstance(f, dict)]
    return []


def _all_field_names(card: dict[str, Any]) -> list[tuple[str, str]]:
    """Return list of (recordset_name, field_name) tuples across all record sets."""
    out: list[tuple[str, str]] = []
    for rs in _record_sets(card):
        rs_name = str(rs.get("name", "<unnamed>"))
        for f in _record_set_fields(rs):
            name = f.get("name")
            if isinstance(name, str) and name:
                out.append((rs_name, name))
    return out


def _bias_entries(card: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Return list of (category, entry) tuples for all bias entries."""
    bias = _ensure_dict(_get(card, "rai", "biasExamination"))
    out: list[tuple[str, dict[str, Any]]] = []
    for cat in ("healthSafetyBiases", "fundamentalRightsBiases", "discriminationBiases"):
        for entry in _ensure_list(bias.get(cat)):
            if isinstance(entry, dict):
                out.append((cat, entry))
    return out


def _parse_date(value: Any) -> datetime.date | None:
    """Parse an ISO 8601 date string. Returns None if not parseable."""
    if isinstance(value, datetime.date):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Accept YYYY-MM-DD or full ISO datetime
    try:
        return datetime.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _today() -> datetime.date:
    return datetime.date.today()


def _is_semver(version: Any) -> bool:
    return isinstance(version, str) and bool(_SEMVER_RE.match(version.strip()))


# Patterns used for column-name matching (case-insensitive substring match)
_DEMOGRAPHIC_PATTERNS = (
    "gender", "sex", "age", "ethnicity", "race", "religion",
    "disability", "nationality", "marital_status", "sexual_orientation",
    "pregnancy", "trans_status",
)

_PII_PATTERNS = (
    "name", "first_name", "last_name", "surname", "forename",
    "email", "address", "street", "phone", "telephone", "mobile",
    "postcode", "zip_code", "zipcode", "date_of_birth", "dob", "birth_date",
    "ssn", "social_security", "nhs_number", "nhi_number", "national_insurance",
    "ni_number", "ip_address", "mac_address", "passport", "drivers_license",
    "patient_id", "subject_id", "person_id",
)

_HEALTH_PATTERNS = (
    "diagnosis", "condition", "treatment", "medication", "prescription",
    "symptom", "icd", "snomed", "procedure", "clinical", "medical",
    "health", "disease", "therapy", "dosage", "allergy", "blood",
    "genetic", "genomic", "biomarker", "vital_sign", "heart_rate", "bmi",
)

_HIGH_RISK_PURPOSE_DOMAIN = {
    "clinical-decision-support": "essential-services",
    "infrastructure-monitoring": "critical-infrastructure",
    "public-service-delivery": "essential-services",
}

_DATA_FILE_EXTS_FOR_SOURCE_COUNT = {
    ".csv", ".tsv", ".json", ".jsonl", ".parquet", ".arrow",
    ".xlsx", ".xls", ".ndjson", ".feather",
}

_NON_DATA_FILE_NAMES = {
    "readme", "license", "licence", "notice", "changelog",
    "numinal", "datacard", "data-card",
}

_EXT_TO_MIME = {
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".parquet": "application/x-parquet",
    ".arrow": "application/x-apache-arrow",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".tar": "application/x-tar",
}


def _column_matches(col: str, patterns: Iterable[str]) -> bool:
    lower = col.lower()
    return any(p in lower for p in patterns)


def _format_bytes(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024:
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} {unit}"
        f /= 1024
    return f"{f:.1f} PB"


# ---------------------------------------------------------------------------
# Category 1: Dataset-Aware Rules (DS-001 .. DS-008)
# ---------------------------------------------------------------------------


def _check_dataset_aware(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []

    bias = _ensure_dict(_get(card, "rai", "biasExamination"))
    discrimination = _ensure_list(bias.get("discriminationBiases"))

    # DS-001
    discrim_refs: set[str] = set()
    for entry in discrimination:
        if not isinstance(entry, dict):
            continue
        for key in ("protectedCharacteristic", "affectedPopulation"):
            v = entry.get(key)
            if isinstance(v, str) and v.strip():
                discrim_refs.add(v.strip().lower())

    for rs_name, col in _all_field_names(card):
        if _column_matches(col, _DEMOGRAPHIC_PATTERNS):
            col_lower = col.lower()
            referenced = any(col_lower in r or r in col_lower for r in discrim_refs)
            if not referenced:
                diags.append(SmartDiagnostic(
                    rule_id="DS-001",
                    severity="warning",
                    message=(
                        f"Column '{col}' in recordSet '{rs_name}' appears to contain "
                        "demographic data but has no corresponding entry in "
                        "discriminationBiases. Article 10(2)(f) requires examination "
                        "of biases relating to prohibited discrimination."
                    ),
                    field_path=f"recordSet.{rs_name}.fields.{col}",
                ))

    # DS-002
    pdp = _get(card, "rai", "dataOrigin", "personalDataPresent")
    if pdp is not True:
        for rs_name, col in _all_field_names(card):
            if _column_matches(col, _PII_PATTERNS):
                diags.append(SmartDiagnostic(
                    rule_id="DS-002",
                    severity="warning",
                    message=(
                        f"Column '{col}' in recordSet '{rs_name}' looks like personal "
                        "data but personalDataPresent is false. Verify and update if "
                        "this is personal data under GDPR Article 4(1)."
                    ),
                    field_path=f"recordSet.{rs_name}.fields.{col}",
                ))

    # DS-003
    scdp = _get(card, "gov", "publisherSpecialCategoryHandling", "specialCategoryDataPresent")
    if scdp is not True:
        for rs_name, col in _all_field_names(card):
            if _column_matches(col, _HEALTH_PATTERNS):
                diags.append(SmartDiagnostic(
                    rule_id="DS-003",
                    severity="warning",
                    message=(
                        f"Column '{col}' in recordSet '{rs_name}' looks like health "
                        "data, which is special category under GDPR Article 9. "
                        "specialCategoryDataPresent is false — verify this is correct."
                    ),
                    field_path=f"recordSet.{rs_name}.fields.{col}",
                ))

    # DS-004
    missing_by_field = _ensure_dict(
        _get(card, "rai", "dataQualityAssessment", "completeness", "missingDataByField")
    )
    documented_fields = {str(k) for k in missing_by_field.keys()}
    for rs in _record_sets(card):
        rs_name = str(rs.get("name", "<unnamed>"))
        for f in _record_set_fields(rs):
            name = f.get("name")
            null_rate = f.get("nullRate")
            if not isinstance(name, str) or not isinstance(null_rate, (int, float)):
                continue
            if null_rate > 0.05 and name not in documented_fields:
                diags.append(SmartDiagnostic(
                    rule_id="DS-004",
                    severity="warning",
                    message=(
                        f"Column '{name}' in recordSet '{rs_name}' has "
                        f"{null_rate:.1%} null rate but is not documented in "
                        "missingDataByField. Article 10(3) requires assessment "
                        "of completeness."
                    ),
                    field_path=f"recordSet.{rs_name}.fields.{name}",
                ))

    # DS-005
    manifest = card.get("_fileManifest")
    distribution = _ensure_list(card.get("distribution"))
    if isinstance(manifest, list) and manifest:
        manifest_count = len(manifest)
        manifest_size = sum(int(m.get("sizeBytes", 0)) for m in manifest if isinstance(m, dict))
        dist_count = sum(int(d.get("fileCount", 0)) for d in distribution if isinstance(d, dict))
        dist_size = sum(int(d.get("totalSizeBytes", 0)) for d in distribution if isinstance(d, dict))
        if dist_count > 0 or dist_size > 0:
            count_diff_ratio = (
                abs(manifest_count - dist_count) / manifest_count
                if manifest_count else 0
            )
            size_diff_ratio = (
                abs(manifest_size - dist_size) / manifest_size
                if manifest_size else 0
            )
            if count_diff_ratio > 0.20 or size_diff_ratio > 0.50:
                diags.append(SmartDiagnostic(
                    rule_id="DS-005",
                    severity="warning",
                    message=(
                        f"File manifest has {manifest_count} files "
                        f"({_format_bytes(manifest_size)}) but distribution claims "
                        f"{dist_count} files ({_format_bytes(dist_size)}). Verify "
                        "distribution entries are current."
                    ),
                    field_path="distribution",
                ))

    # DS-006
    measurements = _ensure_list(_get(card, "rai", "measurementAssumptions"))
    all_field_pairs = _all_field_names(card)
    if measurements and all_field_pairs:
        ma_field_strings: list[str] = []
        for m in measurements:
            if isinstance(m, dict):
                v = m.get("field")
                if isinstance(v, str):
                    ma_field_strings.append(v.lower())
                elif isinstance(v, list):
                    ma_field_strings.extend(str(x).lower() for x in v if x)
        covered_fields = set()
        for _rs_name, col in all_field_pairs:
            col_lower = col.lower()
            if any(col_lower in s or s == col_lower for s in ma_field_strings):
                covered_fields.add(col_lower)
        total = len({c.lower() for _r, c in all_field_pairs})
        covered = len(covered_fields)
        if total > 0 and (covered / total) < 0.25:
            diags.append(SmartDiagnostic(
                rule_id="DS-006",
                severity="info",
                message=(
                    f"Only {covered}/{total} recordSet fields are referenced in "
                    "measurementAssumptions. Consider documenting assumptions for "
                    "key fields. Article 10(2)(d) requires documenting the "
                    "information that the data are supposed to measure and represent."
                ),
                field_path="rai.measurementAssumptions",
            ))

    # DS-007
    if isinstance(manifest, list) and manifest:
        dist_mimes = {
            d.get("contentType")
            for d in distribution if isinstance(d, dict) and isinstance(d.get("contentType"), str)
        }
        manifest_exts: set[str] = set()
        for m in manifest:
            if not isinstance(m, dict):
                continue
            path = m.get("path")
            if not isinstance(path, str):
                continue
            idx = path.rfind(".")
            if idx == -1:
                continue
            ext = path[idx:].lower()
            if ext:
                manifest_exts.add(ext)
        # Only consider extensions we have a known MIME for
        for ext in sorted(manifest_exts):
            mime = _EXT_TO_MIME.get(ext)
            if mime and mime not in dist_mimes:
                diags.append(SmartDiagnostic(
                    rule_id="DS-007",
                    severity="warning",
                    message=(
                        f"File manifest contains {ext} files but no distribution "
                        f"entry declares content type {mime}."
                    ),
                    field_path="distribution",
                ))

    # DS-008
    aggregation_performed = _get(card, "rai", "dataPreparation", "aggregation", "performed") is True
    if aggregation_performed and isinstance(manifest, list):
        data_files = []
        for m in manifest:
            if not isinstance(m, dict):
                continue
            path = m.get("path")
            if not isinstance(path, str):
                continue
            lower = path.lower()
            base = lower.rsplit("/", 1)[-1]
            stem = base.split(".", 1)[0]
            if stem in _NON_DATA_FILE_NAMES:
                continue
            idx = base.rfind(".")
            ext = base[idx:] if idx != -1 else ""
            if ext in _DATA_FILE_EXTS_FOR_SOURCE_COUNT:
                data_files.append(path)
        if len(data_files) == 1:
            diags.append(SmartDiagnostic(
                rule_id="DS-008",
                severity="info",
                message=(
                    "Aggregation is marked as performed but only one data file is "
                    "present. If aggregation was done pre-publication, consider "
                    "documenting the source count."
                ),
                field_path="rai.dataPreparation.aggregation",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 2: Personal Data Consistency (PD-001 .. PD-005)
# ---------------------------------------------------------------------------


def _check_personal_data(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    origin = _ensure_dict(_get(card, "rai", "dataOrigin"))
    pdp = origin.get("personalDataPresent")
    categories = _ensure_list(origin.get("personalDataCategories"))
    legal_basis = _get(card, "gov", "legalBasis")
    consent_basis = origin.get("consentBasis")
    purpose = origin.get("originalCollectionPurpose")

    if pdp is True:
        # PD-001
        if not categories:
            diags.append(SmartDiagnostic(
                rule_id="PD-001",
                severity="error",
                message=(
                    "personalDataPresent is true but no personalDataCategories are "
                    "listed. Specify which categories of personal data are present "
                    "(e.g., health-data, racial-ethnic-origin)."
                ),
                field_path="rai.dataOrigin.personalDataCategories",
            ))
        # PD-002
        if not _is_truthy_str(legal_basis) and not (
            isinstance(legal_basis, list) and legal_basis
        ):
            diags.append(SmartDiagnostic(
                rule_id="PD-002",
                severity="error",
                message=(
                    "personalDataPresent is true but no legal basis is specified. "
                    "A GDPR legal basis is required for processing personal data."
                ),
                field_path="gov.legalBasis",
            ))
        # PD-004
        if not _is_truthy_str(consent_basis) and not (
            isinstance(consent_basis, list) and consent_basis
        ):
            diags.append(SmartDiagnostic(
                rule_id="PD-004",
                severity="warning",
                message=(
                    "personalDataPresent is true but consentBasis is not specified. "
                    "Document the legal basis for the original data collection."
                ),
                field_path="rai.dataOrigin.consentBasis",
            ))
        # PD-005
        if (not _is_truthy_str(purpose)) or (
            isinstance(purpose, str) and purpose.strip().upper().startswith("TODO")
        ):
            diags.append(SmartDiagnostic(
                rule_id="PD-005",
                severity="warning",
                message=(
                    "personalDataPresent is true but originalCollectionPurpose is "
                    "not documented. Article 10(2)(b) requires documenting the "
                    "original purpose for which data was collected."
                ),
                field_path="rai.dataOrigin.originalCollectionPurpose",
            ))

    # PD-003
    if categories and pdp is False:
        diags.append(SmartDiagnostic(
            rule_id="PD-003",
            severity="warning",
            message=(
                f"personalDataCategories lists {categories} but personalDataPresent "
                "is false. This is contradictory — update one or the other."
            ),
            field_path="rai.dataOrigin",
        ))

    return diags


# ---------------------------------------------------------------------------
# Category 3: Special Category Data Consistency (SC-001 .. SC-004)
# ---------------------------------------------------------------------------


_SC_CONDITIONS: tuple[tuple[str, str], ...] = (
    ("a_alternativeDataInsufficient", "evidence"),
    ("b_technicalReuseLimitations", "measures"),
    ("c_accessControlAndConfidentiality", "measures"),
    ("d_noThirdPartyTransfer", "enforcement"),
    ("e_deletionOnCompletion", "mechanism"),
    ("f_processingRecords", "ropaReference"),
)


def _check_special_category(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    handling = _ensure_dict(_get(card, "gov", "publisherSpecialCategoryHandling"))
    scdp = handling.get("specialCategoryDataPresent")
    categories = _ensure_list(handling.get("categories"))
    pdp = _get(card, "rai", "dataOrigin", "personalDataPresent")

    if scdp is True:
        # SC-001
        if not categories:
            diags.append(SmartDiagnostic(
                rule_id="SC-001",
                severity="error",
                message=(
                    "specialCategoryDataPresent is true but no categories are listed. "
                    "Specify which special categories are present (e.g., health-data, "
                    "racial-ethnic-origin)."
                ),
                field_path="gov.publisherSpecialCategoryHandling.categories",
            ))
        # SC-002
        if pdp is not True:
            diags.append(SmartDiagnostic(
                rule_id="SC-002",
                severity="error",
                message=(
                    "specialCategoryDataPresent is true but personalDataPresent is "
                    "false. Special category data is a subset of personal data under "
                    "GDPR Article 9 — personalDataPresent must also be true."
                ),
                field_path="rai.dataOrigin.personalDataPresent",
            ))
        # SC-003
        conditions = _ensure_dict(handling.get("conditions"))
        for cond_key, text_field in _SC_CONDITIONS:
            cond = _ensure_dict(conditions.get(cond_key))
            met = cond.get("met")
            text_value = cond.get(text_field)
            if met is False and not _is_truthy_str(text_value):
                diags.append(SmartDiagnostic(
                    rule_id="SC-003",
                    severity="warning",
                    message=(
                        f"Article 10(5) condition '{cond_key}' has not been "
                        "explicitly addressed (met is false with no explanation). "
                        "All six conditions must be actively assessed when special "
                        "category data is present."
                    ),
                    field_path=f"gov.publisherSpecialCategoryHandling.conditions.{cond_key}",
                ))

    # SC-004
    if categories and scdp is False:
        diags.append(SmartDiagnostic(
            rule_id="SC-004",
            severity="warning",
            message=(
                f"Special categories {categories} are listed but "
                "specialCategoryDataPresent is false. This is contradictory."
            ),
            field_path="gov.publisherSpecialCategoryHandling",
        ))

    return diags


# ---------------------------------------------------------------------------
# Category 4: Bias Examination Consistency (BX-001 .. BX-005)
# ---------------------------------------------------------------------------


def _check_bias_examination(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    entries = _bias_entries(card)

    # BX-001
    if entries and all(e.get("mitigationStatus") == "not-assessed" for _c, e in entries):
        diags.append(SmartDiagnostic(
            rule_id="BX-001",
            severity="warning",
            message=(
                f"All {len(entries)} documented biases have mitigationStatus "
                "'not-assessed'. Article 10(2)(g) requires measures to detect, "
                "prevent, and mitigate biases."
            ),
            field_path="rai.biasExamination",
        ))

    # BX-002
    for cat, e in entries:
        if e.get("severity") == "high":
            status = e.get("mitigationStatus")
            if status in (None, "", "not-assessed", "documented"):
                bias_label = e.get("bias", "<unnamed>")
                status_label = status if _is_truthy_str(status) else "not-assessed"
                diags.append(SmartDiagnostic(
                    rule_id="BX-002",
                    severity="warning",
                    message=(
                        f"Bias '{bias_label}' has high severity but "
                        f"mitigationStatus is '{status_label}'. High-severity biases "
                        "should have active mitigation measures."
                    ),
                    field_path=f"rai.biasExamination.{cat}",
                ))

    # BX-003 / BX-004 (discriminationBiases only)
    discrimination = _ensure_list(
        _get(card, "rai", "biasExamination", "discriminationBiases")
    )
    for entry in discrimination:
        if not isinstance(entry, dict):
            continue
        bias_label = entry.get("bias", "<unnamed>")
        if not _is_truthy_str(entry.get("protectedCharacteristic")):
            diags.append(SmartDiagnostic(
                rule_id="BX-003",
                severity="error",
                message=(
                    f"Discrimination bias entry '{bias_label}' has no "
                    "protectedCharacteristic. This field is required to link the "
                    "bias to a specific protected characteristic under equality law."
                ),
                field_path="rai.biasExamination.discriminationBiases",
            ))
        if not _is_truthy_str(entry.get("legalBasis")):
            diags.append(SmartDiagnostic(
                rule_id="BX-004",
                severity="warning",
                message=(
                    f"Discrimination bias entry '{bias_label}' has no legalBasis. "
                    "Specify the relevant equality legislation (e.g., Equality Act "
                    "2010, EU AI Act Art. 10(2)(f))."
                ),
                field_path="rai.biasExamination.discriminationBiases",
            ))

    # BX-005
    for cat, e in entries:
        if _is_truthy_str(e.get("detectionMethod")) and not _is_truthy_str(
            e.get("mitigationStatus")
        ):
            bias_label = e.get("bias", "<unnamed>")
            diags.append(SmartDiagnostic(
                rule_id="BX-005",
                severity="warning",
                message=(
                    f"Bias '{bias_label}' has a detection method documented but no "
                    "mitigation status. Set mitigationStatus to one of: mitigated, "
                    "partially-mitigated, documented, not-assessed."
                ),
                field_path=f"rai.biasExamination.{cat}",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 5: Access Policy Consistency (AP-001 .. AP-016)
# ---------------------------------------------------------------------------


def _check_access_policies(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    policies = _ensure_list(_get(card, "gov", "accessPolicies"))
    if not policies:
        return diags

    seen_ids: dict[str, int] = {}
    for policy in policies:
        if not isinstance(policy, dict):
            continue
        pid = policy.get("policyId", "<unnamed>")

        # Track for AP-015
        if isinstance(pid, str):
            seen_ids[pid] = seen_ids.get(pid, 0) + 1

        permitted = _ensure_list(policy.get("permittedPurposes"))
        prohibited = _ensure_list(policy.get("prohibitedPurposes"))

        # AP-001
        if not permitted:
            diags.append(SmartDiagnostic(
                rule_id="AP-001",
                severity="error",
                message=(
                    f"Access policy '{pid}' has no permitted purposes. A policy "
                    "must permit at least one purpose to be meaningful."
                ),
                field_path=f"gov.accessPolicies[{pid}].permittedPurposes",
            ))

        # AP-002
        for purpose in permitted:
            if purpose in prohibited:
                diags.append(SmartDiagnostic(
                    rule_id="AP-002",
                    severity="error",
                    message=(
                        f"Access policy '{pid}' has purpose '{purpose}' in both "
                        "permittedPurposes and prohibitedPurposes. This is "
                        "contradictory."
                    ),
                    field_path=f"gov.accessPolicies[{pid}]",
                ))

        # AP-003 / AP-004 / AP-005
        eff_from_raw = policy.get("effectiveFrom")
        eff_from = _parse_date(eff_from_raw)
        expires_raw = policy.get("expiresAt")
        expires = _parse_date(expires_raw)

        if not _is_truthy_str(eff_from_raw):
            diags.append(SmartDiagnostic(
                rule_id="AP-003",
                severity="warning",
                message=(
                    f"Access policy '{pid}' has no effectiveFrom date. Policies "
                    "should have an explicit effective date for auditability."
                ),
                field_path=f"gov.accessPolicies[{pid}].effectiveFrom",
            ))

        if eff_from and expires and eff_from > expires:
            diags.append(SmartDiagnostic(
                rule_id="AP-004",
                severity="error",
                message=(
                    f"Access policy '{pid}' has effectiveFrom ({eff_from.isoformat()}) "
                    f"after expiresAt ({expires.isoformat()}). The policy can never "
                    "be active."
                ),
                field_path=f"gov.accessPolicies[{pid}]",
            ))

        if expires and expires < _today():
            diags.append(SmartDiagnostic(
                rule_id="AP-005",
                severity="warning",
                message=(
                    f"Access policy '{pid}' expired on {expires.isoformat()}. "
                    "Remove or update the policy."
                ),
                field_path=f"gov.accessPolicies[{pid}].expiresAt",
            ))

        # Retention rules (AP-006 .. AP-008)
        retention = _ensure_dict(policy.get("retention"))
        max_days = retention.get("maxRetentionDays")
        deletion_method = retention.get("deletionMethod")

        if max_days == 0:
            diags.append(SmartDiagnostic(
                rule_id="AP-006",
                severity="warning",
                message=(
                    f"Access policy '{pid}' has retention set to 0 days. Is this "
                    "intentional (data must be deleted immediately after use) or "
                    "unfilled?"
                ),
                field_path=f"gov.accessPolicies[{pid}].retention.maxRetentionDays",
            ))

        if isinstance(max_days, (int, float)) and max_days > 3650:
            years = max_days / 365.0
            diags.append(SmartDiagnostic(
                rule_id="AP-007",
                severity="info",
                message=(
                    f"Access policy '{pid}' has retention of {int(max_days)} days "
                    f"({years:.1f} years). Verify this aligns with data minimisation "
                    "principles."
                ),
                field_path=f"gov.accessPolicies[{pid}].retention.maxRetentionDays",
            ))

        if (
            isinstance(max_days, (int, float))
            and max_days > 0
            and not _is_truthy_str(deletion_method)
        ):
            diags.append(SmartDiagnostic(
                rule_id="AP-008",
                severity="warning",
                message=(
                    f"Access policy '{pid}' specifies retention of {int(max_days)} "
                    "days but no deletion method. Specify how data will be deleted "
                    "(cryptographic-erasure, standard-deletion, or verified-deletion)."
                ),
                field_path=f"gov.accessPolicies[{pid}].retention.deletionMethod",
            ))

        # Redistribution (AP-009)
        redistribution = _ensure_dict(policy.get("redistribution"))
        if redistribution.get("derivativeWorksPermitted") is True and not _is_truthy_str(
            redistribution.get("derivativeWorkConditions")
        ):
            diags.append(SmartDiagnostic(
                rule_id="AP-009",
                severity="warning",
                message=(
                    f"Access policy '{pid}' permits derivative works but specifies "
                    "no conditions. Consider documenting requirements for "
                    "derivatives (e.g., attribution, de-identification, approval)."
                ),
                field_path=f"gov.accessPolicies[{pid}].redistribution.derivativeWorkConditions",
            ))

        # Audit (AP-010 / AP-011)
        audit = _ensure_dict(policy.get("auditRequirements"))
        if audit.get("auditRightGranted") is True:
            if not _is_truthy_str(audit.get("auditFrequency")):
                diags.append(SmartDiagnostic(
                    rule_id="AP-010",
                    severity="warning",
                    message=(
                        f"Access policy '{pid}' grants audit rights but specifies "
                        "no audit frequency."
                    ),
                    field_path=f"gov.accessPolicies[{pid}].auditRequirements.auditFrequency",
                ))
            if not _is_truthy_str(audit.get("auditScope")):
                diags.append(SmartDiagnostic(
                    rule_id="AP-011",
                    severity="warning",
                    message=(
                        f"Access policy '{pid}' grants audit rights but specifies "
                        "no audit scope."
                    ),
                    field_path=f"gov.accessPolicies[{pid}].auditRequirements.auditScope",
                ))

        # Scope (AP-012 / AP-013)
        scope = _ensure_dict(policy.get("accessScope"))
        scope_type = scope.get("scopeType")
        if scope_type == "partial" and not _ensure_list(scope.get("includedRecordSets")):
            diags.append(SmartDiagnostic(
                rule_id="AP-012",
                severity="warning",
                message=(
                    f"Access policy '{pid}' has scope type 'partial' but no "
                    "includedRecordSets are specified. Which record sets are included?"
                ),
                field_path=f"gov.accessPolicies[{pid}].accessScope.includedRecordSets",
            ))
        if scope_type == "sample":
            sample_limit = scope.get("sampleLimit")
            if sample_limit in (None, 0):
                diags.append(SmartDiagnostic(
                    rule_id="AP-013",
                    severity="warning",
                    message=(
                        f"Access policy '{pid}' has scope type 'sample' but no "
                        "sampleLimit. How many records can a consumer access?"
                    ),
                    field_path=f"gov.accessPolicies[{pid}].accessScope.sampleLimit",
                ))

        # Eligibility (AP-014)
        eligibility = _ensure_dict(policy.get("eligibility"))
        consumer_type = _ensure_list(eligibility.get("consumerType"))
        consumer_entity = eligibility.get("consumerEntity")
        consumer_entity_present = (
            isinstance(consumer_entity, str) and consumer_entity.strip()
            or (isinstance(consumer_entity, list) and len(consumer_entity) > 0)
            or (isinstance(consumer_entity, dict) and len(consumer_entity) > 0)
        )
        if not consumer_type and not consumer_entity_present:
            diags.append(SmartDiagnostic(
                rule_id="AP-014",
                severity="warning",
                message=(
                    f"Access policy '{pid}' has no eligibility criteria. Who is "
                    "this policy for?"
                ),
                field_path=f"gov.accessPolicies[{pid}].eligibility",
            ))

        # AP-016
        advisory = policy.get("highRiskDomainAdvisory")
        if not _is_truthy_str(advisory):
            for purpose in permitted:
                domain = _HIGH_RISK_PURPOSE_DOMAIN.get(purpose)
                if domain:
                    diags.append(SmartDiagnostic(
                        rule_id="AP-016",
                        severity="warning",
                        message=(
                            f"Access policy '{pid}' permits '{purpose}' which is "
                            f"associated with EU AI Act Annex III high-risk domain "
                            f"'{domain}', but highRiskDomainAdvisory is empty. "
                            "Consumers need to know about high-risk classification "
                            "implications."
                        ),
                        field_path=f"gov.accessPolicies[{pid}].highRiskDomainAdvisory",
                    ))

    # AP-015 — duplicates
    for pid, count in seen_ids.items():
        if count > 1:
            diags.append(SmartDiagnostic(
                rule_id="AP-015",
                severity="error",
                message=(
                    f"Duplicate policyId '{pid}' — policy IDs must be unique."
                ),
                field_path="gov.accessPolicies",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 6: Compliance Gap Consistency (CG-001 .. CG-003)
# ---------------------------------------------------------------------------


def _check_compliance_gaps(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    gaps = _ensure_list(_get(card, "rai", "complianceGaps"))
    today = _today()

    for entry in gaps:
        if not isinstance(entry, dict):
            continue
        gap_label = entry.get("gap", "<unnamed>")
        timeline = _parse_date(entry.get("remediationTimeline"))
        if timeline and timeline < today:
            diags.append(SmartDiagnostic(
                rule_id="CG-001",
                severity="warning",
                message=(
                    f"Compliance gap '{gap_label}' has remediation deadline "
                    f"{timeline.isoformat()} which has passed. Update the timeline "
                    "or document that remediation is complete."
                ),
                field_path="rai.complianceGaps",
            ))
        if entry.get("severity") == "high" and not _is_truthy_str(entry.get("remediationPlan")):
            diags.append(SmartDiagnostic(
                rule_id="CG-002",
                severity="warning",
                message=(
                    f"Compliance gap '{gap_label}' has high severity but no "
                    "remediation plan."
                ),
                field_path="rai.complianceGaps",
            ))

    # CG-003
    known_gaps_text = _get(
        card, "rai", "dataQualityAssessment", "representativeness", "knownGaps"
    )
    if isinstance(known_gaps_text, str) and known_gaps_text.strip():
        kg_words = {
            w.strip().lower()
            for w in re.findall(r"[A-Za-z]{4,}", known_gaps_text)
        }
        gap_texts = []
        for entry in gaps:
            if isinstance(entry, dict):
                v = entry.get("gap")
                if isinstance(v, str):
                    gap_texts.append(v.lower())
        overlap = any(any(w in t for w in kg_words) for t in gap_texts)
        if kg_words and not overlap:
            diags.append(SmartDiagnostic(
                rule_id="CG-003",
                severity="info",
                message=(
                    "Representativeness has known gaps but no corresponding "
                    "compliance gap entry. If these gaps affect Article 10(3) "
                    "compliance, document them as compliance gaps."
                ),
                field_path="rai.complianceGaps",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 7: Temporal and Date Consistency (DT-001 .. DT-004)
# ---------------------------------------------------------------------------


def _check_temporal(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    today = _today()

    pub = _parse_date(card.get("datePublished"))
    if pub and pub > today:
        diags.append(SmartDiagnostic(
            rule_id="DT-001",
            severity="info",
            message=f"datePublished is {pub.isoformat()}, which is in the future.",
            field_path="datePublished",
        ))

    review = _parse_date(_get(card, "gov", "lastGovernanceReview"))
    if review:
        if review < today - datetime.timedelta(days=365):
            delta_days = (today - review).days
            months = delta_days // 30
            diags.append(SmartDiagnostic(
                rule_id="DT-002",
                severity="warning",
                message=(
                    f"Last governance review was {review.isoformat()} ({months} "
                    "months ago). Consider scheduling a review — governance "
                    "documentation should be reviewed periodically."
                ),
                field_path="gov.lastGovernanceReview",
            ))
        if review > today:
            diags.append(SmartDiagnostic(
                rule_id="DT-003",
                severity="warning",
                message=(
                    f"lastGovernanceReview is {review.isoformat()}, which is in "
                    "the future."
                ),
                field_path="gov.lastGovernanceReview",
            ))

    sources = _ensure_list(_get(card, "rai", "dataOrigin", "sources"))
    for src in sources:
        if not isinstance(src, dict):
            continue
        ext_date = _parse_date(src.get("extractionDate"))
        if ext_date and ext_date > today:
            name = src.get("name", "<unnamed>")
            diags.append(SmartDiagnostic(
                rule_id="DT-004",
                severity="warning",
                message=(
                    f"Source '{name}' has extractionDate {ext_date.isoformat()} "
                    "which is in the future."
                ),
                field_path="rai.dataOrigin.sources",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 8: Version Format (VF-001 .. VF-003)
# ---------------------------------------------------------------------------


def _check_version_format(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []

    version = card.get("version")
    if _is_truthy_str(version) and not _is_semver(version):
        diags.append(SmartDiagnostic(
            rule_id="VF-001",
            severity="warning",
            message=(
                f"Dataset version '{version}' does not follow semantic "
                "versioning (X.Y.Z). Semver is recommended for interoperability."
            ),
            field_path="version",
        ))

    gov_version = _get(card, "gov", "governanceVersion")
    if _is_truthy_str(gov_version) and not _is_semver(gov_version):
        diags.append(SmartDiagnostic(
            rule_id="VF-002",
            severity="warning",
            message=(
                f"Governance version '{gov_version}' does not follow semantic "
                "versioning."
            ),
            field_path="gov.governanceVersion",
        ))

    for policy in _ensure_list(_get(card, "gov", "accessPolicies")):
        if not isinstance(policy, dict):
            continue
        pv = policy.get("policyVersion")
        pid = policy.get("policyId", "<unnamed>")
        if _is_truthy_str(pv) and not _is_semver(pv):
            diags.append(SmartDiagnostic(
                rule_id="VF-003",
                severity="warning",
                message=(
                    f"Policy '{pid}' version '{pv}' does not follow semantic "
                    "versioning."
                ),
                field_path=f"gov.accessPolicies[{pid}].policyVersion",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 9: License-Governance Relationship (LG-001 .. LG-002)
# ---------------------------------------------------------------------------


def _check_license_governance(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    relationship = _get(card, "gov", "licenseGovernanceRelationship", "relationship")
    policies = _ensure_list(_get(card, "gov", "accessPolicies"))

    if relationship == "license-only" and policies:
        diags.append(SmartDiagnostic(
            rule_id="LG-001",
            severity="warning",
            message=(
                "License-governance relationship is 'license-only' but access "
                "policies are defined. If governance policies control access, "
                "the relationship should be 'governance-supersedes' or "
                "'complementary'."
            ),
            field_path="gov.licenseGovernanceRelationship",
        ))

    if relationship == "governance-supersedes" and not policies:
        diags.append(SmartDiagnostic(
            rule_id="LG-002",
            severity="warning",
            message=(
                "License-governance relationship is 'governance-supersedes' but "
                "no access policies are defined. Define access policies or "
                "change the relationship."
            ),
            field_path="gov.accessPolicies",
        ))

    return diags


# ---------------------------------------------------------------------------
# Category 10: Classification & Governance Model (GM-001 .. GM-003)
# ---------------------------------------------------------------------------


def _check_governance_model(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    classification = _get(card, "gov", "dataClassification")
    model = _get(card, "gov", "governanceModel")

    if classification in ("secret", "top-secret") and model == "open":
        diags.append(SmartDiagnostic(
            rule_id="GM-001",
            severity="error",
            message=(
                f"Data classification is '{classification}' but governance model "
                "is 'open'. Classified data cannot be openly accessible. Use "
                "'controlled' or 'restricted'."
            ),
            field_path="gov.governanceModel",
        ))

    if classification == "official-sensitive" and model == "open":
        diags.append(SmartDiagnostic(
            rule_id="GM-002",
            severity="warning",
            message=(
                "Data classification is 'official-sensitive' but governance "
                "model is 'open'. OFFICIAL-SENSITIVE information is not intended "
                "for public release — consider 'controlled' governance."
            ),
            field_path="gov.governanceModel",
        ))

    if model in ("controlled", "restricted"):
        controller_name = _get(card, "gov", "dataController", "name")
        if not _is_truthy_str(controller_name):
            diags.append(SmartDiagnostic(
                rule_id="GM-003",
                severity="warning",
                message=(
                    f"Governance model is '{model}' but no data controller is "
                    "specified. Controlled and restricted datasets must have an "
                    "identified data controller."
                ),
                field_path="gov.dataController.name",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 11: Derived Dataset Consistency (DD-001 .. DD-002)
# ---------------------------------------------------------------------------


def _check_derived(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    derived = _ensure_list(_get(card, "gov", "derivedFrom"))

    for entry in derived:
        if not isinstance(entry, dict):
            continue
        source_label = entry.get("source") or entry.get("name") or entry.get("datasetId") or "<unnamed>"
        constraints = entry.get("inheritedConstraints")

        if not constraints:  # empty list, None, or missing
            diags.append(SmartDiagnostic(
                rule_id="DD-001",
                severity="warning",
                message=(
                    f"Dataset is derived from '{source_label}' but no inherited "
                    "constraints are documented. Even if no constraints carry "
                    "forward, this should be explicitly stated."
                ),
                field_path="gov.derivedFrom",
            ))
            continue

        if isinstance(constraints, list):
            for c in constraints:
                if not isinstance(c, dict):
                    continue
                if c.get("inherited") is True and not _is_truthy_str(c.get("howAddressed")):
                    constraint_label = c.get("constraint") or c.get("name") or "<unnamed>"
                    diags.append(SmartDiagnostic(
                        rule_id="DD-002",
                        severity="warning",
                        message=(
                            f"Inherited constraint '{constraint_label}' from "
                            f"'{source_label}' is marked as inherited but "
                            "howAddressed is empty. Document how this constraint "
                            "is handled in the derived dataset."
                        ),
                        field_path="gov.derivedFrom",
                    ))

    return diags


# ---------------------------------------------------------------------------
# Category 12: Data Preparation Consistency (DP-001 .. DP-005)
# ---------------------------------------------------------------------------


def _check_data_preparation(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    prep = _ensure_dict(_get(card, "rai", "dataPreparation"))

    annotation = _ensure_dict(prep.get("annotation"))
    if annotation.get("performed") is True:
        annotator_count = annotation.get("annotatorCount", 0) or 0
        if annotator_count == 0:
            diags.append(SmartDiagnostic(
                rule_id="DP-001",
                severity="warning",
                message="Annotation is marked as performed but annotatorCount is 0.",
                field_path="rai.dataPreparation.annotation.annotatorCount",
            ))
        if isinstance(annotator_count, (int, float)) and annotator_count > 1:
            iaa = _ensure_dict(annotation.get("interAnnotatorAgreement"))
            if not _is_truthy_str(iaa.get("metric")):
                diags.append(SmartDiagnostic(
                    rule_id="DP-002",
                    severity="warning",
                    message=(
                        f"Annotation was performed by {int(annotator_count)} "
                        "annotators but no inter-annotator agreement metric is "
                        "reported. Document agreement to evidence annotation quality."
                    ),
                    field_path="rai.dataPreparation.annotation.interAnnotatorAgreement",
                ))

    aggregation = _ensure_dict(prep.get("aggregation"))
    if aggregation.get("performed") is True:
        source_count = aggregation.get("sourceCount", 0) or 0
        if source_count == 0:
            diags.append(SmartDiagnostic(
                rule_id="DP-003",
                severity="warning",
                message="Aggregation is marked as performed but sourceCount is 0.",
                field_path="rai.dataPreparation.aggregation.sourceCount",
            ))

    enrichment = _ensure_dict(prep.get("enrichment"))
    if enrichment.get("performed") is True and not _is_truthy_str(
        enrichment.get("enrichmentSource")
    ):
        diags.append(SmartDiagnostic(
            rule_id="DP-004",
            severity="warning",
            message=(
                "Enrichment is marked as performed but enrichmentSource is not "
                "specified. Document where the enrichment data came from."
            ),
            field_path="rai.dataPreparation.enrichment.enrichmentSource",
        ))

    cleaning = _ensure_dict(prep.get("cleaning"))
    if cleaning.get("performed") is True:
        removed_count = cleaning.get("recordsRemovedCount", 0) or 0
        removed_pct = cleaning.get("recordsRemovedPercentage", 0) or 0
        if removed_count == 0 and removed_pct == 0:
            diags.append(SmartDiagnostic(
                rule_id="DP-005",
                severity="info",
                message=(
                    "Cleaning is marked as performed but no records were removed "
                    "(count and percentage both 0). If cleaning involved "
                    "transformations without removal, consider documenting this "
                    "in the description."
                ),
                field_path="rai.dataPreparation.cleaning",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 13: Funding and Impact (FI-001 .. FI-002)
# ---------------------------------------------------------------------------


def _check_funding_impact(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    funding = _ensure_dict(_get(card, "gov", "fundingSource"))
    funder = funding.get("funderName")
    impact = _ensure_dict(_get(card, "gov", "impactReporting"))
    metrics = _ensure_list(impact.get("metricsRequired"))
    frequency = impact.get("reportingFrequency")

    if _is_truthy_str(funder) and not metrics and not _is_truthy_str(frequency):
        diags.append(SmartDiagnostic(
            rule_id="FI-001",
            severity="info",
            message=(
                f"Dataset has a funding source ({funder}) but no impact reporting "
                "is configured. Most funders require usage metrics — verify "
                "whether reporting is needed."
            ),
            field_path="gov.impactReporting",
        ))

    if funding.get("fundingTrack") == "commercial":
        any_product = False
        for policy in _ensure_list(_get(card, "gov", "accessPolicies")):
            if isinstance(policy, dict):
                if "product-development" in _ensure_list(policy.get("permittedPurposes")):
                    any_product = True
                    break
        if not any_product:
            diags.append(SmartDiagnostic(
                rule_id="FI-002",
                severity="info",
                message=(
                    "Funding track is 'commercial' but no access policy permits "
                    "'product-development'. Verify this is intentional."
                ),
                field_path="gov.fundingSource.fundingTrack",
            ))

    return diags


# ---------------------------------------------------------------------------
# Category 14: Data Controller (DC-001)
# ---------------------------------------------------------------------------


def _check_data_controller(card: dict[str, Any]) -> list[SmartDiagnostic]:
    diags: list[SmartDiagnostic] = []
    contact = _get(card, "gov", "dataController", "contactEmail")
    if isinstance(contact, str) and "todo" in contact.lower():
        diags.append(SmartDiagnostic(
            rule_id="DC-001",
            severity="warning",
            message=(
                "Data controller contact email still contains 'TODO'. Update with "
                "a real contact address before publishing."
            ),
            field_path="gov.dataController.contactEmail",
        ))
    return diags


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_CATEGORY_CHECKS = (
    _check_dataset_aware,
    _check_personal_data,
    _check_special_category,
    _check_bias_examination,
    _check_access_policies,
    _check_compliance_gaps,
    _check_temporal,
    _check_version_format,
    _check_license_governance,
    _check_governance_model,
    _check_derived,
    _check_data_preparation,
    _check_funding_impact,
    _check_data_controller,
)


def run_all_rules(card: dict[str, Any]) -> list[SmartDiagnostic]:
    """Run every smart rule against the card.

    Robust to missing sections — if `rai`, `gov`, or any nested structure is
    absent, the affected rules simply produce no diagnostics rather than
    raising. Returns a flat list ordered by category.
    """
    if not isinstance(card, dict):
        return []
    out: list[SmartDiagnostic] = []
    for fn in _CATEGORY_CHECKS:
        try:
            out.extend(fn(card))
        except Exception:  # pragma: no cover - defensive: rules must never crash
            continue
    return out
