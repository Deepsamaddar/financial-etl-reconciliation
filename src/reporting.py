"""Export a self-contained, synthetic-demo report without a web server."""
from __future__ import annotations

import html
import json
from pathlib import Path


def write_report(result: dict, directory: Path) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    rows = result["rows_in"]
    rate = 100 * result["rows_clean"] / rows if rows else 0
    labels = {"matched": "Matched", "amount_break": "Amount differences",
              "missing_bank": "Missing from bank", "missing_ledger": "Missing from ledger"}
    table = "".join(f'<tr><td>{label}</td><td>{result["reconciliation"][key]:,}</td></tr>'
                    for key, label in labels.items())
    cards = "".join(f'<div class="card"><span>{label}</span><strong>{value:,}</strong></div>'
                    for label, value in [("Source records", rows), ("Accepted", result["rows_clean"]),
                                         ("Quarantined", result["rows_quarantined"])])
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Deep Samaddar | Financial ETL Report</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#101927;color:#edf3fa;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1040px;margin:auto;padding:64px 28px}}.tag{{color:#7ee0bf;letter-spacing:.16em;font-size:12px;font-weight:700}}
h1{{font-size:clamp(30px,5vw,48px);line-height:1.15;margin:16px 0}}p{{color:#abbcd0}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:32px 0}}
.card,.panel{{background:#19263a;border:1px solid #30415a;border-radius:14px;padding:24px}}
.card span{{display:block;color:#abbcd0}}strong{{display:block;font-size:36px;margin-top:6px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:14px 0;text-align:left;border-bottom:1px solid #30415a}}td:last-child,th:last-child{{text-align:right}}
progress{{width:100%;height:14px;accent-color:#7ee0bf}}code{{overflow-wrap:anywhere}}footer{{margin-top:32px;color:#abbcd0;font-size:13px}}
@media(max-width:600px){{.cards{{grid-template-columns:1fr}}main{{padding:30px 18px}}}}
</style><main><div class="tag">DEEP SAMADDAR / DATA ENGINEERING PORTFOLIO</div>
<h1>Financial ETL &amp;<br>reconciliation report</h1>
<p>A reproducible view of data quality and ledger-to-bank exceptions. Synthetic-data demonstration.</p>
<p>Run <code>{html.escape(result["run_id"])}</code></p><section class="cards">{cards}</section>
<section class="panel"><h2>Data quality</h2><p>{rate:.2f}% of source records accepted</p>
<progress value="{rate}" max="100" aria-label="Accepted source records">{rate:.2f}%</progress>
<p>Control: source records = accepted + quarantined.</p></section><br>
<section class="panel"><h2>Reconciliation outcomes</h2><table><thead><tr><th scope="col">Outcome</th><th scope="col">Records</th></tr></thead><tbody>{table}</tbody></table>
<p>Missing-from-ledger records can include source records rejected by the quality gate.
Counts describe this run only; they are not production performance claims.</p></section>
<footer>Deep Samaddar · Financial ETL portfolio extension. Third-party license notices are retained in the repository LICENSE.
No real customer or bank data. Reconciliation is in memory; the demo assumes unique IDs and consistent currencies per ID.</footer></main></html>'''
    path = directory / "report.html"
    path.write_text(document + "\n")
    return path
