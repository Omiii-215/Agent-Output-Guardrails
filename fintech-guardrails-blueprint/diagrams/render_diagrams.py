"""Render editable DOT diagram sources to PNG and SVG with one visual style."""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
DIAGRAMS = [
    ("01-system-context", "System context", "People, source systems and provider boundaries", "02-system-architecture.md"),
    ("02-system-architecture", "System architecture / high-level design", "One modular application, an API and durable background workers", "02-system-architecture.md"),
    ("03-technology-stack", "Technology stack", "Proposed development and pilot-hosting choices", "03-technology-stack.md"),
    ("04-low-level-components", "Low-level component design", "Application services and their control boundaries", "04-low-level-design.md"),
    ("05-core-data-model", "Core data model", "Simplified relationships; see the LLD for complete contracts", "04-low-level-design.md"),
    ("06-approval-lifecycle", "Approval lifecycle", "Approval binds an independent reviewer to an exact proposal", "04-low-level-design.md"),
    ("07-payment-execution", "Payment execution and recovery", "Simulation first; live connectors require a separate release gate", "04-low-level-design.md"),
    ("08-finance-user-flow", "Finance user flow", "From an invoice to a reviewed, traceable simulation", "05-user-and-buyer-flows.md"),
    ("09-reconciliation-flow", "Reconciliation flow", "First release supports exact one-to-one matching only", "05-user-and-buyer-flows.md"),
    ("10-target-buyer-flow", "Target buyer journey", "CFO or controller buys; finance staff validate daily usefulness", "05-user-and-buyer-flows.md"),
    ("11-consumer-correction-flow", "Supplier and consumer correction flow", "Requests pass through the customer organization's authorized channel", "05-user-and-buyer-flows.md"),
    ("12-competitive-positioning", "Competitive landscape and positioning", "Known product overlap; proposed differentiation still needs evidence", "07-competition-and-positioning.md"),
    ("13-implementation-roadmap", "Implementation roadmap", "12-16 weeks assumes two experienced builders and accessible data", "08-implementation-plan.md"),
    ("14-startup-roadmap", "From project to startup", "Advance when customer evidence supports the next investment", "06-startup-roadmap.md"),
    ("15-eight-module-platform", "Eight modules, one shared platform", "Three first-release workflows; five separately validated expansions", "01-product-and-problem.md"),
]

def style_source(source: str, number: str, title: str, subtitle: str) -> str:
    heading = (
        '<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5">'
        '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="12" COLOR="#3F756A">'
        f'FINGUARD / DESIGN BLUEPRINT / {number}</FONT></TD></TR>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="28"><B>{html.escape(title)}</B></FONT></TD></TR>'
        f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="15" COLOR="#4D6071">{html.escape(subtitle)}</FONT></TD></TR>'
        '<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="11" COLOR="#60717D">'
        'Proposed design | October 2026 | Not an implemented system</FONT></TD></TR>'
        '<TR><TD HEIGHT="20"></TD></TR></TABLE>'
    )
    defaults = f'''
    graph [bgcolor="#FCFCFA", fontname="Helvetica", fontcolor="#142C41",
           pad="0.45", nodesep="0.40", ranksep="0.65", splines=polyline,
           labelloc=t, labeljust=l, label=<{heading}>];
    node [shape=box, style="rounded,filled", fillcolor="#F0F3F7", color="#C9D4DC",
          penwidth=1, fontname="Helvetica", fontcolor="#142C41", fontsize=15,
          margin="0.20,0.14"];
    edge [color="#60778A", penwidth=1.3, arrowsize=0.7, fontname="Helvetica",
          fontcolor="#3B5366", fontsize=11];
'''
    styled = re.sub(r'(digraph\s+\w+\s*\{)', lambda m: m.group(1) + defaults, source, count=1)
    cluster_style = ('\n    graph [style="rounded,filled", fillcolor="#F8FAFB", '
                     'color="#D3DFE6", penwidth=1, margin=22, fontsize=14];\n')
    return re.sub(r'(subgraph\s+cluster_\w+\s*\{)', lambda m: m.group(1) + cluster_style, styled)

def main() -> None:
    rendered = ROOT / "sources" / "styled"
    rendered.mkdir(parents=True, exist_ok=True)
    report = []
    for slug, title, subtitle, source_doc in DIAGRAMS:
        source_path = ROOT / "sources" / f"{slug}.dot"
        if not source_path.exists():
            continue
        styled_path = rendered / source_path.name
        styled_path.write_text(style_source(source_path.read_text(), slug[:2], title, subtitle))
        warnings = []
        for fmt in ("svg", "png"):
            proc = subprocess.run([
                "dot", f"-T{fmt}", "-Gdpi=180", "-Gsize=18,13",
                str(styled_path), "-o", str(ROOT / f"{slug}.{fmt}"),
            ], capture_output=True, text=True, check=True)
            if proc.stderr.strip():
                warnings.append(proc.stderr.strip())
        report.append({"slug": slug, "title": title, "subtitle": subtitle,
                       "source": source_doc, "warnings": warnings})
    (ROOT / "diagram-manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"rendered": len(report), "warnings": [r for r in report if r["warnings"]]}, indent=2))

if __name__ == "__main__":
    main()
