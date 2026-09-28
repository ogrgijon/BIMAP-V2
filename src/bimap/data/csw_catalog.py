"""OGC Catalogue Service for the Web (CSW) client.

Provides a lightweight search interface against any CSW 2.0.2 endpoint —
returns discovered service records with their WFS / WMS access URLs.

No external OWSLib dependency; uses only ``requests`` + stdlib XML parsing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import requests

from bimap.config import HTTP_HEADERS

# ── Defaults ─────────────────────────────────────────────────────────────────
IDEE_CSW_URL = "https://www.idee.es/csw-inspire-idee/srv/spa/csw"

# XML namespaces
_NS = {
    "csw": "http://www.opengis.net/cat/csw/2.0.2",
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gmx": "http://www.isotc211.org/2005/gmx",
    "gco": "http://www.isotc211.org/2005/gco",
    "srv": "http://www.isotc211.org/2005/srv",
    "ows": "http://www.opengis.net/ows",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dct": "http://purl.org/dc/terms/",
    "xlink": "http://www.w3.org/1999/xlink",
}

# Register short prefixes so ET serialises them cleanly
for _prefix, _uri in _NS.items():
    ET.register_namespace(_prefix, _uri)


@dataclass
class CswRecord:
    """A single CSW discovery record."""

    title: str = ""
    abstract: str = ""
    identifier: str = ""
    service_type: str = ""          # WFS | WMS | WMTS | WCS | …
    access_url: str = ""            # direct service endpoint (if resolvable)
    record_url: str = ""            # link to the full metadata record
    bbox: tuple[float, float, float, float] | None = None   # (minx, miny, maxx, maxy)
    keywords: list[str] = field(default_factory=list)

    # ── Convenience ──────────────────────────────────────────────────────────

    def is_wfs(self) -> bool:
        return "WFS" in self.service_type.upper()

    def is_wms(self) -> bool:
        stype = self.service_type.upper()
        return "WMS" in stype or "WMTS" in stype


# ── GetRecords template ───────────────────────────────────────────────────────

_GET_RECORDS_TMPL = """\
<?xml version="1.0" encoding="UTF-8"?>
<csw:GetRecords xmlns:csw="http://www.opengis.net/cat/csw/2.0.2"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:gmd="http://www.isotc211.org/2005/gmd"
    service="CSW" version="2.0.2"
    resultType="results"
    startPosition="{start}"
    maxRecords="{max_records}"
    outputSchema="http://www.opengis.net/cat/csw/2.0.2"
    outputFormat="application/xml">
  <csw:Query typeNames="csw:Record">
    <csw:ElementSetName>full</csw:ElementSetName>
    {filter_xml}
  </csw:Query>
</csw:GetRecords>"""

_TEXT_FILTER_TMPL = """\
    <csw:Constraint version="1.1.0">
      <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
        <ogc:PropertyIsLike wildCard="*" singleChar="?" escapeChar="\\">
          <ogc:PropertyName>AnyText</ogc:PropertyName>
          <ogc:Literal>*{text}*</ogc:Literal>
        </ogc:PropertyIsLike>
      </ogc:Filter>
    </csw:Constraint>"""


def _build_get_records_body(
    text: str,
    max_records: int,
    start: int = 1,
) -> str:
    filter_xml = _TEXT_FILTER_TMPL.format(text=_escape_xml(text)) if text.strip() else ""
    return _GET_RECORDS_TMPL.format(
        start=start,
        max_records=max_records,
        filter_xml=filter_xml,
    )


def _escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )


# ── Record parsers ────────────────────────────────────────────────────────────

def _text(root: ET.Element, *tag_suffixes: str) -> str:
    """Find first element whose local name matches any suffix and return text."""
    for elem in root.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local in tag_suffixes and elem.text:
            return elem.text.strip()
    return ""


def _attr_href(elem: ET.Element) -> str:
    for attr, val in elem.attrib.items():
        if attr.endswith("}href") or attr == "href":
            return val
    return ""


def _parse_record(rec: ET.Element) -> CswRecord:
    """Parse a csw:Record or equivalent into a CswRecord."""
    cr = CswRecord()
    cr.title = _text(rec, "title", "Title")
    cr.abstract = _text(rec, "abstract", "Abstract", "description", "Description")
    cr.identifier = _text(rec, "identifier", "Identifier")

    # Service type from dc:type or keywords
    dtype = _text(rec, "type", "Type").upper()
    for candidate in ("WFS", "WMS", "WMTS", "WCS", "CSW"):
        if candidate in dtype:
            cr.service_type = candidate
            break
    if not cr.service_type:
        # Try keywords
        for elem in rec.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "subject" and elem.text:
                for kw in elem.text.upper().split():
                    for candidate in ("WFS", "WMS", "WMTS", "WCS"):
                        if candidate in kw:
                            cr.service_type = candidate
                            break

    # URI / access URL
    for elem in rec.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local in ("URI", "references", "relation"):
            href = _attr_href(elem) or (elem.text or "").strip()
            if href.startswith("http") and "?" not in href:
                cr.access_url = href
                break
            elif href.startswith("http"):
                cr.access_url = href.split("?")[0]
                break

    # Bounding box  (ows:BoundingBox or dc:spatial)
    for elem in rec.iter():
        local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if local == "BoundingBox":
            lower = _find_child_text(elem, "LowerCorner")
            upper = _find_child_text(elem, "UpperCorner")
            if lower and upper:
                try:
                    lc = [float(v) for v in lower.split()]
                    uc = [float(v) for v in upper.split()]
                    cr.bbox = (lc[0], lc[1], uc[0], uc[1])
                except (ValueError, IndexError):
                    pass

    return cr


def _find_child_text(parent: ET.Element, local_name: str) -> str:
    for child in parent:
        local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if local == local_name and child.text:
            return child.text.strip()
    return ""


# ── Public API ────────────────────────────────────────────────────────────────

class CswCatalog:
    """Simple CSW 2.0.2 catalogue client.

    Usage::

        cat = CswCatalog("https://www.idee.es/csw-inspire-idee/srv/spa/csw")
        records = cat.search("transporte ferroviario", max_records=10)
        for r in records:
            print(r.title, r.service_type, r.access_url)
    """

    def __init__(self, url: str = IDEE_CSW_URL) -> None:
        self._url = url.rstrip("?& ")

    # ── Public methods ────────────────────────────────────────────────────────

    def search(
        self,
        text: str = "",
        max_records: int = 20,
        start: int = 1,
    ) -> list[CswRecord]:
        """POST a GetRecords request and return matching records.

        Parameters
        ----------
        text:
            Free-text search string (AnyText LIKE %text%).  Empty = no filter.
        max_records:
            Maximum number of records to retrieve per call.
        start:
            Start position for paging (1-based).
        """
        body = _build_get_records_body(text, max_records, start)
        headers = {**HTTP_HEADERS, "Content-Type": "application/xml; charset=UTF-8"}
        try:
            resp = requests.post(self._url, data=body.encode(), headers=headers, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"CSW search failed: {exc}") from exc

        return self._parse_response(resp.text)

    def get_capabilities(self) -> dict[str, Any]:
        """Retrieve basic service info from GetCapabilities."""
        params = {"SERVICE": "CSW", "VERSION": "2.0.2", "REQUEST": "GetCapabilities"}
        try:
            resp = requests.get(
                self._url, params=params, headers=HTTP_HEADERS, timeout=15
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"CSW GetCapabilities failed: {exc}") from exc
        info: dict[str, Any] = {}
        try:
            root = ET.fromstring(resp.text)
            info["title"] = _text(root, "Title")
            info["abstract"] = _text(root, "Abstract")
        except ET.ParseError:
            pass
        return info

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(xml_text: str) -> list[CswRecord]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        records: list[CswRecord] = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "Record":
                records.append(_parse_record(elem))
        return records
