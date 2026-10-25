"""Build a self-contained local HTML review copy of Blog Post 7.

Render in a temporary standalone Quarto project so the website and its published
``docs/`` directory are never rebuilt. The calling environment, including
``R_LIBS_USER``, is inherited unchanged.
"""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


POST = Path(__file__).resolve().parent
OUTPUT_NAME = "Blog-Post-7.html"
RSTUDIO_QUARTO = Path(
    "/Applications/RStudio.app/Contents/Resources/app/quarto/bin/quarto"
)

PREVIEW_CONFIG = """project:
  type: default
language:
  title-block-published: "Draft date"
format:
  html:
    theme: cosmo
    embed-resources: true
    toc: false
    title-block-banner: "#173f49"
    css: preview.css
    code-overflow: scroll
"""

PREVIEW_CSS = """body{font-size:18px;line-height:1.7;color:#223841;background:#fffefa}
main{max-width:880px;margin:auto;min-width:0}
.quarto-title-banner{padding:2.7rem 0}
.quarto-title-banner,.quarto-title-banner h1,.quarto-title-banner .description,
.quarto-title-banner .quarto-category{color:#fff!important}
.quarto-title-banner .quarto-category{border-color:#a8c6ca!important}
.draft-note{padding:.65rem 1rem;margin:1rem 0 1.5rem;background:#e7f1ee;
border-left:4px solid #387f85;font-size:.92rem;font-weight:600}
figcaption{font-size:.9rem;color:#53676f}
figure{margin:2rem 0}a{color:#1e687c}h2{margin-top:2.2rem}
pre{font-size:.83rem;line-height:1.55}table{font-size:.92rem}
.cell{min-width:0;max-width:100%}.cell-output-display{overflow-x:auto}
@media(max-width:600px){
body{font-size:16px}
#quarto-content{display:block;margin:0 18px}
main{width:100%;max-width:100%}
table{font-size:.8rem;table-layout:fixed;width:100%}
td code{white-space:normal;overflow-wrap:anywhere}
.math.display{display:block;overflow-x:auto}
}
"""


def preview_source(source):
    """Render either source status locally without changing the article itself."""
    front_matter = re.match(r"\A---\s*\n(.*?)\n---[ \t]*\n?", source, re.DOTALL)
    if front_matter is None:
        raise ValueError("index.qmd must begin with YAML front matter")
    original_header = front_matter.group(1)
    draft_entries = re.findall(r"^draft:[^\n]*$", original_header, flags=re.MULTILINE)
    if len(draft_entries) != 1:
        raise ValueError("Keep exactly one boolean 'draft: true' or 'draft: false' entry in index.qmd")
    header, replacements = re.subn(
        r"^draft:[ \t]*(?:true|false)[ \t]*$",
        "draft: false",
        original_header,
        flags=re.MULTILINE,
    )
    if replacements != 1:
        raise ValueError("Keep exactly one boolean 'draft: true' or 'draft: false' entry in index.qmd")
    # Standalone files have no website listing. Omit only the preview's category
    # navigation so Quarto does not try to fetch a nonexistent listings.json.
    header = re.sub(r"^categories:[^\n]*$", "", header, flags=re.MULTILINE)
    body = source[front_matter.end() :]
    # The output is one folder below these source files. Keep its download links
    # usable without changing the links in the article destined for the website.
    for filename in (path.name for path in POST.iterdir() if path.is_file()):
        if Path(filename).suffix.lower() in {".md", ".r", ".py", ".qmd"}:
            body = body.replace(f"]({filename})", f"](../{filename})")
    return (
        "---\n"
        + header
        + '\n---\n\n<div class="draft-note" role="note">'
        + "Unpublished draft for review</div>\n\n"
        + body
    )


def main():
    default_quarto = shutil.which("quarto")
    if default_quarto is None and RSTUDIO_QUARTO.is_file():
        default_quarto = str(RSTUDIO_QUARTO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarto", default=default_quarto or "quarto")
    args = parser.parse_args()

    source = preview_source((POST / "index.qmd").read_text(encoding="utf-8"))
    if not (POST / "results").is_dir():
        raise FileNotFoundError("Run the post's analysis first to create results/")
    with tempfile.TemporaryDirectory(prefix="aeds6400-blog7-") as directory:
        work = Path(directory)
        shutil.copytree(POST / "results", work / "results")
        for folder in ("R", "config"):
            shutil.copytree(POST / folder, work / folder)
        for path in POST.iterdir():
            if path.is_file() and path.suffix.lower() in {".r", ".js", ".css"}:
                shutil.copy2(path, work / path.name)
        (work / "index.qmd").write_text(source, encoding="utf-8")
        (work / "_quarto.yml").write_text(PREVIEW_CONFIG, encoding="utf-8")
        (work / "preview.css").write_text(PREVIEW_CSS, encoding="utf-8")
        subprocess.run(
            [args.quarto, "render", "index.qmd", "--output", OUTPUT_NAME],
            cwd=work,
            check=True,
        )
        target = POST / "preview"
        target.mkdir(exist_ok=True)
        shutil.copy2(work / OUTPUT_NAME, target / OUTPUT_NAME)
    print(target / OUTPUT_NAME)


if __name__ == "__main__":
    main()
