"""Regression test: a Jinja syntax error (e.g. invalid escaping inside a
{{ }} expression) only surfaces the first time a template is actually
requested, since Jinja compiles lazily. That let a broken onsubmit=confirm(...)
expression in video_detail.html ship and pass the full test suite while
still 500-ing on every real request. Compile every template up front so a
syntax error fails CI instead of production.
"""
from pathlib import Path

from app.web.main import templates

TEMPLATES_DIR = Path(__file__).parent.parent / "app" / "web" / "templates"


def test_all_templates_compile():
    names = [p.name for p in TEMPLATES_DIR.glob("*.html")]
    assert names, "no templates found — check TEMPLATES_DIR"
    for name in names:
        templates.env.get_template(name)  # raises TemplateSyntaxError if broken
