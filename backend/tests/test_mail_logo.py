"""BIMI gönderen logosu: SVG doğrulama ve Tiny PS uyarlaması."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes.mail_logo import sanitize_svg, bimi_record  # noqa: E402

OK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100"><rect width="100" height="100" fill="#d71920"/></svg>'


def test_valid_svg_is_converted_to_tiny_ps():
    out = sanitize_svg(OK, "GarajTek")
    assert 'baseProfile="tiny-ps"' in out and 'version="1.2"' in out
    assert "<title>GarajTek</title>" in out
    assert 'width="100" height="100" fill' in out  # rect korunur
    assert '<svg' in out and 'width="100" height="100" viewBox' not in out


@pytest.mark.parametrize("bad", [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><script>alert(1)</script></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" onload="x()"></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><image href="http://e.com/a.png"/></svg>',
    '<!DOCTYPE svg [<!ENTITY a "b">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"></svg>',
    '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    '<html></html>',
    'not xml',
])
def test_rejects_unsafe_or_invalid(bad):
    with pytest.raises(HTTPException):
        sanitize_svg(bad)


def test_bimi_record():
    r = bimi_record("https://garajtek.com/api/bimi/logo.svg")
    assert r == {"type": "TXT", "name": "default._bimi", "value": "v=BIMI1; l=https://garajtek.com/api/bimi/logo.svg;"}
