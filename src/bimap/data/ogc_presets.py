"""Curated list of public Spanish OGC WFS services.

Each entry is a dict with:
  type    – "WFS"
  name    – human-readable service name
  url     – base service URL (no query-string)
  notes   – short description shown in the picker
"""

from __future__ import annotations

PRESET_SERVICES: list[dict[str, str]] = [
    # ── IGN (Instituto Geográfico Nacional) ───────────────────────────────────
    {
        "type": "WFS",
        "name": "IGN — Topographic features (WFS)",
        "url": "https://www.ign.es/wfs-inspire/ign-base",
        "notes": "Roads, buildings, hydrography, boundaries",
    },
    # ── Catastro ──────────────────────────────────────────────────────────────
    {
        "type": "WFS",
        "name": "Catastro — Inspire parcels (WFS)",
        "url": "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx",
        "notes": "Cadastral parcel polygons (INSPIRE CadastralParcel)",
    },
    # ── IGME (Instituto Geológico y Minero) ───────────────────────────────────
    {
        "type": "WFS",
        "name": "IGME — Litología (WFS)",
        "url": "https://mapas.igme.es/gis/services/BasesDatos/IGME_Litologia_200/MapServer/WFSServer",
        "notes": "Lithology features as vectors",
    },
]
