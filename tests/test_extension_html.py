from __future__ import annotations

import json
from types import SimpleNamespace

from bimap.ui.dialogs import extension_viewer_dialog
from bimap.ui.dialogs.extension_editor_dialog import _serialize_script_data


def test_script_data_escapes_html_script_terminators():
    payload = {"metadata": {"label": "</script><script>alert(1)</script>"}}

    serialized = _serialize_script_data(payload)

    assert "</script>" not in serialized
    assert json.loads(serialized) == payload


def test_rendered_extension_keeps_payload_inside_script(monkeypatch):
    element = SimpleNamespace(extension_html="<html><head></head><body></body></html>")
    payload = {"metadata": {"label": "</script><script>alert(1)</script>"}}
    monkeypatch.setattr(
        extension_viewer_dialog,
        "_build_data_payload",
        lambda _element, _etype: payload,
    )

    rendered = extension_viewer_dialog._build_rendered_html(element, "zone")

    assert rendered.count("</script>") == 1
    assert r"\u003c/script>" in rendered
