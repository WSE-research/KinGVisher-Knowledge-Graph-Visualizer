"""Unit tests for util.py — the importable logic of the KinGVisher app.

These cover the pure / file-based helpers so that dependency upgrades
(Pillow, Markdown, requests, …) are validated automatically by CI.
"""
import base64
from io import BytesIO

from PIL import Image

import util


def _png_bytes(width=10, height=20, color=(255, 0, 0)):
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


# --- get_size_of_image -------------------------------------------------------
def test_get_size_of_image_returns_width_and_height():
    img = Image.new("RGB", (30, 40))
    assert util.get_size_of_image(img) == {"width": 30, "height": 40}


# --- im_2_b64 ----------------------------------------------------------------
def test_im_2_b64_roundtrips_to_a_valid_png():
    img = Image.new("RGB", (4, 4), (0, 128, 255))
    encoded = util.im_2_b64(img)
    decoded = base64.b64decode(encoded)
    restored = Image.open(BytesIO(decoded))
    assert restored.format == "PNG"
    assert restored.size == (4, 4)


# --- copy_file ---------------------------------------------------------------
def test_copy_file_duplicates_content(tmp_path):
    src = tmp_path / "src.txt"
    dest = tmp_path / "dest.txt"
    src.write_text("hello world", encoding="utf-8")
    util.copy_file(str(src), str(dest))
    assert dest.read_text(encoding="utf-8") == "hello world"


# --- save_uploaded_file ------------------------------------------------------
def test_save_uploaded_file_writes_image_and_returns_size(tmp_path):
    uploaded = BytesIO(_png_bytes(12, 8))
    target = tmp_path / "uploaded.png"
    size = util.save_uploaded_file(str(target), uploaded)
    assert target.exists()
    assert size == {"width": 12, "height": 8}


# --- download_image (network mocked) -----------------------------------------
def test_download_image_saves_remote_image(tmp_path, monkeypatch):
    class _FakeResponse:
        raw = BytesIO(_png_bytes(7, 9))

    monkeypatch.setattr(util.requests, "get", lambda url, stream: _FakeResponse())
    target = tmp_path / "downloaded.png"
    size = util.download_image("http://example.org/x.png", str(target))
    assert target.exists()
    assert size == {"width": 7, "height": 9}


# --- include_css -------------------------------------------------------------
def test_include_css_concatenates_files_into_a_style_tag(tmp_path):
    a = tmp_path / "a.css"
    b = tmp_path / "b.css"
    a.write_text("body{color:red}", encoding="utf-8")
    b.write_text(".x{margin:0}", encoding="utf-8")

    captured = {}

    class _FakeSt:
        def markdown(self, html, unsafe_allow_html=False):
            captured["html"] = html
            captured["unsafe"] = unsafe_allow_html

    util.include_css(_FakeSt(), [str(a), str(b)])
    assert captured["unsafe"] is True
    assert "body{color:red}" in captured["html"]
    assert ".x{margin:0}" in captured["html"]
    assert captured["html"].startswith("<style>")


# --- replace_index_html + replace_values_in_index_html -----------------------
DEFAULT_INDEX_HTML = (
    "<head><link rel=\"shortcut icon\" href=\"./favicon.png\"/></head>"
    "<title>Streamlit</title>"
    "<noscript>You need to enable JavaScript to run this app.</noscript>"
)


class _FakeStreamlitModule:
    """Mimics the `streamlit` module: only `__file__` is used by the code."""

    def __init__(self, pkg_dir):
        self.__file__ = str(pkg_dir / "__init__.py")


def _make_streamlit_layout(tmp_path):
    pkg = tmp_path / "streamlit_pkg"
    static = pkg / "static"
    static.mkdir(parents=True)
    (static / "index.html").write_text(DEFAULT_INDEX_HTML, encoding="utf-8")
    return pkg, static / "index.html"


def test_replace_values_in_index_html_rewrites_title_and_meta(tmp_path):
    pkg, index_html = _make_streamlit_layout(tmp_path)
    icon = tmp_path / "icon.png"
    icon.write_bytes(_png_bytes(64, 64))
    fake_st = _FakeStreamlitModule(pkg)

    util.replace_values_in_index_html(
        fake_st,
        activate=True,
        new_title="KinGVisher",
        new_meta_description="A KG visualizer",
        new_noscript_content="enable js please",
        canonical_url="https://wse-research.org/KinGVisher/",
        page_icon_with_path=str(icon),
        additional_html_head_content="<meta name='x' content='y'/>",
    )

    result = index_html.read_text(encoding="utf-8")
    assert "<title>KinGVisher</title>" in result
    assert '<meta name="description" content="A KG visualizer"/>' in result
    assert '<link rel="canonical" href="https://wse-research.org/KinGVisher/"/>' in result
    assert "<meta name='x' content='y'/>" in result
    # favicon placeholder must have been replaced by an embedded data URI
    assert "./favicon.png" not in result
    assert "data:image/png;base64," in result


def test_replace_values_in_index_html_is_a_noop_when_not_activated(tmp_path):
    pkg, index_html = _make_streamlit_layout(tmp_path)
    fake_st = _FakeStreamlitModule(pkg)
    util.replace_values_in_index_html(fake_st, activate=False, new_title="ignored")
    assert index_html.read_text(encoding="utf-8") == DEFAULT_INDEX_HTML
