from datetime import datetime
from types import SimpleNamespace

from dashboard import theme


def test_header_html_has_title_and_time():
    h = theme.header_html(now=lambda: datetime(2026, 11, 7, 21, 30))
    assert "Faceless Video AI" in h and "System online" in h and "21:30" in h


def test_inject_theme_css_sidebar_brand_and_header(monkeypatch):
    main, side = [], []
    monkeypatch.setattr(theme.st, "markdown", lambda body, **kw: main.append(body))
    monkeypatch.setattr(theme.st, "sidebar", SimpleNamespace(markdown=lambda body, **kw: side.append(body)))
    theme.inject_theme()
    assert len(main) == 2 and main[0].startswith("<style>") and len(side) == 1 and "sb-brand" in side[0]
    main.clear()
    theme.inject_theme(show_header=False)
    assert len(main) == 1


def test_css_keeps_sidebar_visible():
    assert 'stSidebar"][aria-expanded="false"]' in theme.CSS and "transform: none" in theme.CSS
