# numinal data card specification

**Version:** 1.0-rc1 (release candidate)
**Date:** 2026-05-04
**Status:** Pre-implementation review

---

## 1. Purpose

This document specifies the numinal data card — a machine-readable metadata format for governed, multi-party AI dataset sharing. A numinal data card describes not only what a dataset *contains* (structure, provenance, bias characteristics) but also *who may access it, under what terms, for what purposes, and with what constraints*.

The specification extends the Croissant metadata format (MLCommons) with a governance layer (`Croissant-GOV`) that adds access control policies, data use agreements, compliance evidence, and impact reporting. Every numinal data card is simultaneously valid Croissant metadata.

---

## 2. Design philosophy

### 2.1 Compose existing standards

| Layer | Standard | Maintainer | What it covers |
|-------|----------|-----------|----------------|
| Dataset structure | Croissant 1.0 | MLCommons | Files, schemas, splits, ML semantics |
| Responsible AI | Croissant-RAI 1.0 | MLCommons | Bias, fairness, collection methodology |
| Governance & access | **Croissant-GOV 0.1** | **numinal** | Access policies, DUAs, compliance, metering |
| Policy expression | W3C ODRL 2.2 (via DPV-ODRL profile) | W3C Community Group | Permissions, prohibitions, duties |

### 2.2 Two representations

- **`numinal.yaml`** — human-authored source of truth, version-controlled alongside the dataset
- **`datacard.json`** — CLI-generated JSON-LD output conforming to Croissant 1.0 with RAI and GOV extensions

### 2.3 Vocabulary rules

1. Every enumerated term cites its authoritative source
2. Vocabularies are extensible via `custom:` prefix — core terms are canonical, custom terms produce validation warnings
3. Align with existing standards before inventing terms

### 2.4 Three compliance tiers

| Tier | Name | Purpose | Who needs it |
|------|------|---------|-------------|
| T1 | **Discovery** | Dataset is findable, understandable, usable | Any dataset publisher |
| T2 | **Regulatory** | Downstream consumer can satisfy EU AI Act Art. 10 | Publishers whose data may be used in high-risk AI |
| T3 | **Governed sharing** | Full multi-party access control with audit trail | Any cross-organisational dataset sharing |

T3 is a superset of T2, which is a superset of T1.

---

## 3. Controlled vocabularies

### 3.1 Organisation types (`gov:consumerType`)

#### UK public sector

**Source:** UK Cabinet Office Public Bodies Handbook Part 1: "Classification of Public Bodies: Guidance for Departments" (originally April 2016, periodically updated); GOV.UK public bodies guidance (https://www.gov.uk/guidance/public-bodies-reform). Chapter and section references verified against the full handbook document.

| Term | Definition | Source reference |
|------|-----------|----------------|
| `uk-ministerial-dept` | Ministerial department (e.g., DSIT, DHSC) | GOV.UK departments list (https://www.gov.uk/government/organisations). Not in Public Bodies Handbook — ministerial departments are not ALBs. |
| `uk-non-ministerial-dept` | Non-ministerial department (e.g., HMRC, Ofgem, Food Standards Agency) | Public Bodies Handbook, Ch. 2 §2.4 |
| `uk-executive-agency` | Executive agency of a department (e.g., DVLA, Met Office) | Public Bodies Handbook, Ch. 2 §2.2 |
| `uk-executive-ndpb` | Executive non-departmental public body (e.g., UKRI, NHS England, Environment Agency) | Public Bodies Handbook, Ch. 2 §2.3 |
| `uk-advisory-ndpb` | Advisory NDPB | Public Bodies Handbook, Ch. 2 §2.3.1 |
| `uk-public-corporation` | Public corporation (e.g., BBC, Ordnance Survey, Channel 4) | Public Bodies Handbook, Ch. 6; ONS Sector Classification Guide |
| `uk-nhs-trust` | NHS trust or NHS foundation trust | Public Bodies Handbook, Ch. 3 §3.6.1 (Special Health Authorities); NHS England organisational structure |
| `uk-local-authority` | Local authority (county, district, unitary, metropolitan, London borough) | Public Bodies Handbook, Ch. 5 §5.1; ONS local authority classification |
| `uk-devolved-govt` | Scottish Government, Welsh Government, or Northern Ireland Executive body | Public Bodies Handbook, Ch. 5 §5.2 |
| `uk-combined-authority` | Combined or mayoral combined authority | Cities and Local Government Devolution Act 2016 |

#### UK private sector

**Source:** Companies House company type codes; Companies Act 2006.

| Term | Definition | Source reference |
|------|-----------|----------------|
| `uk-ltd-company` | Private limited company (Ltd) | Companies House |
| `uk-plc` | Public limited company (PLC) | Companies House |
| `uk-llp` | Limited liability partnership | Companies House |
| `uk-sole-trader` | Sole trader / self-employed individual | HMRC employment status |
| `uk-startup` | UK company incorporated within last 5 years, fewer than 50 employees | numinal-defined. Justification: Sovereign AI programme specifically targets startups as beneficiaries; this distinction is required for impact reporting |
| `uk-sme` | UK SME per Companies Act 2006 s.465 as amended by SI 2024/1303 (fewer than 250 employees, turnover ≤£54m, balance sheet ≤£27m — must meet 2 of 3). Thresholds effective for periods commencing on or after 6 April 2025. | Companies Act 2006, s.465; SI 2024/1303 |

#### UK academic and research

**Source:** Office for Students register (England); Scottish Funding Council (Scotland); Commission for Tertiary Education and Research (Wales); Department for the Economy (Northern Ireland). HESA maintains the unified UK HE providers list.

| Term | Definition |
|------|-----------|
| `uk-university` | UK higher education institution with degree-awarding powers (registered with OfS, SFC, CTER, or DfE as applicable) |
| `uk-research-institute` | UK independent research organisation (e.g., Turing, Crick, Sanger) |
| `uk-further-education` | UK further education college |
| `uk-research-council` | UKRI research council (e.g., EPSRC, MRC) |

#### UK third sector

| Term | Definition | Source reference |
|------|-----------|----------------|
| `uk-charity` | Registered with Charity Commission (or OSCR/CCNI) | Charity Commission register |
| `uk-social-enterprise` | Organisation with primary social mission | Social Enterprise UK definition |
| `uk-cic` | Community Interest Company | Companies House CIC register |

#### International

| Term | Definition |
|------|-----------|
| `eu-registered-entity` | Entity registered in an EU/EEA member state |
| `international-entity` | Entity registered outside UK and EU/EEA |
| `international-university` | Non-UK higher education institution |
| `international-research-org` | Non-UK independent research organisation |

#### Individual

| Term | Definition |
|------|-----------|
| `individual-researcher` | Named individual (e.g., PhD student, independent researcher) |

### 3.2 Data use purposes (`gov:purpose`)

#### Purposes sourced from GA4GH Data Use Ontology (DUO)

**Source:** DUO ontology, https://github.com/EBISPOT/DUO — verified against duo.owl and OLS4 (EMBL-EBI Ontology Lookup Service).

| numinal term | DUO ID | DUO label | DUO shorthand | Verified |
|-------------|--------|-----------|---------------|----------|
| `general-research` | DUO:0000042 | General research use | GRU | ✓ OWL source + OLS4 |
| `health-biomedical-research` | DUO:0000006 | Health or medical or biomedical research | HMB | ✓ OWL source |
| `disease-specific-research` | DUO:0000007 | Disease-specific research | DS | ✓ OWL source |
| `not-for-profit-non-commercial` | DUO:0000018 | Not-for-profit, non-commercial use only | NPUNCU | ✓ GitHub README |

Note: DUO's scope is biomedical data sharing. numinal extends DUO with AI-specific purpose terms not present in DUO. Each extension term below includes a justification for why no existing DUO term covers the concept.

#### Purposes defined by numinal (no DUO equivalent)

| Term | Definition | Justification for new term |
|------|-----------|--------------------------|
| `model-training` | Training an AI/ML model on the dataset | Core ML workflow; DUO has no AI-specific terms |
| `model-fine-tuning` | Fine-tuning a pre-trained model | Distinct access scope from full training (smaller volumes, different retention) |
| `model-evaluation` | Evaluating model performance against dataset | Testing/validation use; maps to Art. 10(6) lighter requirements |
| `model-validation` | Validating model for regulatory conformity assessment | Distinct from evaluation: specifically for EU AI Act Art. 43 conformity |
| `benchmarking` | Using dataset as public benchmark | Results are published; distinct governance from private evaluation |
| `bias-auditing` | Auditing dataset or model for bias/fairness/discrimination | Required by EU AI Act Art. 10(2)(f); may require access to demographic data |
| `safety-testing` | Testing AI system safety properties | EU AI Act Art. 15 |
| `red-teaming` | Adversarial testing of AI systems for vulnerabilities | Distinct from safety-testing: involves deliberate misuse attempts |
| `reproducibility` | Reproducing published research results | Standard scientific practice; important for grant-funded datasets |
| `dataset-enrichment` | Using one dataset to enrich or augment another | Requires downstream provenance tracking |
| `synthetic-data-generation` | Using real data to generate synthetic training data | Distinct governance: synthetic data may inherit source biases; different retention rules |
| `transfer-learning` | Pre-training a model to be fine-tuned on different data | Distinct from training: dataset domain may differ from final application domain |
| `data-curation` | Using dataset to validate, clean, or curate another | Different access scope needs than training |
| `competition-entry` | Using data in ML competition, challenge, or hackathon | Typically time-limited with mandatory result publication |
| `teaching` | Educational use in teaching settings | Not in DUO; common for university datasets |
| `product-development` | Incorporating into commercial product | Distinct from research; triggers commercial track rules |
| `clinical-decision-support` | Informing clinical decisions in healthcare | High-risk under EU AI Act Annex III |
| `public-service-delivery` | Delivering or improving public services | Relevant for UK public sector consumers |
| `policy-development` | Informing government or institutional policy | Distinct accountability requirements from research |
| `meta-analysis` | Combining with other sources for meta-analysis | Redistribution and derivative work implications |
| `environmental-monitoring` | Environmental, climate, or earth observation | Relevant for geospatial datasets |
| `materials-discovery` | Materials science, drug discovery, molecular simulation | Relevant for autonomous laboratory datasets |
| `simulation-training` | Training simulation or digital twin environments | Relevant for autonomous lab and defence domains |
| `infrastructure-monitoring` | Monitoring or managing critical infrastructure | EU AI Act Annex III §2 high-risk domain |

#### Purpose modifiers sourced from DUO

| numinal term | DUO ID | DUO label | DUO shorthand | Verified |
|-------------|--------|-----------|---------------|----------|
| `geographic-restriction` | DUO:0000022 | Geographical restriction | GS | ✓ OWL source |
| `institution-specific` | DUO:0000028 | Institution-specific restriction | IS | ✓ GitHub README |
| `time-limited` | DUO:0000025 | Time-specific restriction | TS | ✓ GitHub README |
| `project-specific` | DUO:0000027 | Project-specific restriction | PS | ✓ GitHub README |
| `collaboration-required` | DUO:0000020 | Collaboration required | COL | ✓ OWL source |
| `ethics-approval-required` | DUO:0000021 | Ethics approval required | IRB | ✓ OWL source |
| `publication-required` | DUO:0000019 | Publication required | PUB | ✓ OLS4 |
| `publication-moratorium` | DUO:0000024 | Publication moratorium | MOR | ✓ OWL source |
| `return-to-database` | DUO:0000029 | Return to database | RTN | ✓ Consent Codes paper mapping |
| `user-specific` | DUO:0000026 | User-specific restriction | US | ✓ GitHub README |

### 3.3 EU AI Act high-risk domains (`gov:highRiskDomain`)

**Source:** EU AI Act Annex III, Regulation (EU) 2024/1689. Terms taken verbatim from the eight Annex III categories.

| Term | Annex III section |
|------|------------------|
| `biometrics` | §1 |
| `critical-infrastructure` | §2 |
| `education-vocational` | §3 |
| `employment-workers` | §4 |
| `essential-services` | §5 |
| `law-enforcement` | §6 |
| `migration-border` | §7 |
| `justice-democracy` | §8 |
| `not-high-risk` | Consumer declares use outside Annex III |

### 3.4 UK Government security classifications

**Source:** UK Government Security Classifications Policy (GSCP), Cabinet Office. Originally effective 2 April 2014; updated 30 June 2023; latest draft August 2024. Published at: https://www.gov.uk/government/publications/government-security-classifications

Note: The GSCP defines three classification tiers. OFFICIAL-SENSITIVE is not a separate tier — it is an additional marking on OFFICIAL information. "Unclassified" is deliberately omitted from the GSCP; numinal includes it as a convenience term for non-government datasets.

| Term | Classification | Notes |
|------|---------------|-------|
| `official` | OFFICIAL | Majority of government information |
| `official-sensitive` | OFFICIAL-SENSITIVE | Additional marking on OFFICIAL, not a separate tier. Indicates information not intended for public release. |
| `secret` | SECRET | Requires enhanced protective controls; compromise could threaten life or seriously damage UK security |
| `top-secret` | TOP SECRET | Highest sensitivity; compromise could cause exceptionally grave damage |
| `unclassified` | — | numinal convenience term for datasets not subject to UK Government classification. Not an official GSCP term. |

---

## 4. Article 10 compliance fields

Every field in this section maps to a specific sub-clause of EU AI Act Article 10. The full Article 10 text is at: https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-10

Note: Article 10(2) states practices "shall concern *in particular*" items (a)-(h), meaning this list is non-exhaustive. The schema covers all eight named items and provides an `additionalGovernancePractices` field for unlisted practices.

### 4.1 Design choices — Art. 10(2)(a)

```yaml
rai:
  designChoices:
    designObjective: ""          # What was the dataset designed to achieve?
    populationScope: ""          # What populations/phenomena does it represent?
    inclusionCriteria: ""        # What was included and why?
    exclusionCriteria: ""        # What was excluded and why?
    exclusionRationale: ""       # Why were exclusions necessary?
    featureSelectionRationale: "" # Why were these features chosen?
    tradeoffs:                   # What trade-offs were made?
      - tradeoff: ""
        impact: ""
```

### 4.2 Collection processes and origin — Art. 10(2)(b)

```yaml
rai:
  dataCollection: ""  # Free text: how was data gathered?
  dataOrigin:
    sources:
      - name: ""
        type: ""      # e.g., nhs-ehr-system, web-scrape, sensor, survey, purchased
        system: ""     # Specific system name if applicable
        extractionDate: ""
    originalCollectionPurpose: ""  # REQUIRED if personal data. What were data subjects told?
    consentBasis: ""               # Legal basis for original collection
    personalDataPresent: false
    personalDataCategories: []     # e.g., health-data, racial-ethnic-origin
```

### 4.3 Data preparation operations — Art. 10(2)(c)

Article 10(2)(c) names six operation types. Each has a dedicated structured entry.

```yaml
rai:
  dataPreparation:
    annotation:
      performed: false
      description: ""
      annotatorCount: 0
      annotatorQualifications: ""
      annotationGuidelines: ""    # URL to guidelines document
      interAnnotatorAgreement:
        metric: ""                # e.g., Cohen's kappa, Fleiss' kappa, Krippendorff's alpha
        value: 0.0
    labelling:
      performed: false
      description: ""
      labelSchema: ""
      labellingMethod: ""
    cleaning:
      performed: false
      description: ""
      recordsRemovedCount: 0
      recordsRemovedPercentage: 0.0
      removalCriteria: ""
    updating:
      performed: false
      description: ""
    enrichment:
      performed: false
      description: ""
      enrichmentSource: ""
      enrichmentMethod: ""
    aggregation:
      performed: false
      description: ""
      aggregationMethod: ""
      sourceCount: 0
```

### 4.4 Measurement assumptions — Art. 10(2)(d)

```yaml
rai:
  measurementAssumptions:
    - field: ""                # Column/field name
      assumption: ""           # What you assume this data represents
      knownLimitations: ""     # Known validity limitations of this assumption
```

### 4.5 Suitability assessment — Art. 10(2)(e)

```yaml
rai:
  suitabilityAssessment:
    quantityAssessment: ""       # Is there enough data? Evidence?
    availabilityAssessment: ""   # Was needed data available? What was missing?
    suitabilityAssessment: ""    # Is the data appropriate for the intended purpose?
    additionalDataNeeded: ""     # What additional data would improve the dataset?
```

### 4.6 Bias examination — Art. 10(2)(f)

Structured by the three harm categories named in Article 10(2)(f): health/safety, fundamental rights, prohibited discrimination. Plus the feedback loop concern from the same clause.

```yaml
rai:
  biasExamination:
    healthSafetyBiases:
      - bias: ""
        potentialHarm: ""
        severity: ""             # high, medium, low
        affectedPopulation: ""
        detectionMethod: ""
        mitigationStatus: ""     # mitigated, partially-mitigated, documented, not-assessed
        mitigationMeasure: ""
    fundamentalRightsBiases:
      - bias: ""
        potentialHarm: ""
        severity: ""
        affectedPopulation: ""
        detectionMethod: ""
        mitigationStatus: ""
        mitigationMeasure: ""
    discriminationBiases:
      - bias: ""
        protectedCharacteristic: ""  # e.g., race-ethnicity, gender, age, disability, religion
        legalBasis: ""               # e.g., Equality Act 2010, EU AI Act Art. 10(2)(f)
        potentialHarm: ""
        severity: ""
        affectedPopulation: ""
        detectionMethod: ""
        mitigationStatus: ""
        mitigationMeasure: ""
    feedbackLoopRisks:
      - risk: ""
        mitigationStatus: ""
        mitigationMeasure: ""
```

### 4.7 Bias mitigation — Art. 10(2)(g)

Addressed within each bias entry above via `detectionMethod`, `mitigationStatus`, and `mitigationMeasure` fields. These map to the three action types Article 10(2)(g) requires: detect, prevent, mitigate.

### 4.8 Compliance gaps — Art. 10(2)(h)

```yaml
rai:
  complianceGaps:
    - gap: ""
      affectedRequirement: ""      # e.g., art-10-para-3, art-10-para-4
      affectedRequirementText: ""  # Human-readable quote of the requirement
      impactOnCompliance: ""       # How does this gap prevent compliance?
      severity: ""                 # high, medium, low
      remediationPlan: ""
      remediationTimeline: ""      # ISO 8601 date
```

### 4.9 Data quality assessment — Art. 10(3)

```yaml
rai:
  dataQualityAssessment:
    relevance:
      assessment: ""
      evidenceBasis: ""
    representativeness:
      assessment: ""
      comparisonBasis: ""       # What population was compared against?
      knownGaps: ""
    errorRate:
      assessment: ""
      auditMethodology: ""
      errorTypes: ""
    completeness:
      assessment: ""
      missingDataByField: {}    # field_name: percentage_missing
      missingDataStrategy: ""
    statisticalProperties: ""
    combinedDatasetNote: ""     # Per Art. 10(3) final sentence: quality may be met at combined level
```

### 4.10 Geographic and contextual characteristics — Art. 10(4)

```yaml
rai:
  geographicContext:
    dataOriginCountries: []     # ISO 3166-1 alpha-2
    dataOriginRegions: []
    intendedDeploymentContext: ""
    contextualAlignment: ""     # How data matches deployment context
    knownContextualLimitations: ""
  contextualCharacteristics:
    languageCharacteristics: ""
    culturalConsiderations: ""
    temporalCoverage: ""
    functionalContext: ""
```

### 4.11 Special category data handling — Art. 10(5)

**Important:** Article 10(5) obligations fall on the *provider of the high-risk AI system*, not the dataset publisher. This section documents the *publisher's own* handling of special category data. Downstream consumers who are providers of high-risk AI systems have independent Article 10(5) obligations that this documentation supports but does not discharge.

```yaml
gov:
  publisherSpecialCategoryHandling:
    specialCategoryDataPresent: false
    categories: []             # e.g., health-data, racial-ethnic-origin, political-opinions
    processingPurpose: ""      # Should be bias-detection-correction per Art. 10(5)
    processingJustification: ""
    conditions:
      a_alternativeDataInsufficient:
        met: false
        evidence: ""
      b_technicalReuseLimitations:
        met: false
        measures: ""
      c_accessControlAndConfidentiality:
        met: false
        measures: ""
      d_noThirdPartyTransfer:
        met: false
        enforcement: ""
      e_deletionOnCompletion:
        met: false
        mechanism: ""
        retentionPeriodDays: 0
      f_processingRecords:
        met: false
        ropaReference: ""
        justificationDocumented: false
    obligationNote: >
      This section documents the dataset publisher's handling of special category
      data. Downstream consumers who are providers of high-risk AI systems have
      independent obligations under Article 10(5). This documentation supports
      but does not discharge those obligations.
```

### 4.12 Dataset role distinction — Art. 10(6)

Article 10(6) states that for non-training AI systems, paragraphs 2-5 apply only to testing datasets. Each access policy includes:

```yaml
intendedDatasetRole: [training, validation, testing]  # Subset as applicable
```

### 4.13 Additional governance practices

For practices not covered by Article 10(2)(a)-(h):

```yaml
rai:
  additionalGovernancePractices: ""  # Freetext for unlisted practices
```

---

## 5. Access policy structure

### 5.1 ODRL alignment

Each access policy maps to W3C ODRL 2.2 semantics via the DPV-ODRL community profile.

**Standards note:** The DPV-ODRL integration is a W3C Community Group specification (https://w3id.org/dpv/dpv-odrl), not a full W3C Recommendation. ODRL 2.2 itself is a W3C Recommendation. The mapping uses `dpv-odrl:Purpose` as a LeftOperand for purpose-based constraints, as documented in the DPV-ODRL specification.

| numinal YAML | ODRL/DPV expression |
|---|---|
| Permitted purpose | `odrl:Permission` with constraint: `dpv-odrl:Purpose odrl:eq gov:{purpose-term}` |
| Prohibited purpose | `odrl:Prohibition` with constraint: `dpv-odrl:Purpose odrl:eq gov:{purpose-term}` |
| Retention limit | `odrl:Duty` with `odrl:action odrl:delete` and `odrl:dateTime` constraint |
| Attribution | `odrl:Duty` with `odrl:action odrl:attribute` |
| Eligibility | `odrl:Constraint` on `odrl:assignee` with custom left-operands |

### 5.2 Policy YAML structure

```yaml
gov:
  accessPolicies:
    - policyId: ""               # Unique ID
      policyVersion: ""          # Semver
      description: ""            # Human-readable

      eligibility:
        consumerType: []         # From §3.1 vocabulary
        consumerEntity:          # EITHER consumerType OR consumerEntity
          type: ""               # single-organisation | consortium
          # If consortium:
          name: ""
          leadOrganisation:
            name: ""
            type: ""             # From §3.1 vocabulary
          members:
            - name: ""
              type: ""
          consortiumAgreementUrl: ""
        jurisdictions: []        # ISO 3166-1 alpha-2. Empty = no restriction
        requiredCertifications: []
        requiredApprovals: []    # e.g., ethics-approval-required (DUO:0000021)
        excludedEntities: []

      permittedPurposes: []      # From §3.2 vocabulary
      prohibitedPurposes: []
      purposeModifiers: []       # From §3.2 modifiers

      highRiskDomainAdvisory: "" # Advisory note re: Annex III

      accessScope:
        scopeType: ""            # full | partial | sample
        includedRecordSets: []   # Croissant RecordSet IDs (if partial)
        excludedFields: []       # Croissant Field IDs
        rowFilter: ""            # SQL-like WHERE clause (syntax TBD)
        sampleLimit: null        # Max records. Null = unlimited
        accessMethod: ""         # bulk-download | api-query | streaming | federated-query | secure-enclave
        rateLimit:
          requestsPerDay: 0
          maxRecordsPerRequest: 0

      retention:
        maxRetentionDays: 0
        retentionType: ""        # fixed | rolling
        deletionMethod: ""       # cryptographic-erasure | standard-deletion | verified-deletion
        retentionExceptions: ""

      redistribution:
        redistributionPermitted: false
        derivativeWorksPermitted: false
        derivativeWorkConditions: ""
        sharingWithSubprocessors: "" # prohibited | permitted-with-notification | permitted-with-approval

      attribution:
        attributionText: ""
        citationRequired: false
        citationFormat: ""       # bibtex | apa | vancouver | custom
        citation: ""

      auditRequirements:
        auditRightGranted: false
        auditFrequency: ""       # annual | biannual | on-request
        auditScope: ""

      prerequisites:
        - prerequisiteType: ""   # agreement | approval | certification
          description: ""
          verificationMethod: "" # digital-signature | document-upload | manual-review | api-check
          templateUrl: ""

      intendedDatasetRole: []    # training | validation | testing

      effectiveFrom: ""          # ISO 8601
      expiresAt: ""              # ISO 8601. Null = no expiry
```

---

## 6. Derived dataset provenance

When a dataset is derived from one or more source datasets, the data card must document the provenance chain.

```yaml
gov:
  derivedFrom:
    - sourceDataset:
        name: ""
        url: ""
        version: ""
        dataCardUrl: ""
      accessPolicyUsed: ""       # Policy ID under which source was accessed
      accessDate: ""             # ISO 8601
      derivationMethod: ""       # How the derivation was performed
      inheritedConstraints:
        - constraint: ""         # What constraint exists on the source
          inherited: false       # Does it carry forward?
          howAddressed: ""       # How the constraint is handled in the derived dataset
      provenanceCertificateId: "" # numinal platform certificate ID (if accessed via platform)
```

---

## 7. License-governance relationship

```yaml
gov:
  licenseGovernanceRelationship:
    relationship: ""             # license-only | governance-supersedes | complementary | license-with-conditions
    explanation: ""
```

| Term | Meaning |
|------|---------|
| `license-only` | Standard license governs all use; no additional governance policies |
| `governance-supersedes` | Governance policies take precedence for data access; license applies to metadata/documentation |
| `complementary` | License and governance apply simultaneously without conflict |
| `license-with-conditions` | License applies but governance adds enforceable conditions beyond what license requires |

---

## 8. Funding and impact reporting (optional)

These fields are available for any publicly-funded dataset. They are not specific to any single programme.

```yaml
gov:
  fundingSource:
    funderName: ""
    programmeName: ""
    grantReference: ""
    fundingAmount: ""            # ISO 4217 currency code + amount, e.g., "GBP 3500000"
    fundingTrack: ""             # non-commercial | commercial
    reportingBody: ""

  impactReporting:
    metricsRequired: []          # e.g., unique-consumer-organisations, total-api-calls, data-volume-served-gb
    reportingFrequency: ""       # quarterly | biannual | annual
```

---

## 9. Dataset-level governance fields

```yaml
gov:
  governanceModel: ""            # open | controlled | restricted
  governanceVersion: ""          # Semver, independent of dataset version
  dataController:
    name: ""
    contactEmail: ""
    url: ""
  dataProtectionOfficer:
    name: ""
    contactEmail: ""
  dataClassification: ""         # From §3.4
  legalBasis: ""                 # e.g., legitimate-interest, consent, public-task, research-exemption
  regulatoryAlignment: []        # e.g., eu-ai-act-art-10, uk-gdpr, nhs-data-sharing-framework
  lastGovernanceReview: ""       # ISO 8601
```

---

## 10. Field requirement levels

● = required | ○ = optional

### Dataset-level

| Field | T1 | T2 | T3 |
|-------|:--:|:--:|:--:|
| `name` | ● | ● | ● |
| `description` | ● | ● | ● |
| `version` | ● | ● | ● |
| `license` | ● | ● | ● |
| `creator` | ● | ● | ● |
| `datePublished` | ○ | ● | ● |
| `distribution` | ● | ● | ● |
| `recordSet` | ○ | ● | ● |
| `gov:governanceModel` | ● | ● | ● |
| `gov:governanceVersion` | ● | ● | ● |
| `gov:dataController` | ○ | ● | ● |
| `gov:dataClassification` | ○ | ● | ● |
| `gov:legalBasis` | ○ | ●* | ● |
| `gov:regulatoryAlignment` | ○ | ○ | ● |
| `gov:dataProtectionOfficer` | ○ | ○ | ○ |
| `gov:lastGovernanceReview` | ○ | ○ | ● |
| `gov:fundingSource` | ○ | ○ | ○ |
| `gov:impactReporting` | ○ | ○ | ○ |
| `gov:licenseGovernanceRelationship` | ○ | ○ | ● |

*Required at T2 only if personal data present

### RAI / Article 10 fields

| Field | T1 | T2 | T3 | Art. 10 clause |
|-------|:--:|:--:|:--:|:---:|
| `rai:designChoices` | ○ | ● | ● | 10(2)(a) |
| `rai:dataCollection` | ○ | ● | ● | 10(2)(b) |
| `rai:dataOrigin` | ○ | ● | ● | 10(2)(b) |
| `rai:dataOrigin.originalCollectionPurpose` | ○ | ●* | ●* | 10(2)(b) |
| `rai:dataPreparation` | ○ | ● | ● | 10(2)(c) |
| `rai:measurementAssumptions` | ○ | ● | ● | 10(2)(d) |
| `rai:suitabilityAssessment` | ○ | ● | ● | 10(2)(e) |
| `rai:biasExamination` | ○ | ● | ● | 10(2)(f) |
| `rai:complianceGaps` | ○ | ● | ● | 10(2)(h) |
| `rai:dataQualityAssessment` | ○ | ● | ● | 10(3) |
| `rai:geographicContext` | ○ | ● | ● | 10(4) |
| `rai:contextualCharacteristics` | ○ | ○ | ● | 10(4) |
| `gov:publisherSpecialCategoryHandling` | ○ | ●* | ●* | 10(5) |

*Required only if personal data / special category data present

### Governance fields

| Field | T1 | T2 | T3 |
|-------|:--:|:--:|:--:|
| `gov:accessPolicies` (≥1) | ○ | ○ | ● |
| `.eligibility` | — | — | ● |
| `.permittedPurposes` | — | — | ● |
| `.accessScope` | — | — | ● |
| `.retention` | — | — | ● |
| `.redistribution` | — | — | ● |
| `.prerequisites` | — | — | ● |
| `.intendedDatasetRole` | ○ | ● | ● |
| `gov:derivedFrom` | ○ | ○ | ●* |

*Required at T3 only if the dataset is derived from another governed dataset

---

## 11. CLI specification

### 11.1 Installation

```bash
pip install numinal
```

### 11.2 Commands

| Command | Purpose |
|---------|---------|
| `numinal init` | Generate a new data card from a dataset directory |
| `numinal validate` | Validate a data card against all three tiers |
| `numinal render` | Render as markdown, HTML, or PDF |
| `numinal diff` | Compare two data card versions |
| `numinal compliance` | Check against specific regulations |

### 11.3 Validation output

```
$ numinal validate ./datacard.json

Tier 1 (discovery):     ✓ PASS — 12/12 required fields
Tier 2 (regulatory):    ✗ FAIL — 9/14 required fields
  Missing:
  - rai:measurementAssumptions (Art. 10(2)(d))
  - rai:suitabilityAssessment (Art. 10(2)(e))
  - rai:complianceGaps (Art. 10(2)(h))
  - rai:dataQualityAssessment (Art. 10(3))
  - rai:geographicContext (Art. 10(4))
Tier 3 (governed sharing): ✗ FAIL — 14/23 required fields
  [list...]

Completeness: 67% (35/52 total fields)
```

### 11.4 Compliance checker

```
$ numinal compliance ./datacard.json --regulation eu-ai-act-art-10

EU AI Act Article 10 — 13 sub-requirements checked:

✓ 10(2)(a) Design choices
✓ 10(2)(b) Collection and origin
✓ 10(2)(c) Data preparation
✗ 10(2)(d) Assumptions — rai:measurementAssumptions missing
[...]

Score: 10/13 requirements met
```

### 11.5 Auto-detection

The CLI auto-detects from the dataset directory:
- File types, sizes, counts, SHA-256 checksums
- Existing README, LICENSE, Croissant metadata, HuggingFace dataset cards

The CLI does not profile dataset contents. Schema details (field names, data
types, null rates, cardinality) are publisher-supplied — filled in by hand,
imported from a profiling tool, or bootstrapped from existing Croissant
metadata via `numinal init --from-croissant <path-or-url>`, which extracts
`name`, `description`, `version`, `license`, `creator`, `datePublished`,
`distribution`, and `recordSet` and scaffolds the governance layer on top.

---

## 12. Standards reference

| Standard | Version | Usage | URI | Status |
|----------|---------|-------|-----|--------|
| Croissant | 1.0 | Dataset structure | http://mlcommons.org/croissant/1.0 | MLCommons release |
| Croissant-RAI | 1.0 | Responsible AI | http://mlcommons.org/croissant/RAI/ | MLCommons release. Note: RAI properties may be in `cr:` namespace (not separate `rai:` namespace) depending on implementation. Verify against mlcroissant library. |
| W3C ODRL | 2.2 | Policy model | http://www.w3.org/ns/odrl/2/ | W3C Recommendation (Feb 2018) |
| W3C DPV | 2.0 | Privacy vocabulary | https://w3id.org/dpv | W3C Community Group spec (not a W3C Standard) |
| DPV-ODRL | Draft | Purpose constraints | https://w3id.org/dpv/dpv-odrl | W3C Community Group spec, currently in draft, may undergo major changes |
| GA4GH DUO | v2021-02-23 | Purpose vocabulary | https://github.com/EBISPOT/DUO | GA4GH approved standard |
| schema.org | 26.0 | Base vocabulary | https://schema.org/ | Community standard |
| EU AI Act | 2024/1689 | Regulatory mapping | EUR-Lex OJ:L_202401689 | EU Regulation |
| UK GSCP | 2023 (updated Aug 2024) | Data classification | https://www.gov.uk/government/publications/government-security-classifications | UK Government policy (effective April 2014) |
| UK Public Bodies Handbook | Part 1, April 2016 | Org type classification | Cabinet Office: "Classification of Public Bodies: Guidance for Departments" | UK Government guidance. Chapter references verified against full document. |
| Companies Act 2006 | As amended by SI 2024/1303 | SME definition | https://www.legislation.gov.uk/ukpga/2006/46/section/465 | UK primary legislation. Thresholds effective 6 April 2025. |

---

## 13. Known limitations (deferred to v0.3)

1. **Non-health worked examples.** The spec needs validated examples for satellite imagery, financial text, and autonomous lab datasets.
2. **Live dataset governance.** Streaming/continuously updated datasets have governance dynamics not fully specified here.
3. **Full JSON-LD output specification.** The exact JSON-LD structure with GOV namespace declarations needs a reference implementation.
4. **ODRL policy evaluation semantics.** The mapping from YAML to ODRL is defined; the evaluation algorithm for policy matching is a platform concern.
5. **Internationalisation.** Controlled vocabularies are English-only and UK-centric. EU and international variants needed for broader adoption.

---

## 14. Comparison with existing standards

| Feature | Croissant | RAI | DUO | ODRL | DCAT | Datasheets | **numinal GOV** |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| ML dataset structure | ✓ | — | — | — | — | — | ✓ |
| Bias by harm category | — | partial | — | — | — | prose | **✓** |
| Machine-readable | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Purpose vocabulary | — | — | ✓ | — | — | — | ✓ (extends DUO) |
| Access policies | ✗ | ✗ | ✗ | generic | ✗ | ✗ | **✓** |
| Data use agreements | ✗ | ✗ | ✗ | generic | ✗ | ✗ | **✓** |
| Purpose-bound access | ✗ | ✗ | matching | ✗ | ✗ | ✗ | **✓ (enforcement)** |
| Retention/redistribution | ✗ | ✗ | ✗ | generic | ✗ | ✗ | **✓** |
| Art. 10 full mapping | ✗ | partial | ✗ | ✗ | ✗ | ✗ | **✓ (13 sub-reqs)** |
| Art. 10(5) safeguards | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ (6-condition)** |
| Derived provenance | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |
| Org type vocabulary | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ (UK Gov sourced)** |
| Consortium support | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |
| License-governance | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓** |
| Enforceable by platform | ✗ | ✗ | ✗ | with ODRE | ✗ | ✗ | **✓ (ODRL-compat)** |
