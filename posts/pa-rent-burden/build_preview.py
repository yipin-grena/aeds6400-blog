"""Render a local, self-contained review copy. Does not touch published docs."""
import argparse
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

POST=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--quarto',default='quarto');args=p.parse_args()
with tempfile.TemporaryDirectory(prefix='aeds6400-blog5-') as directory:
 work=Path(directory)
 shutil.copytree(POST/'results',work/'results')
 source=(POST/'index.qmd').read_text().replace('draft: true','draft: false')
 # A local review copy should not display Quarto's default "Published" label.
 source=re.sub(r'^date: .*\n', '', source, flags=re.MULTILINE)
 source=source.replace('Rent competes with groceries',
  '<div class="draft-note">Unpublished draft for review</div>\n\nRent competes with groceries',1)
 (work/'index.qmd').write_text(source)
 (work/'_quarto.yml').write_text('''project:
  type: default
format:
  html:
    theme: cosmo
    embed-resources: true
    toc: false
    title-block-banner: "#173f49"
    css: preview.css
''')
 (work/'preview.css').write_text('''body{font-size:18px;line-height:1.7;color:#223841;background:#fffefa}main{max-width:880px;margin:auto}.quarto-title-banner{padding:2.7rem 0}.quarto-title-banner,.quarto-title-banner h1,.quarto-title-banner .description,.quarto-title-banner .quarto-category{color:#fff!important}.quarto-title-banner .quarto-category{border-color:#a8c6ca!important}.draft-note{padding:.65rem 1rem;margin:1rem 0 1.5rem;background:#e7f1ee;border-left:4px solid #387f85;font-size:.92rem;font-weight:600}figcaption{font-size:.9rem;color:#53676f}figure{margin:2rem 0}a{color:#1e687c}''')
 subprocess.run([args.quarto,'render','index.qmd','--output','Blog-Post-5.html'],cwd=work,check=True)
 target=POST/'preview';target.mkdir(exist_ok=True)
 shutil.copy2(work/'Blog-Post-5.html',target/'Blog-Post-5.html')
 print(target/'Blog-Post-5.html')
