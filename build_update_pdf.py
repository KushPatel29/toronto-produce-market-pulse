"""Render a Market Update markdown file to a printable PDF (via LibreOffice). Usage: python build_update_pdf.py 2024-01-30"""

import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

wk = sys.argv[1] if len(sys.argv) > 1 else "2024-01-30"
md = Path(f"outputs/market_update_{wk}.md").read_text(encoding="utf-8")
body = markdown.markdown(md, extensions=["tables"])
html = f"""<html><head><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;font-size:9.5pt;color:#0b0b0b}} h1{{font-size:15pt;color:#1F3864;margin:0 0 4pt}}
h2{{font-size:11pt;color:#1F3864;margin:10pt 0 3pt;border-bottom:1px solid #ccc}} table{{border-collapse:collapse;width:100%}}
th{{background:#1F3864;color:#fff;text-align:left;padding:2pt 4pt}} td{{border-bottom:1px solid #ddd;padding:2pt 4pt}} p,li{{margin:2pt 0}}
</style></head><body>{body}</body></html>"""
out = Path("outputs")
src = out / f"market_update_{wk}.html"
src.write_text(html, encoding="utf-8")
prof = tempfile.mkdtemp()
subprocess.run(
    [
        "soffice",
        f"-env:UserInstallation=file://{prof}",
        "--headless",
        "--convert-to",
        "pdf:writer_web_pdf_Export",
        "--outdir",
        str(out),
        str(src),
    ],
    check=True,
    capture_output=True,
)
src.unlink()
print("wrote", out / f"market_update_{wk}.pdf")
