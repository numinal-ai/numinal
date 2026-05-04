# numinal

**Governance-as-code data cards for multi-party AI dataset sharing.**

numinal generates structured, machine-readable metadata for AI datasets — covering provenance, bias analysis, access policies, and EU AI Act Article 10 compliance. Built on [Croissant](https://mlcommons.org/croissant/) (MLCommons) with a governance extension layer.

## Why

If you're publishing a shared AI dataset — especially under a UK Sovereign AI grant, an UKRI programme, or any cross-organisational data sharing initiative — you need to document:

- What the dataset contains (structure, provenance, collection methodology)
- What biases exist and how they've been addressed
- Who can access it, for what purposes, under what constraints
- How it maps to EU AI Act Article 10 requirements

No existing tool produces this documentation in a machine-readable format. numinal does.

## Install

```bash
pip install numinal
```

## Quick start

```bash
# Generate a data card from your dataset directory
numinal init ./my-dataset/ --tier 2

# Validate against compliance tiers
numinal validate ./my-dataset/numinal.yaml

# Check EU AI Act Article 10 compliance
numinal compliance ./my-dataset/numinal.yaml --regulation eu-ai-act-art-10

# Render as markdown for documentation
numinal render ./my-dataset/numinal.yaml -o datacard.md
```

## What it looks like

### Validation

```
$ numinal validate ./numinal.yaml

Tier 1 (discovery):           ✓ PASS — 8/8 required fields
Tier 2 (regulatory):          ✗ FAIL — 9/14 required fields
  Missing:
  - rai:measurementAssumptions (Art. 10(2)(d))
  - rai:suitabilityAssessment (Art. 10(2)(e))
  - rai:complianceGaps (Art. 10(2)(h))
  - rai:dataQualityAssessment (Art. 10(3))
  - rai:geographicContext (Art. 10(4))
Tier 3 (governed sharing):    ✗ FAIL — 14/23 required fields

Completeness: 67% (35/52 total fields)
```

### Article 10 compliance

```
$ numinal compliance ./numinal.yaml --regulation eu-ai-act-art-10

EU AI Act Article 10 — 13 sub-requirements checked:

  ✓ 10(2)(a) Design choices
  ✓ 10(2)(b) Collection processes and origin
  ✓ 10(2)(b)+ Original collection purpose disclosure
  ✓ 10(2)(c) Data preparation operations
  ✗ 10(2)(d) Measurement assumptions — rai.measurementAssumptions missing
  ✓ 10(2)(e) Suitability assessment
  ✓ 10(2)(f) Bias examination
  ✓ 10(2)(g) Bias mitigation measures
  ✗ 10(2)(h) Compliance gaps identified — rai.complianceGaps missing
  ✓ 10(3) Data quality criteria
  ✓ 10(4) Geographic and contextual characteristics
  — 10(5) Special category data safeguards (skipped: not applicable)
  ✓ 10(6) Dataset role distinction

Score: 10/11 requirements met
```

## Compliance tiers

| Tier | Name | Purpose | Who needs it |
|------|------|---------|-------------|
| T1 | **Discovery** | Dataset is findable, understandable, usable | Any dataset publisher |
| T2 | **Regulatory** | Supports EU AI Act Article 10 compliance | Publishers whose data may be used in high-risk AI |
| T3 | **Governed sharing** | Full multi-party access control with audit trail | Cross-organisational dataset sharing |

T3 ⊇ T2 ⊇ T1. Start at T1, add fields as you need them.

## How it works

`numinal init` scans your dataset directory and auto-detects:
- File types, sizes, SHA-256 checksums
- Column names, data types, null rates, cardinality (CSV/TSV)
- Existing README, LICENSE, Croissant metadata

It generates a `numinal.yaml` — the human-authored source of truth — with TODO markers for fields you need to fill in manually. Run `numinal validate` to see what's missing at each tier.

## Schema

The numinal data card extends Croissant with two additional layers:

| Layer | Standard | What it covers |
|-------|----------|----------------|
| Dataset structure | Croissant 1.0 (MLCommons) | Files, schemas, splits, ML semantics |
| Responsible AI | Croissant-RAI 1.0 (MLCommons) | Bias, fairness, collection methodology |
| **Governance** | **Croissant-GOV 0.1 (numinal)** | Access policies, DUAs, compliance, metering |

Every numinal data card is simultaneously valid Croissant metadata. The governance fields live in their own namespace — tools that don't understand `gov:` fields simply ignore them.

Controlled vocabularies are sourced from:
- **Organisation types:** UK Cabinet Office Public Bodies Handbook, Companies House
- **Data use purposes:** GA4GH Data Use Ontology (DUO), extended with AI-specific terms
- **High-risk domains:** EU AI Act Annex III
- **Security classifications:** UK Government Security Classifications Policy (GSCP)
- **Policy expression:** W3C ODRL 2.2 via DPV-ODRL profile

See the [specification](numinal-datacard-spec-v1-rc1.md) for full details.

## Example

See [`examples/uk-health-ai-corpus.yaml`](examples/uk-health-ai-corpus.yaml) for a complete T3 data card demonstrating all three schema layers.

## Commands

| Command | Status | Purpose |
|---------|--------|---------|
| `numinal init` | ✓ | Generate a data card from a dataset directory |
| `numinal validate` | ✓ | Validate against compliance tiers |
| `numinal compliance` | ✓ | Check against EU AI Act Article 10 |
| `numinal render` | ✓ | Render as markdown |
| `numinal diff` | planned | Compare two data card versions |

## License

Apache-2.0
