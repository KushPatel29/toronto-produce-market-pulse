"""Build a self-contained report from synchronized README evidence."""
import base64
import re
from pathlib import Path
import markdown

ROOT = Path(__file__).parent
text = (ROOT / 'README.md').read_text(encoding='utf-8')

def embed(match):
    data = base64.b64encode((ROOT / match.group(2)).read_bytes()).decode('ascii')
    return f'![{match.group(1)}](data:image/png;base64,{data})'

text = re.sub(r'!\[([^]]*)\]\((outputs/img/[^)]+)\)', embed, text)
text = re.sub(r'(?<!!)\]\(outputs/', '](', text)
text = text.replace('](docs/', '](https://github.com/KushPatel29/toronto-produce-market-pulse/blob/main/docs/')
body = markdown.markdown(text, extensions=['tables', 'fenced_code'])
html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Toronto Produce Market Pulse</title>
<style>body{{font:16px/1.6 'Segoe UI',Arial,sans-serif;color:#16324f;background:white;margin:0}}
main{{max-width:1050px;margin:auto;padding:36px 24px}}h1{{font-size:34px;line-height:1.2}}h2{{margin-top:36px}}
a{{color:#26734d}}img{{max-width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow:auto}}
td,th{{padding:10px;text-align:left;border-bottom:1px solid #ccd5dc}}th{{background:#eef2f4}}pre{{padding:16px;background:#eef2f4;overflow:auto}}
p,li{{max-width:85ch}}code{{font-size:14px}}:focus-visible{{outline:3px solid #9c6500}}</style></head>
<body><main>{body}</main></body></html>'''
(ROOT / 'outputs/index.html').write_text(html, encoding='utf-8')
print('Historical report regenerated')
