"""numinal render — render a data card as markdown, HTML, or PDF.

Produces a human-readable document from a numinal.yaml or datacard.json.
Markdown is the primary output format; HTML wraps markdown; PDF is deferred.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from numinal.commands.validate import load_card
from numinal.schema.tiers import _resolve_path, _is_populated


def render_markdown(path: str | Path) -> tuple[str | None, str | None]:
    """Render a data card as a markdown document.

    Returns (markdown_string, error_message).
    """
    card, error = load_card(path)
    if error:
        return None, error

    assert card is not None
    lines: list[str] = []

    # --- Header ---
    name = card.get("name", "Untitled Dataset")
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"**Version:** {card.get('version', 'unknown')}")
    lines.append(f"**License:** {card.get('license', 'not specified')}")
    lines.append(f"**Creator:** {card.get('creator', 'not specified')}")
    if card.get("datePublished"):
        lines.append(f"**Published:** {card['datePublished']}")

    spec = card.get("_spec")
    if spec:
        lines.append(f"**Spec:** {spec}")
    lines.append("")

    desc = card.get("description", "")
    if desc:
        lines.append(f"> {desc}")
        lines.append("")

    # --- Governance ---
    gov = card.get("gov", {})
    if gov:
        lines.append("## Governance")
        lines.append("")
        if gov.get("governanceModel"):
            lines.append(f"**Model:** {gov['governanceModel']}")
        if gov.get("governanceVersion"):
            lines.append(f"**Governance version:** {gov['governanceVersion']}")
        if gov.get("dataClassification"):
            lines.append(f"**Classification:** {gov['dataClassification']}")
        if gov.get("legalBasis"):
            lines.append(f"**Legal basis:** {gov['legalBasis']}")

        dc = gov.get("dataController", {})
        if dc.get("name"):
            lines.append(f"**Data controller:** {dc['name']}")
            if dc.get("contactEmail"):
                lines.append(f"**Contact:** {dc['contactEmail']}")

        alignment = gov.get("regulatoryAlignment", [])
        if alignment:
            lines.append(f"**Regulatory alignment:** {', '.join(alignment)}")

        lgr = gov.get("licenseGovernanceRelationship", {})
        if lgr.get("relationship"):
            lines.append(f"**License-governance:** {lgr['relationship']}")
            if lgr.get("explanation"):
                lines.append(f"  — {lgr['explanation']}")
        lines.append("")

    # --- Distribution ---
    dist = card.get("distribution", [])
    if dist:
        lines.append("## Distribution")
        lines.append("")
        lines.append("| Name | Type | Files | Size |")
        lines.append("|------|------|------:|-----:|")
        for d in dist:
            name_d = d.get("name", "")
            ct = d.get("contentType", "")
            fc = d.get("fileCount", "")
            sz = _human_size(d.get("totalSizeBytes", 0))
            lines.append(f"| {name_d} | {ct} | {fc} | {sz} |")
        lines.append("")

    # --- Record Sets ---
    rsets = card.get("recordSet", [])
    if rsets:
        lines.append("## Record Sets")
        lines.append("")
        for rs in rsets:
            lines.append(f"### {rs.get('name', 'unnamed')}")
            if rs.get("description"):
                lines.append(f"\n{rs['description']}")
            if rs.get("source"):
                lines.append(f"\n**Source:** `{rs['source']}`")
            fields = rs.get("fields", [])
            if fields:
                lines.append("")
                lines.append("| Field | Type | Null rate | Cardinality |")
                lines.append("|-------|------|----------:|------------:|")
                for f in fields:
                    nr = f"{f['nullRate']:.1%}" if "nullRate" in f else "—"
                    card_val = str(f.get("cardinality", "—"))
                    lines.append(f"| `{f.get('name', '')}` | {f.get('dataType', '')} | {nr} | {card_val} |")
            lines.append("")

    # --- RAI: Design Choices ---
    rai = card.get("rai", {})
    if rai:
        lines.append("## Responsible AI Documentation")
        lines.append("")

        dc_section = rai.get("designChoices", {})
        if dc_section and isinstance(dc_section, dict):
            lines.append("### Design Choices — Art. 10(2)(a)")
            lines.append("")
            for key, label in [
                ("designObjective", "Design objective"),
                ("populationScope", "Population scope"),
                ("inclusionCriteria", "Inclusion criteria"),
                ("exclusionCriteria", "Exclusion criteria"),
                ("exclusionRationale", "Exclusion rationale"),
                ("featureSelectionRationale", "Feature selection rationale"),
            ]:
                val = dc_section.get(key, "")
                if val and not str(val).startswith("TODO"):
                    lines.append(f"**{label}:** {val}")
            tradeoffs = dc_section.get("tradeoffs", [])
            if tradeoffs:
                lines.append("\n**Trade-offs:**")
                for t in tradeoffs:
                    if isinstance(t, dict):
                        lines.append(f"- {t.get('tradeoff', '')} — *Impact:* {t.get('impact', '')}")
            lines.append("")

        # --- Data Collection & Origin ---
        if rai.get("dataCollection") and not str(rai["dataCollection"]).startswith("TODO"):
            lines.append("### Collection and Origin — Art. 10(2)(b)")
            lines.append("")
            lines.append(rai["dataCollection"])
            origin = rai.get("dataOrigin", {})
            if origin.get("personalDataPresent"):
                lines.append(f"\n**Personal data present:** Yes")
                cats = origin.get("personalDataCategories", [])
                if cats:
                    lines.append(f"**Categories:** {', '.join(cats)}")
            sources = origin.get("sources", [])
            if sources:
                lines.append("\n**Sources:**")
                for s in sources:
                    lines.append(f"- {s.get('name', 'unnamed')} ({s.get('type', '')})")
            lines.append("")

        # --- Data Preparation ---
        prep = rai.get("dataPreparation", {})
        if prep and isinstance(prep, dict):
            active_ops = [k for k, v in prep.items()
                          if isinstance(v, dict) and v.get("performed")]
            if active_ops:
                lines.append("### Data Preparation — Art. 10(2)(c)")
                lines.append("")
                for op_name in active_ops:
                    op = prep[op_name]
                    lines.append(f"**{op_name.title()}:** {op.get('description', '')}")
                    if op_name == "annotation":
                        if op.get("annotatorCount"):
                            lines.append(f"  - Annotators: {op['annotatorCount']}")
                        iaa = op.get("interAnnotatorAgreement", {})
                        if iaa.get("metric"):
                            lines.append(f"  - {iaa['metric']}: {iaa.get('value', '')}")
                    if op_name == "cleaning":
                        if op.get("recordsRemovedCount"):
                            lines.append(f"  - Records removed: {op['recordsRemovedCount']} ({op.get('recordsRemovedPercentage', 0):.1f}%)")
                    if op_name == "aggregation":
                        if op.get("sourceCount"):
                            lines.append(f"  - Sources aggregated: {op['sourceCount']}")
                lines.append("")

        # --- Bias Examination ---
        bias = rai.get("biasExamination", {})
        if bias and isinstance(bias, dict):
            has_entries = any(
                bias.get(cat) for cat in
                ("healthSafetyBiases", "fundamentalRightsBiases", "discriminationBiases", "feedbackLoopRisks")
            )
            if has_entries:
                lines.append("### Bias Examination — Art. 10(2)(f)")
                lines.append("")
                for cat_key, cat_label in [
                    ("healthSafetyBiases", "Health & Safety"),
                    ("fundamentalRightsBiases", "Fundamental Rights"),
                    ("discriminationBiases", "Discrimination"),
                ]:
                    entries = bias.get(cat_key, [])
                    if entries:
                        lines.append(f"**{cat_label} biases:**")
                        for e in entries:
                            lines.append(f"- **{e.get('bias', '')}** (severity: {e.get('severity', 'unrated')})")
                            lines.append(f"  - Affected: {e.get('affectedPopulation', 'not specified')}")
                            lines.append(f"  - Status: {e.get('mitigationStatus', 'not assessed')}")
                            if e.get("mitigationMeasure"):
                                lines.append(f"  - Measure: {e['mitigationMeasure']}")
                        lines.append("")

                fl = bias.get("feedbackLoopRisks", [])
                if fl:
                    lines.append("**Feedback loop risks:**")
                    for r in fl:
                        lines.append(f"- {r.get('risk', '')} (status: {r.get('mitigationStatus', '')})")
                    lines.append("")

        # --- Compliance Gaps ---
        gaps = rai.get("complianceGaps", [])
        if gaps:
            lines.append("### Compliance Gaps — Art. 10(2)(h)")
            lines.append("")
            for g in gaps:
                sev = g.get("severity", "")
                lines.append(f"- **{g.get('gap', '')}** [{sev}]")
                if g.get("affectedRequirement"):
                    lines.append(f"  - Affects: {g['affectedRequirement']}")
                if g.get("remediationPlan"):
                    lines.append(f"  - Plan: {g['remediationPlan']}")
                if g.get("remediationTimeline"):
                    lines.append(f"  - Timeline: {g['remediationTimeline']}")
            lines.append("")

        # --- Data Quality ---
        dq = rai.get("dataQualityAssessment", {})
        if dq and isinstance(dq, dict):
            lines.append("### Data Quality — Art. 10(3)")
            lines.append("")
            for key, label in [
                ("relevance", "Relevance"),
                ("representativeness", "Representativeness"),
                ("errorRate", "Error rate"),
                ("completeness", "Completeness"),
            ]:
                section = dq.get(key, {})
                if isinstance(section, dict) and section.get("assessment"):
                    val = section["assessment"]
                    if not str(val).startswith("TODO"):
                        lines.append(f"**{label}:** {val}")
            lines.append("")

        # --- Geographic Context ---
        geo = rai.get("geographicContext", {})
        if geo and isinstance(geo, dict):
            countries = geo.get("dataOriginCountries", [])
            if countries:
                lines.append("### Geographic Context — Art. 10(4)")
                lines.append("")
                lines.append(f"**Origin countries:** {', '.join(countries)}")
                if geo.get("intendedDeploymentContext") and not str(geo["intendedDeploymentContext"]).startswith("TODO"):
                    lines.append(f"**Deployment context:** {geo['intendedDeploymentContext']}")
                if geo.get("knownContextualLimitations"):
                    lines.append(f"**Limitations:** {geo['knownContextualLimitations']}")
                lines.append("")

    # --- Access Policies ---
    policies = gov.get("accessPolicies", [])
    if policies:
        lines.append("## Access Policies")
        lines.append("")
        for p in policies:
            pid = p.get("policyId", "unnamed")
            lines.append(f"### Policy: {pid}")
            if p.get("description"):
                lines.append(f"\n{p['description']}")
            lines.append("")

            elig = p.get("eligibility", {})
            ct = elig.get("consumerType", [])
            if ct:
                lines.append(f"**Eligible consumers:** {', '.join(ct)}")
            juris = elig.get("jurisdictions", [])
            if juris:
                lines.append(f"**Jurisdictions:** {', '.join(juris)}")

            pp = p.get("permittedPurposes", [])
            if pp:
                lines.append(f"**Permitted purposes:** {', '.join(pp)}")
            prohib = p.get("prohibitedPurposes", [])
            if prohib:
                lines.append(f"**Prohibited purposes:** {', '.join(prohib)}")

            scope = p.get("accessScope", {})
            if scope.get("scopeType"):
                lines.append(f"**Scope:** {scope['scopeType']} via {scope.get('accessMethod', 'unspecified')}")

            ret = p.get("retention", {})
            if ret.get("maxRetentionDays"):
                lines.append(f"**Retention:** {ret['maxRetentionDays']} days ({ret.get('retentionType', '')}) — deletion via {ret.get('deletionMethod', 'unspecified')}")

            redist = p.get("redistribution", {})
            lines.append(f"**Redistribution:** {'permitted' if redist.get('redistributionPermitted') else 'not permitted'}")
            lines.append(f"**Derivative works:** {'permitted' if redist.get('derivativeWorksPermitted') else 'not permitted'}")

            roles = p.get("intendedDatasetRole", [])
            if roles:
                lines.append(f"**Dataset role:** {', '.join(roles)}")
            lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by numinal CLI. Spec: {card.get('_spec', 'unknown')}*")
    lines.append("")

    return "\n".join(lines), None


def _human_size(nbytes: int) -> str:
    """Format bytes as human-readable."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"
