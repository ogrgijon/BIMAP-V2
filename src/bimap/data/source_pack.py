"""Source Pack — shareable XML bundles of pre-configured data sources.

A *Source Pack* is a single ``.bsp`` (or ``.xml``) file that a community
member can author and distribute.  Each pack contains one or more *source
entries*, each of which describes a ready-to-use data source (WFS, REST API,
GeoJSON, CSV URL, …) together with its default connection parameters and a
declaration of which parameters the end-user is expected to fill in or
customise.

──────────────────────────────────────────────────────────────────────────────
XML format  (schema version 1)
──────────────────────────────────────────────────────────────────────────────

<?xml version="1.0" encoding="UTF-8"?>
<source-pack version="1" xmlns="urn:bimap:source-pack:1">

  <meta>
    <name>Spain Open Data</name>
    <author>IDEE / IGN</author>
    <description>Open geospatial services from Spain's SDI (IDEE)</description>
    <version>1.0.0</version>
    <url>https://www.idee.es</url>
    <license>OGL</license>
  </meta>

  <sources>
    <source id="ign-transport" type="wfs" name="Transport Network (IGN)"
            category="Infrastructure">
      <description>Spanish road and rail transport WFS (INSPIRE)</description>
      <tags>transport,roads,rail,Spain,INSPIRE</tags>
      <connection>
        <!-- fixed="true"  → shown read-only; user cannot change it        -->
        <!-- fixed="false" → shown as editable field in the import dialog  -->
        <param name="url"
               value="https://servicios.idee.es/wfs-inspire/redes-transporte"
               fixed="true"/>
        <param name="type_name"
               value="TN-RoadTransportNetwork:RoadLink"
               fixed="true"/>
        <param name="max_features" value="500"  fixed="false"
               label="Max Features" type="int" min="1" max="5000"/>
        <param name="bbox"         value=""     fixed="false"
               label="Bounding Box (minx,miny,maxx,maxy)" type="string"/>
        <param name="cql_filter"   value=""     fixed="false"
               label="CQL Filter" type="string"/>
      </connection>
    </source>

    <source id="idee-buildings" type="wfs" name="Buildings (INSPIRE)"
            category="Urban">
      <description>INSPIRE building footprints from IDEE</description>
      <tags>buildings,urban,cadastre,Spain</tags>
      <connection>
        <param name="url"
               value="https://servicios.idee.es/wfs-inspire/edificios"
               fixed="true"/>
        <param name="type_name" value="BU.Building" fixed="true"/>
        <param name="max_features" value="200" fixed="false"
               label="Max Features" type="int" min="1" max="2000"/>
        <param name="bbox" value="" fixed="false"
               label="Bounding Box" type="string"/>
      </connection>
    </source>
  </sources>

</source-pack>

──────────────────────────────────────────────────────────────────────────────
Public API
──────────────────────────────────────────────────────────────────────────────

    pack = SourcePack.load(path)
    for entry in pack.sources:
        print(entry.name, entry.source_type, entry.category)

    # Build a DataSource model (user-supplied values merged into defaults)
    ds = entry.build_data_source({"max_features": "100"})

    # Persist a pack
    SourcePack.save(pack, path)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bimap.models.data_source import DataSource, SourceType

# ── XML namespace ─────────────────────────────────────────────────────────────
_NS = "urn:bimap:source-pack:1"
_NS_PREFIX = f"{{{_NS}}}"

ET.register_namespace("", _NS)


# ── Parameter descriptor ──────────────────────────────────────────────────────

@dataclass
class PackParam:
    """Describes a single connection parameter inside a source entry.

    Attributes
    ----------
    name:
        Internal parameter key (matches ``DataSource.connection`` dict key).
    value:
        Default / preset value.
    fixed:
        If ``True``, the parameter is locked and shown read-only to the user.
        If ``False``, the user can override it in the import dialog.
    label:
        Human-readable label for the form field (falls back to ``name``).
    param_type:
        One of ``"string"``, ``"int"``, ``"float"``, ``"password"``.
    min_value / max_value:
        Optional numeric constraints (only meaningful for int/float).
    """

    name: str
    value: str = ""
    fixed: bool = True
    label: str = ""
    param_type: str = "string"    # string | int | float | password
    min_value: str = ""
    max_value: str = ""

    @property
    def display_label(self) -> str:
        return self.label or self.name


# ── Source entry ──────────────────────────────────────────────────────────────

@dataclass
class PackSourceEntry:
    """A single pre-configured data source inside a Source Pack.

    Attributes
    ----------
    id:
        Unique stable identifier within the pack (e.g. ``"ign-transport"``).
    name:
        Human-readable display name.
    source_type:
        One of the ``SourceType`` enum values (``"wfs"``, ``"rest_api"``, …).
    category:
        Optional grouping category (e.g. ``"Infrastructure"``, ``"Urban"``).
    description:
        Long-form description shown in the import dialog.
    tags:
        Comma-separated keyword list for filtering.
    params:
        Ordered list of ``PackParam`` objects.
    """

    id: str
    name: str
    source_type: str                          # raw string — validated lazily
    category: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    params: list[PackParam] = field(default_factory=list)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def editable_params(self) -> list[PackParam]:
        """Return only the params the user can configure."""
        return [p for p in self.params if not p.fixed]

    def fixed_connection(self) -> dict[str, str]:
        """Return the hardwired connection values (fixed=True params)."""
        return {p.name: p.value for p in self.params if p.fixed}

    def default_connection(self) -> dict[str, str]:
        """Return all params with their default values."""
        return {p.name: p.value for p in self.params}

    def build_data_source(
        self,
        user_values: dict[str, str] | None = None,
        custom_name: str = "",
    ) -> DataSource:
        """Merge user-supplied values with defaults and return a ``DataSource``.

        Parameters
        ----------
        user_values:
            Dict of ``{param_name: value}`` entered by the user in the dialog.
            Only non-fixed params should be supplied here, but extras are
            silently ignored for fixed ones.
        custom_name:
            Override the datasource ``name``; defaults to ``self.name``.
        """
        conn = self.default_connection()
        if user_values:
            for key, val in user_values.items():
                if key in conn:
                    conn[key] = val
        # Validate source type
        try:
            stype = SourceType(self.source_type)
        except ValueError:
            stype = SourceType.REST_API
        return DataSource(
            name=custom_name or self.name,
            source_type=stype,
            connection=conn,
        )

    def matches_filter(self, text: str) -> bool:
        """Case-insensitive substring match across name, description, tags."""
        low = text.lower()
        return (
            low in self.name.lower()
            or low in self.description.lower()
            or any(low in tag.lower() for tag in self.tags)
            or low in self.category.lower()
        )


# ── Pack metadata ─────────────────────────────────────────────────────────────

@dataclass
class SourcePackMeta:
    name: str = "Unnamed Pack"
    author: str = ""
    description: str = ""
    version: str = "1.0.0"
    url: str = ""
    license: str = ""


# ── Source Pack ───────────────────────────────────────────────────────────────

@dataclass
class SourcePack:
    """A collection of pre-configured data sources that can be shared as XML.

    Usage::

        pack = SourcePack.load("spain_open_data.bsp")
        for entry in pack.sources:
            ds = entry.build_data_source({"max_features": "100"})
    """

    meta: SourcePackMeta = field(default_factory=SourcePackMeta)
    sources: list[PackSourceEntry] = field(default_factory=list)

    # ── I/O ───────────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> "SourcePack":
        """Parse a ``.bsp`` / ``.xml`` file.  Raises ``ValueError`` on error."""
        path = Path(path)
        try:
            tree = ET.parse(path)
        except (ET.ParseError, OSError) as exc:
            raise ValueError(f"Cannot read source pack: {exc}") from exc
        return cls._from_element(tree.getroot())

    @classmethod
    def loads(cls, xml_text: str) -> "SourcePack":
        """Parse from an XML string."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError(f"Invalid source pack XML: {exc}") from exc
        return cls._from_element(root)

    @staticmethod
    def save(pack: "SourcePack", path: str | Path) -> None:
        """Serialise *pack* to a ``.bsp`` XML file."""
        root = SourcePack._to_element(pack)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(str(path), encoding="utf-8", xml_declaration=True)

    # ── XML ↔ model helpers ───────────────────────────────────────────────────

    @classmethod
    def _from_element(cls, root: ET.Element) -> "SourcePack":
        pack = cls()
        # Strip namespace prefix helper
        def local(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        for child in root:
            tag = local(child.tag)
            if tag == "meta":
                pack.meta = _parse_meta(child, local)
            elif tag == "sources":
                for src_el in child:
                    if local(src_el.tag) == "source":
                        entry = _parse_source(src_el, local)
                        pack.sources.append(entry)
        return pack

    @staticmethod
    def _to_element(pack: "SourcePack") -> ET.Element:
        root = ET.Element(f"{_NS_PREFIX}source-pack", {"version": "1"})
        # meta
        meta_el = ET.SubElement(root, f"{_NS_PREFIX}meta")
        _sub_text(meta_el, "name", pack.meta.name)
        _sub_text(meta_el, "author", pack.meta.author)
        _sub_text(meta_el, "description", pack.meta.description)
        _sub_text(meta_el, "version", pack.meta.version)
        _sub_text(meta_el, "url", pack.meta.url)
        _sub_text(meta_el, "license", pack.meta.license)
        # sources
        sources_el = ET.SubElement(root, f"{_NS_PREFIX}sources")
        for entry in pack.sources:
            src_el = ET.SubElement(
                sources_el,
                f"{_NS_PREFIX}source",
                {
                    "id": entry.id,
                    "type": entry.source_type,
                    "name": entry.name,
                    "category": entry.category,
                },
            )
            _sub_text(src_el, "description", entry.description)
            _sub_text(src_el, "tags", ",".join(entry.tags))
            conn_el = ET.SubElement(src_el, f"{_NS_PREFIX}connection")
            for p in entry.params:
                attribs: dict[str, Any] = {
                    "name": p.name,
                    "value": p.value,
                    "fixed": "true" if p.fixed else "false",
                }
                if p.label:
                    attribs["label"] = p.label
                if p.param_type != "string":
                    attribs["type"] = p.param_type
                if p.min_value:
                    attribs["min"] = p.min_value
                if p.max_value:
                    attribs["max"] = p.max_value
                ET.SubElement(conn_el, f"{_NS_PREFIX}param", attribs)
        return root


# ── XML parse helpers ─────────────────────────────────────────────────────────

def _parse_meta(el: ET.Element, local: Any) -> SourcePackMeta:
    meta = SourcePackMeta()
    for child in el:
        tag = local(child.tag)
        text = (child.text or "").strip()
        if tag == "name":
            meta.name = text
        elif tag == "author":
            meta.author = text
        elif tag == "description":
            meta.description = text
        elif tag == "version":
            meta.version = text
        elif tag == "url":
            meta.url = text
        elif tag == "license":
            meta.license = text
    return meta


def _parse_source(el: ET.Element, local: Any) -> PackSourceEntry:
    entry = PackSourceEntry(
        id=el.get("id", ""),
        name=el.get("name", ""),
        source_type=el.get("type", "rest_api"),
        category=el.get("category", ""),
    )
    for child in el:
        tag = local(child.tag)
        text = (child.text or "").strip()
        if tag == "description":
            entry.description = text
        elif tag == "tags":
            entry.tags = [t.strip() for t in text.split(",") if t.strip()]
        elif tag == "connection":
            for param_el in child:
                if local(param_el.tag) == "param":
                    entry.params.append(_parse_param(param_el))
    return entry


def _parse_param(el: ET.Element) -> PackParam:
    fixed_raw = el.get("fixed", "true").lower()
    return PackParam(
        name=el.get("name", ""),
        value=el.get("value", ""),
        fixed=fixed_raw not in ("false", "0", "no"),
        label=el.get("label", ""),
        param_type=el.get("type", "string"),
        min_value=el.get("min", ""),
        max_value=el.get("max", ""),
    )


def _sub_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, f"{_NS_PREFIX}{tag}")
    el.text = text
    return el
