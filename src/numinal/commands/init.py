"""numinal init — generate a new data card from a dataset directory.

Implements spec §11.2 and §11.5:
  - Auto-detects file types, sizes, checksums (§11.5)
  - Detects existing metadata (README, LICENSE, Croissant, HF cards)
  - Prompts for required T1 fields
  - Scaffolds T2/T3 sections with TODO markers
  - Outputs numinal.yaml as the human-authored source of truth (§2.2)
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

import click
import yaml

from numinal.detection.auto import detect, DetectionResult
from numinal.detection.croissant import extract_bootstrap, load_croissant
from numinal.schema.vocabularies import (
    DATA_CLASSIFICATIONS,
    GOVERNANCE_MODELS,
)


def _prompt_required(prompt_text: str, default: str | None = None) -> str:
    """Prompt for a required value."""
    while True:
        value = click.prompt(prompt_text, default=default or "", show_default=bool(default))
        if value.strip():
            return value.strip()
        click.echo("  This field is required.")


def _prompt_choice(prompt_text: str, choices: list[str], default: str | None = None) -> str:
    """Prompt with constrained choices."""
    choice_str = " / ".join(choices)
    while True:
        value = click.prompt(f"{prompt_text} [{choice_str}]", default=default or "")
        if value.strip() in choices:
            return value.strip()
        click.echo(f"  Must be one of: {choice_str}")


def _build_distribution(detection: DetectionResult) -> list[dict[str, Any]]:
    """Build distribution entries from detected files."""
    distributions: list[dict[str, Any]] = []

    # Group by extension
    for ext, count in sorted(detection.file_type_counts.items()):
        total_size = sum(f.size_bytes for f in detection.files if f.extension == ext)
        distributions.append({
            "name": f"{ext.lstrip('.')} files" if ext else "other files",
            "contentType": _mime_for_ext(ext),
            "fileCount": count,
            "totalSizeBytes": total_size,
        })

    return distributions


def _mime_for_ext(ext: str) -> str:
    """Map file extension to MIME type."""
    return {
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
    }.get(ext, "application/octet-stream")


def _build_rai_scaffold() -> dict[str, Any]:
    """Build RAI section scaffold with TODO markers for T2 fields."""
    return {
        "designChoices": {
            "designObjective": "TODO: What was the dataset designed to achieve?",
            "populationScope": "TODO: What populations/phenomena does it represent?",
            "inclusionCriteria": "TODO: What was included and why?",
            "exclusionCriteria": "TODO: What was excluded and why?",
            "exclusionRationale": "TODO: Why were exclusions necessary?",
            "featureSelectionRationale": "TODO: Why were these features chosen?",
            "tradeoffs": [],
        },
        "dataCollection": "TODO: How was data gathered?",
        "dataOrigin": {
            "sources": [],
            "originalCollectionPurpose": "TODO: What were data subjects told? (if personal data)",
            "consentBasis": "TODO: Legal basis for original collection",
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
        "measurementAssumptions": [],
        "suitabilityAssessment": {
            "quantityAssessment": "TODO: Is there enough data? Evidence?",
            "availabilityAssessment": "TODO: Was needed data available?",
            "suitabilityAssessment": "TODO: Is the data appropriate for the intended purpose?",
            "additionalDataNeeded": "TODO: What additional data would improve the dataset?",
        },
        "biasExamination": {
            "healthSafetyBiases": [],
            "fundamentalRightsBiases": [],
            "discriminationBiases": [],
            "feedbackLoopRisks": [],
        },
        "complianceGaps": [],
        "dataQualityAssessment": {
            "relevance": {"assessment": "TODO", "evidenceBasis": "TODO"},
            "representativeness": {"assessment": "TODO", "comparisonBasis": "TODO", "knownGaps": ""},
            "errorRate": {"assessment": "TODO", "auditMethodology": "TODO", "errorTypes": ""},
            "completeness": {"assessment": "TODO", "missingDataByField": {}, "missingDataStrategy": ""},
            "statisticalProperties": "",
            "combinedDatasetNote": "",
        },
        "geographicContext": {
            "dataOriginCountries": [],
            "dataOriginRegions": [],
            "intendedDeploymentContext": "TODO",
            "contextualAlignment": "TODO",
            "knownContextualLimitations": "",
        },
        "contextualCharacteristics": {
            "languageCharacteristics": "",
            "culturalConsiderations": "",
            "temporalCoverage": "",
            "functionalContext": "",
        },
        "additionalGovernancePractices": "",
    }


def _build_gov_scaffold() -> dict[str, Any]:
    """Build GOV section scaffold with TODO markers for T3 fields."""
    return {
        "accessPolicies": [
            {
                "policyId": "TODO-policy-1",
                "policyVersion": "0.1.0",
                "description": "TODO: describe this access policy",
                "eligibility": {
                    "consumerType": [],
                    "jurisdictions": [],
                    "requiredCertifications": [],
                    "requiredApprovals": [],
                    "excludedEntities": [],
                },
                "permittedPurposes": [],
                "prohibitedPurposes": [],
                "purposeModifiers": [],
                "highRiskDomainAdvisory": "",
                "accessScope": {
                    "scopeType": "full",
                    "includedRecordSets": [],
                    "excludedFields": [],
                    "rowFilter": "",
                    "sampleLimit": None,
                    "accessMethod": "bulk-download",
                    "rateLimit": {"requestsPerDay": 0, "maxRecordsPerRequest": 0},
                },
                "retention": {
                    "maxRetentionDays": 0,
                    "retentionType": "fixed",
                    "deletionMethod": "standard-deletion",
                    "retentionExceptions": "",
                },
                "redistribution": {
                    "redistributionPermitted": False,
                    "derivativeWorksPermitted": False,
                    "derivativeWorkConditions": "",
                    "sharingWithSubprocessors": "prohibited",
                },
                "attribution": {
                    "attributionText": "",
                    "citationRequired": False,
                    "citationFormat": "",
                    "citation": "",
                },
                "auditRequirements": {
                    "auditRightGranted": False,
                    "auditFrequency": "",
                    "auditScope": "",
                },
                "prerequisites": [],
                "intendedDatasetRole": ["training", "validation", "testing"],
                "effectiveFrom": "",
                "expiresAt": None,
            }
        ],
        "derivedFrom": [],
        "licenseGovernanceRelationship": {
            "relationship": "TODO: license-only | governance-supersedes | complementary | license-with-conditions",
            "explanation": "TODO",
        },
        "publisherSpecialCategoryHandling": {
            "specialCategoryDataPresent": False,
            "categories": [],
            "processingPurpose": "",
            "processingJustification": "",
            "conditions": {
                "a_alternativeDataInsufficient": {"met": False, "evidence": ""},
                "b_technicalReuseLimitations": {"met": False, "measures": ""},
                "c_accessControlAndConfidentiality": {"met": False, "measures": ""},
                "d_noThirdPartyTransfer": {"met": False, "enforcement": ""},
                "e_deletionOnCompletion": {"met": False, "mechanism": "", "retentionPeriodDays": 0},
                "f_processingRecords": {"met": False, "ropaReference": "", "justificationDocumented": False},
            },
            "obligationNote": (
                "This section documents the dataset publisher's handling of special category "
                "data. Downstream consumers who are providers of high-risk AI systems have "
                "independent obligations under Article 10(5). This documentation supports "
                "but does not discharge those obligations."
            ),
        },
        "fundingSource": {
            "funderName": "",
            "programmeName": "",
            "grantReference": "",
            "fundingAmount": "",
            "fundingTrack": "",
            "reportingBody": "",
        },
        "impactReporting": {
            "metricsRequired": [],
            "reportingFrequency": "",
        },
    }


def _yaml_representer_str(dumper: yaml.Dumper, data: str) -> yaml.Node:
    """Use block scalar style for multiline strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _yaml_representer_none(dumper: yaml.Dumper, data: None) -> yaml.Node:
    """Represent None as null."""
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def run_init(
    directory: str,
    output: str = "numinal.yaml",
    tier: int = 1,
    non_interactive: bool = False,
    from_croissant: str | None = None,
) -> Path:
    """Run the init command.

    Args:
        directory: Path to dataset directory to scan
        output: Output filename (default: numinal.yaml)
        tier: Target tier to scaffold for (1, 2, or 3)
        non_interactive: Skip prompts and use defaults
        from_croissant: Optional path or URL to a Croissant JSON-LD document
            whose fields seed the card (overrides directory-derived defaults
            and pre-fills prompts in interactive mode).

    Returns:
        Path to the generated file
    """
    dataset_dir = Path(directory).resolve()
    output_path = dataset_dir / output

    bootstrap: dict[str, Any] = {}
    if from_croissant:
        click.echo(f"\nLoading Croissant from {from_croissant} ...")
        bootstrap = extract_bootstrap(load_croissant(from_croissant))
        supplied = sorted(bootstrap.keys())
        if supplied:
            click.echo(f"  Bootstrapped: {', '.join(supplied)}")

    click.echo(f"\nScanning {dataset_dir} ...")
    detection = detect(dataset_dir)

    click.echo(f"  Found {len(detection.files)} files ({_human_size(detection.total_size_bytes)})")
    if detection.file_type_counts:
        for ext, count in sorted(detection.file_type_counts.items()):
            click.echo(f"    {ext or '(no ext)'}: {count}")
    if detection.existing_metadata:
        for meta_type, meta_path in detection.existing_metadata.items():
            click.echo(f"  Found existing {meta_type}: {Path(meta_path).name}")

    # Check for existing numinal.yaml
    if "numinal" in detection.existing_metadata:
        if not click.confirm(f"\n  numinal.yaml already exists. Overwrite?", default=False):
            click.echo("  Aborted.")
            raise SystemExit(0)

    click.echo()

    # Collect required T1 fields. Croissant bootstrap values take precedence
    # over generic defaults; in interactive mode they pre-fill the prompts.
    name_default = bootstrap.get("name") or dataset_dir.name
    description_default = bootstrap.get("description") or "TODO: describe this dataset"
    version_default = bootstrap.get("version") or "0.1.0"
    license_default = bootstrap.get("license") or "TODO: specify license (e.g., CC-BY-4.0, Apache-2.0)"
    creator_default = bootstrap.get("creator") or "TODO: creator name"
    date_published = bootstrap.get("datePublished") or datetime.date.today().isoformat()

    if non_interactive:
        name = name_default
        description = description_default
        version = version_default
        license_val = license_default
        creator = creator_default
        gov_model = "open"
        data_class = "unclassified"
    else:
        click.echo("── Tier 1 (discovery) required fields ──\n")
        name = _prompt_required("Dataset name", default=name_default)
        description = _prompt_required("Description", default=bootstrap.get("description"))
        version = _prompt_required("Version", default=version_default)
        license_val = _prompt_required(
            "License (e.g., CC-BY-4.0, Apache-2.0, OGL-UK-3.0)",
            default=bootstrap.get("license"),
        )
        creator = _prompt_required(
            "Creator (organisation or person name)",
            default=bootstrap.get("creator"),
        )
        gov_model = _prompt_choice("Governance model", sorted(GOVERNANCE_MODELS), default="open")
        data_class = _prompt_choice("Data classification",
                                     sorted(DATA_CLASSIFICATIONS), default="unclassified")

    # Build the card
    card: dict[str, Any] = {
        "_spec": "numinal-datacard-v1.0-rc1",
        "_generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "name": name,
        "description": description,
        "version": version,
        "license": license_val,
        "creator": creator,
        "datePublished": date_published,
        "distribution": bootstrap.get("distribution") or _build_distribution(detection),
    }

    # Add file manifest
    card["_fileManifest"] = [
        {
            "path": f.relative_path,
            "sizeBytes": f.size_bytes,
            "sha256": f.sha256,
        }
        for f in detection.files
    ]

    # Gov section (always included — governanceModel and governanceVersion are T1 required)
    card["gov"] = {
        "governanceModel": gov_model,
        "governanceVersion": "0.1.0",
        "dataClassification": data_class,
        "dataController": {
            "name": creator,
            "contactEmail": "TODO",
            "url": "",
        },
        "legalBasis": "",
        "regulatoryAlignment": [],
        "lastGovernanceReview": "",
    }

    # Scaffold higher tiers if requested. A Croissant-supplied recordSet wins
    # over the empty scaffold even at T1, since it's structured publisher data.
    if "recordSet" in bootstrap:
        card["recordSet"] = bootstrap["recordSet"]
    elif tier >= 2:
        card["recordSet"] = []

    if tier >= 2:
        card["rai"] = _build_rai_scaffold()

    if tier >= 3:
        card["gov"].update(_build_gov_scaffold())

    # Write YAML
    dumper = yaml.Dumper
    dumper.add_representer(str, _yaml_representer_str)
    dumper.add_representer(type(None), _yaml_representer_none)

    yaml_str = yaml.dump(
        card,
        Dumper=dumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )

    output_path.write_text(yaml_str, encoding="utf-8")
    click.echo(f"\n✓ Data card written to {output_path}")
    click.echo(f"  Target tier: T{tier} ({['', 'discovery', 'regulatory', 'governed sharing'][tier]})")
    click.echo(f"  Run `numinal validate {output_path}` to check completeness.\n")

    return output_path


def _human_size(nbytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"
