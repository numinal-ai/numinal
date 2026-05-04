"""numinal CLI — governance-as-code data cards.

Entry point: `numinal` command group with `init` and `validate` subcommands.
Output formatting uses Rich for coloured terminal output matching spec §11.3.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from numinal import __version__

console = Console(highlight=False)


@click.group()
@click.version_option(version=__version__, prog_name="numinal")
def cli() -> None:
    """numinal — governance-as-code data cards for AI dataset sharing."""
    pass


# ---------------------------------------------------------------------------
# numinal init
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("directory", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", default="numinal.yaml", help="Output filename")
@click.option(
    "-t", "--tier", default=1, type=click.IntRange(1, 3),
    help="Target compliance tier to scaffold (1=discovery, 2=regulatory, 3=governed sharing)",
)
@click.option("--non-interactive", is_flag=True, help="Skip prompts and use defaults")
def init(directory: str, output: str, tier: int, non_interactive: bool) -> None:
    """Generate a new data card from a dataset directory.

    Scans DIRECTORY for files, detects structure, and creates a numinal.yaml
    with auto-populated fields and TODO markers for manual completion.
    """
    from numinal.commands.init import run_init

    try:
        run_init(directory, output=output, tier=tier, non_interactive=non_interactive)
    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# numinal validate
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-t", "--tier", default=None, type=click.IntRange(1, 3),
    help="Only check a specific tier (default: check all)",
)
@click.option("--json-output", is_flag=True, help="Output as JSON instead of formatted text")
def validate(file: str, tier: int | None, json_output: bool) -> None:
    """Validate a data card against compliance tiers.

    Checks FILE (numinal.yaml or datacard.json) against Tier 1 (discovery),
    Tier 2 (regulatory), and Tier 3 (governed sharing) requirements.
    """
    from numinal.commands.validate import validate as run_validate

    result = run_validate(file)

    if result.parse_error:
        console.print(f"[red]Error:[/red] {result.parse_error}")
        raise SystemExit(1)

    if json_output:
        _print_json(result)
    else:
        _print_formatted(result, tier_filter=tier)

    # Exit code: 0 if highest requested tier passes, 1 otherwise
    target_tier = tier or 3
    for tr in result.tiers:
        if tr.tier == target_tier and not tr.passed:
            raise SystemExit(1)


def _print_formatted(result, tier_filter: int | None = None) -> None:
    """Print formatted validation output matching spec §11.3."""
    from numinal.commands.validate import ValidationResult

    console.print()

    tiers_to_show = result.tiers
    if tier_filter:
        tiers_to_show = [t for t in result.tiers if t.tier == tier_filter]

    for tr in tiers_to_show:
        if tr.passed:
            status = Text("✓ PASS", style="green bold")
            line = Text()
            line.append(f"Tier {tr.tier} ({tr.tier_name}):".ljust(30))
            line.append(status)
            line.append(f" — {tr.present_count}/{tr.required_count} required fields")
            console.print(line)
        else:
            status = Text("✗ FAIL", style="red bold")
            line = Text()
            line.append(f"Tier {tr.tier} ({tr.tier_name}):".ljust(30))
            line.append(status)
            line.append(f" — {tr.present_count}/{tr.required_count} required fields")
            console.print(line)

            console.print("  Missing:")
            for m in tr.missing:
                clause = f" (Art. {m.article_10_clause})" if m.article_10_clause else ""
                console.print(f"  [dim]- {m.field_path}{clause}[/dim]")

        if tr.skipped:
            console.print(f"  [dim]Skipped (conditional): {len(tr.skipped)} field(s)[/dim]")

    # Completeness
    console.print()
    total = result.total_fields
    populated = result.populated_fields
    pct = result.completeness_pct
    console.print(f"Completeness: {pct:.0f}% ({populated}/{total} total fields)")

    # Vocabulary warnings
    errors = [w for w in result.vocab_warnings if w.is_error]
    warnings = [w for w in result.vocab_warnings if not w.is_error]

    if errors:
        console.print()
        console.print(f"[red]Vocabulary errors ({len(errors)}):[/red]")
        for e in errors:
            console.print(f"  [red]✗[/red] {e.message}")

    if warnings:
        console.print()
        console.print(f"[yellow]Vocabulary warnings ({len(warnings)}):[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]![/yellow] {w.message}")

    # Policy sub-field results
    if result.policy_results:
        console.print()
        console.print("[yellow]Access policy sub-field gaps:[/yellow]")
        for pr in result.policy_results:
            console.print(f"  Policy '{pr.policy_id}' missing: {', '.join(pr.missing_subfields)}")

    console.print()


def _print_json(result) -> None:
    """Print validation result as JSON."""
    import json

    output = {
        "file": result.file_path,
        "tiers": [
            {
                "tier": tr.tier,
                "name": tr.tier_name,
                "passed": tr.passed,
                "required": tr.required_count,
                "present": tr.present_count,
                "missing": [
                    {
                        "field": m.field_path,
                        "description": m.description,
                        "article10": m.article_10_clause,
                    }
                    for m in tr.missing
                ],
            }
            for tr in result.tiers
        ],
        "completeness": {
            "percentage": round(result.completeness_pct, 1),
            "populated": result.populated_fields,
            "total": result.total_fields,
        },
        "vocabErrors": [
            {"field": w.field_path, "term": w.term, "message": w.message}
            for w in result.vocab_warnings if w.is_error
        ],
        "vocabWarnings": [
            {"field": w.field_path, "term": w.term, "message": w.message}
            for w in result.vocab_warnings if not w.is_error
        ],
    }
    click.echo(json.dumps(output, indent=2))


# ---------------------------------------------------------------------------
# Placeholder commands (not yet implemented)
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["markdown", "html", "pdf"]), default="markdown")
@click.option("-o", "--output", default=None, help="Output file (default: stdout)")
def render(file: str, fmt: str, output: str | None) -> None:
    """Render a data card as markdown, HTML, or PDF."""
    if fmt in ("html", "pdf"):
        console.print(f"[yellow]{fmt} rendering not yet implemented (planned for v0.2). Use --format markdown.[/yellow]")
        raise SystemExit(0)

    from numinal.commands.render import render_markdown

    md, error = render_markdown(file)
    if error:
        console.print(f"[red]Error:[/red] {error}")
        raise SystemExit(1)

    assert md is not None
    if output:
        Path(output).write_text(md, encoding="utf-8")
        console.print(f"✓ Rendered to {output}")
    else:
        click.echo(md)


@cli.command()
@click.argument("file_a", type=click.Path(exists=True, dir_okay=False))
@click.argument("file_b", type=click.Path(exists=True, dir_okay=False))
def diff(file_a: str, file_b: str) -> None:
    """Compare two data card versions."""
    console.print("[yellow]diff command not yet implemented (planned for v0.2)[/yellow]")
    raise SystemExit(0)


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option("--regulation", type=click.Choice(["eu-ai-act-art-10"]), required=True)
@click.option("--json-output", is_flag=True, help="Output as JSON")
def compliance(file: str, regulation: str, json_output: bool) -> None:
    """Check a data card against specific regulations."""
    from numinal.commands.compliance import check_compliance

    result = check_compliance(file)

    if result.parse_error:
        console.print(f"[red]Error:[/red] {result.parse_error}")
        raise SystemExit(1)

    if json_output:
        import json as json_mod
        output = {
            "file": result.file_path,
            "regulation": regulation,
            "checks": [
                {
                    "clause": c.clause,
                    "label": c.label,
                    "passed": c.passed,
                    "skipped": c.skipped,
                    "missing": c.missing_fields,
                }
                for c in result.checks
            ],
            "score": {"passed": result.passed_count, "total": result.total_checked},
        }
        click.echo(json_mod.dumps(output, indent=2))
    else:
        console.print()
        console.print(f"EU AI Act Article 10 — {result.total_checked} sub-requirements checked:")
        console.print()

        for c in result.checks:
            if c.skipped:
                console.print(f"  [dim]— {c.clause} {c.label} (skipped: {c.skipped_reason})[/dim]")
            elif c.passed:
                console.print(f"  [green]✓[/green] {c.clause} {c.label}")
            else:
                missing_str = ", ".join(c.missing_fields) if c.missing_fields else ""
                suffix = f" — {missing_str} missing" if missing_str else ""
                console.print(f"  [red]✗[/red] {c.clause} {c.label}{suffix}")

        console.print()
        console.print(f"Score: {result.passed_count}/{result.total_checked} requirements met")
        console.print()

    if not result.all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
