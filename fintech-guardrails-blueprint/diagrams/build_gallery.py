"""Create an offline image gallery and a portable diagram package."""
import html
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
records = json.loads((ROOT / "diagram-manifest.json").read_text())
overview = {"slug": "00-problem-to-solution", "title": "Problem, solution and value to prove",
            "subtitle": "Why this proposed product exists and where its first release starts",
            "source": "01-product-and-problem.md"}
records.insert(0, overview)
intro = ("These diagrams describe the proposed FinGuard blueprint. They do not represent a deployed product. "
         "First release: invoice checks, one-to-one reconciliation and simulated payment controls. "
         "Five expansion modules require separate validation. FinGuard is a working name.")
md = ["# FinGuard diagram gallery", "", intro, "", 
      "16 PNG images, plus editable DOT sources and scalable SVG versions of the 15 technical diagrams.", "",
      "[Open the offline gallery](index.html) · [Download the complete ZIP](../finguard-diagrams.zip) · [Back to the blueprint](../README.md)", "",
      "## Diagram index", "", "| # | Diagram | Image | Scalable image | Source |", "|---|---|---|---|---|"]
cards = []
nav = []
for i, r in enumerate(records):
    slug, title, subtitle = r["slug"], r["title"], r["subtitle"]
    svg_link = f"[SVG]({slug}.svg)" if i else "—"
    source_link = f"[DOT](sources/{slug}.dot)" if i else "[Generation prompt](sources/00-overview-prompt.txt)"
    md.append(f"| {i:02} | {title} | [PNG]({slug}.png) | {svg_link} | {source_link} |")
    links = f'<a href="{slug}.png" download>Download PNG</a>'
    if i:
        links += f'<a href="{slug}.svg" download>Download SVG</a><a href="sources/{slug}.dot">Editable source</a>'
    else:
        links += '<a href="sources/00-overview-prompt.txt">Overview prompt</a>'
    links += f'<a href="../{r["source"]}">Blueprint reference</a>'
    nav.append(f'<li><a href="#{slug}">{i:02} · {html.escape(title)}</a></li>')
    cards.append(f'''<section id="{slug}"><div class="caption"><span class="number">{i:02}</span><div>
<h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p></div></div>
<a class="image" href="{slug}.png" title="Open full-resolution image"><img src="{slug}.png" alt="{html.escape(title)}. {html.escape(subtitle)}" loading="lazy"></a>
<div class="links">{links}</div></section>''')
md += ["", "## How to use these images", "",
       "- Use PNG for slides, reports and sharing. Open at full size to inspect small labels.",
       "- Use SVG when you need to zoom or print the technical diagrams without losing sharpness.",
       "- Edit a DOT file and run `python3 render_diagrams.py` with Graphviz installed to regenerate the technical images.",
       "- The overview was created with the built-in image-generation tool; its exact prompt is saved with the sources.",
       "- The technical diagrams faithfully simplify the existing blueprint. The linked documents define the complete contracts.",
       "- Competitor groups summarize the dated research in document 07; they are not rankings or evidence of superiority.", ""]
for r in records:
    md += [f"## {r['slug'][:2]}. {r['title']}", "", r["subtitle"], "", f"![{r['title']}]({r['slug']}.png)", ""]
(ROOT / "README.md").write_text("\n".join(md))
page = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinGuard · Diagram gallery</title><style>
:root{color-scheme:light;font:16px/1.55 system-ui,sans-serif;color:#173047;background:#f2f5f7}
*{box-sizing:border-box}body{margin:0}main{max-width:1200px;margin:auto;padding:48px 24px}
h1{font-size:40px;line-height:1.12;margin:12px 0 20px;letter-spacing:-1px}h2{font-size:24px;margin:0;line-height:1.25}
p{color:#526779;margin:10px 0}.eyebrow{color:#326f60;text-transform:uppercase;font-size:13px;letter-spacing:1.5px}
.intro{max-width:900px}a{color:#175f84;text-underline-offset:3px}.toplinks,.links{display:flex;gap:18px;flex-wrap:wrap}
.toplinks{margin:24px 0}nav{background:white;border-radius:12px;padding:20px 24px;margin:24px 0 40px}
nav ol{columns:2;padding-left:20px;margin:0}nav li{break-inside:avoid;margin:8px 0}
section{background:#fcfcfa;border:1px solid #dce4e9;border-radius:14px;margin:28px 0;overflow:hidden;scroll-margin-top:20px}
.caption{padding:24px;display:flex;gap:16px;border-bottom:1px solid #e3e9ed}.caption p{margin:8px 0 0}
.number{font-size:16px;color:#367967;padding-top:4px}.image{display:block;padding:18px}.image img{display:block;width:100%;height:auto;max-height:1100px;object-fit:contain}
.links{padding:18px 24px;border-top:1px solid #e3e9ed;font-size:14px}footer{margin:40px 0;color:#526779}
@media(max-width:600px){main{padding:28px 12px}h1{font-size:32px}h2{font-size:21px}nav ol{columns:1}.caption{padding:18px}}
@media print{body{background:white}main{padding:0}nav,.toplinks,.links{display:none}section{break-inside:avoid;border:0;break-before:page}.image{padding:0}}
</style></head><body><main><header><div class="eyebrow">FinGuard / visual blueprint / October 2026</div>
<h1>From product idea to startup</h1><p class="intro">INTRO</p><p>16 diagram images. Open any image for full resolution.</p>
<div class="toplinks"><a href="../finguard-diagrams.zip" download>Download all diagrams and sources</a><a href="../README.md">Read the complete blueprint</a></div></header>
<nav aria-label="Diagram index"><ol>NAV</ol></nav>CARDS
<footer>Proposed design, not an implemented system. Source documents retain the full detail. Overview generated with the built-in image-generation tool; technical diagrams rendered from editable Graphviz sources.</footer>
</main></body></html>'''.replace("INTRO", html.escape(intro)).replace("NAV", "".join(nav)).replace("CARDS", "".join(cards))
(ROOT / "index.html").write_text(page)
archive = ROOT.parent / "finguard-diagrams.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as pack:
    files = sorted(ROOT.rglob("*")) + sorted(ROOT.parent.glob("*.md"))
    for path in files:
        if path.is_file() and "__pycache__" not in path.parts:
            pack.write(path, Path("finguard-blueprint") / path.relative_to(ROOT.parent))
print(json.dumps({"images": len(records), "archive": str(archive), "bytes": archive.stat().st_size}))
