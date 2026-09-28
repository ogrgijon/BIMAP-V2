"""
PDF renderer — generates a PDF from a Project using Qt's QPdfWriter (no ReportLab).

The render pipeline:
1.  Create a QPdfWriter targeted at the output file.
2.  Set page size and resolution.
3.  Open a QPainter on the writer.
4.  Draw tiles to the map frame region.
5.  Draw zones / keypoints / annotations as vector graphics.
6.  Add title block, legend, keynote table.
7.  End the painter (saves the PDF automatically).
"""

from __future__ import annotations

import math
import os
from datetime import date
from pathlib import Path
from typing import Any

from bimap.config import TILE_PROVIDERS, TILE_SIZE
from bimap.engine.tile_math import lat_lon_to_pixel, meters_per_pixel, visible_tiles
from bimap.models.pdf_layout import LayoutItemType, PageOrientation, PDFLayout
from bimap.models.project import Project
from bimap.i18n import t


from bimap.config import PDF_PAGE_SIZES_MM as _PAGE_SIZE_MM


def render_pdf(project: Project, output_path: str) -> None:
    """Main entry: render project to output_path (.pdf) using QPdfWriter."""
    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtCore import QMarginsF, QSizeF
    from PyQt6.QtGui import QPainter, QPageLayout, QPageSize, QPdfWriter

    layout = project.pdf_layout
    w_mm, h_mm = _PAGE_SIZE_MM.get(layout.page_size, _PAGE_SIZE_MM["A4"])
    if layout.orientation == PageOrientation.LANDSCAPE:
        w_mm, h_mm = h_mm, w_mm

    dpi = layout.dpi
    writer = QPdfWriter(output_path)
    writer.setTitle(project.name)
    writer.setResolution(dpi)
    writer.setPageLayout(QPageLayout(
        QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter),
        QPageLayout.Orientation.Portrait,
        QMarginsF(0, 0, 0, 0),
        QPageLayout.Unit.Millimeter,
    ))

    pw = int(w_mm / 25.4 * dpi)
    ph = int(h_mm / 25.4 * dpi)

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    _render_page(painter, project, pw, ph, dpi)
    painter.end()


def _render_page(
    painter: Any, project: Project, pw: int, ph: int, dpi: int
) -> None:
    """Render all page content onto an already-open QPainter (PDF writer or printer)."""
    layout = project.pdf_layout
    margin = int(layout.margin / 72.0 * dpi)
    tb_h = _tb_height_px(pw, margin, dpi, layout.tb_enabled)

    frame = _find_item(layout, LayoutItemType.MAP_FRAME)
    if frame:
        pt_to_px = dpi / 72.0
        fx = int(frame.rect.x * pt_to_px)
        fy = int(frame.rect.y * pt_to_px)
        fw = int(frame.rect.width * pt_to_px)
        fh = int(frame.rect.height * pt_to_px)
        center_lat = frame.map_center_lat or project.map_state.center_lat
        center_lon = frame.map_center_lon or project.map_state.center_lon
        zoom = frame.map_zoom or project.map_state.zoom
    else:
        fx, fy = margin, margin
        fw = pw - 2 * margin
        fh = ph - 2 * margin - tb_h
        center_lat = project.map_state.center_lat
        center_lon = project.map_state.center_lon
        zoom = project.map_state.zoom

    if layout.capture_zoom is not None:
        zoom = layout.capture_zoom

    _render_map_frame(painter, project, fx, fy, fw, fh, center_lat, center_lon, zoom)
    _render_vector_overlays(painter, project, fx, fy, fw, fh, center_lat, center_lon, zoom, dpi)
    _render_title_block(painter, project, pw, ph, margin, dpi)
    if not layout.tb_enabled and layout.show_legend and project.zones:
        _render_floating_legend(painter, project, pw, ph, margin, dpi)
    _render_info_box(painter, project, pw, ph, margin, dpi)
    _render_keynote_table(painter, project, pw, ph, margin, dpi)


# ── Map frame ─────────────────────────────────────────────────────────────────

def _render_map_frame(
    painter: Any,
    project: Project,
    fx: int, fy: int, fw: int, fh: int,
    center_lat: float, center_lon: float, zoom: int,
) -> None:
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QPixmap
    import requests
    from bimap.config import HTTP_HEADERS
    from bimap.ui.map_canvas.tile_fetcher import get_tile_cache

    url_template = TILE_PROVIDERS.get(project.map_state.tile_provider, TILE_PROVIDERS["osm_standard"])["url"]
    cache = get_tile_cache()

    tiles = visible_tiles(center_lat, center_lon, zoom, fw, fh)
    for tile_coord, px, py in tiles:
        key = f"{url_template}_{tile_coord.z}_{tile_coord.x}_{tile_coord.y}"
        data = cache.get(key)
        if not data:
            url = (url_template
                   .replace("{z}", str(tile_coord.z))
                   .replace("{x}", str(tile_coord.x))
                   .replace("{y}", str(tile_coord.y)))
            try:
                resp = requests.get(url, headers=HTTP_HEADERS, timeout=8)
                if resp.ok:
                    data = resp.content
                    cache.put(key, data)
            except Exception:
                continue
        if data:
            pm = QPixmap()
            pm.loadFromData(data)
            if not pm.isNull():
                painter.drawPixmap(fx + px, fy + py, pm)


# ── Vector overlays ───────────────────────────────────────────────────────────

def _render_vector_overlays(
    painter: Any,
    project: Project,
    fx: int, fy: int, fw: int, fh: int,
    center_lat: float, center_lon: float, zoom: int,
    dpi: int,
) -> None:
    from PyQt6.QtCore import QPointF, QRectF
    from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen

    def ll_to_pt(lat: float, lon: float) -> tuple[float, float]:
        p = lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, fw, fh)
        return float(fx + p.px), float(fy + p.py)

    painter.save()

    for zone in project.zones:
        if not zone.visible or not zone.coordinates:
            continue
        s = zone.style
        fill = QColor(s.fill_color)
        fill.setAlpha(s.fill_alpha)
        border = QColor(s.border_color)
        pen_width = max(1, int(s.border_width * dpi / 96))

        painter.setPen(QPen(border, pen_width))
        painter.setBrush(QBrush(fill))

        if zone.zone_type.value == "circle" and zone.coordinates:
            c = zone.coordinates[0]
            cx, cy = ll_to_pt(c.lat, c.lon)
            mpp = meters_per_pixel(c.lat, zoom)
            radius_px = (zone.radius_m / mpp) if mpp > 0 else 10
            painter.drawEllipse(QPointF(cx, cy), radius_px, radius_px)
        else:
            pts = [ll_to_pt(c.lat, c.lon) for c in zone.coordinates]
            if len(pts) >= 2:
                path = QPainterPath()
                path.moveTo(*pts[0])
                for pt in pts[1:]:
                    path.lineTo(*pt)
                path.closeSubpath()
                painter.drawPath(path)

        # Zone label
        if zone.label and zone.label.text:
            lats = [c.lat for c in zone.coordinates]
            lons = [c.lon for c in zone.coordinates]
            clat = sum(lats) / len(lats)
            clon = sum(lons) / len(lons)
            lx, ly = ll_to_pt(clat, clon)
            ls = zone.label.style
            font = QFont("Helvetica", ls.font_size)
            font.setBold(ls.bold)
            font.setItalic(ls.italic)
            painter.setFont(font)
            painter.setPen(QPen(QColor(ls.color)))
            painter.drawText(QPointF(lx, ly), zone.label.text)

    for kp in project.keypoints:
        if not kp.visible:
            continue
        kx, ky = ll_to_pt(kp.lat, kp.lon)
        r = kp.icon_size * 0.4 * dpi / 96
        color = QColor(kp.icon_color)
        painter.setPen(QPen(color))
        painter.setBrush(QBrush(color))
        from PyQt6.QtCore import QPointF, QRectF
        painter.drawEllipse(QPointF(kx, ky), r, r)
        if kp.keynote_number is not None:
            painter.setPen(QPen(QColor("#FFFFFF")))
            f = QFont("Helvetica", max(6, int(r * 1.2)))
            f.setBold(True)
            painter.setFont(f)
            painter.drawText(
                QRectF(kx - r, ky - r, 2 * r, 2 * r),
                0x84,   # AlignCenter
                str(kp.keynote_number),
            )
        if kp.info_card.title:
            painter.setPen(QPen(QColor("#222222")))
            painter.setFont(QFont("Helvetica", 8))
            painter.drawText(QPointF(kx, ky + r + 10), kp.info_card.title)

    painter.restore()


# ── Architectural title block (combines project title + legend + metadata) ───
#
# Layout (landscape A4 example, full page width between margins):
#
#  ┌────────────────────────────────────────────────────────────────────────┐
#  │ ║ PROJECT NAME (large)        │ DESCRIPTION       │ Legend swatches   │
#  │ ║                             │                   │ ● Zone A          │
#  │ ╠═════════════════════════════╪═══════════════════╪═══════════════════╡
#  │ ║ Scale: 1:NTS  Sheet: 1/1   │ Drawn: …  Rev: A  │ ● Zone B          │
#  └────────────────────────────────────────────────────────────────────────┘
#
# Column widths (relative):  title 35% | meta 30% | legend 35%

def _tb_height_px(pw: int, margin: int, dpi: int, enabled: bool) -> int:
    """Title block height in device pixels, scaled to the printable page width.

    Height = 7.5 % of printable width in points, clamped to [50, 80] pt.
    A4-landscape at 300 dpi → ~58 pt (≈ 20 mm).
    A3-landscape at 300 dpi → 80 pt (≈ 28 mm, upper clamp).
    Portrait pages → 50 pt minimum (≈ 17.5 mm).
    Returns 0 when *enabled* is False (no title block drawn).
    """
    if not enabled:
        return 0
    strip_w_pt = (pw - 2 * margin) * 72.0 / dpi
    tb_pt = max(50.0, min(80.0, strip_w_pt * 0.075))
    return int(tb_pt / 72.0 * dpi)


def _render_title_block(
    painter: Any, project: Project, pw: int, ph: int, margin: int, dpi: int
) -> None:
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QFont, QPen

    layout = project.pdf_layout
    if not layout.tb_enabled:
        return
    tb_h = _tb_height_px(pw, margin, dpi, True)
    strip_w = pw - 2 * margin
    x0 = margin
    y0 = ph - margin - tb_h

    # Column widths
    col_title  = int(strip_w * 0.32)
    col_legend = int(strip_w * 0.36)
    col_meta   = strip_w - col_title - col_legend

    x_title  = x0
    x_meta   = x0 + col_title
    x_legend = x0 + col_title + col_meta

    row2_h = int(tb_h * 0.38)    # bottom row height
    row1_h = tb_h - row2_h       # top row height

    p1 = int(4 / 72.0 * dpi)     # inner cell padding
    lw = max(1, int(0.6 / 72.0 * dpi))   # line weight

    # ── Background ────────────────────────────────────────────────────────── #
    painter.save()
    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor("#FFFFFF")))
    painter.drawRect(QRectF(x0, y0, strip_w, tb_h))

    # ── Outer border (heavy) ─────────────────────────────────────────────── #
    heavy = QPen(QColor("#111111"), lw * 2)
    painter.setPen(heavy)
    painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
    painter.drawRect(QRectF(x0, y0, strip_w, tb_h))

    # ── Internal vertical dividers ───────────────────────────────────────── #
    thin = QPen(QColor("#333333"), lw)
    painter.setPen(thin)
    # title | meta
    painter.drawLine(QRectF(x_meta, y0, 0, tb_h).topLeft(),
                     QRectF(x_meta, y0, 0, tb_h).bottomLeft())
    # meta | legend
    painter.drawLine(QRectF(x_legend, y0, 0, tb_h).topLeft(),
                     QRectF(x_legend, y0, 0, tb_h).bottomLeft())

    # ── Horizontal divider (top row / bottom row) ────────────────────────── #
    # Only in title and meta columns; legend uses all its height for swatches
    y_mid = y0 + row1_h
    # title col
    painter.drawLine(
        QRectF(x_title, y_mid, col_title, 0).topLeft(),
        QRectF(x_title, y_mid, col_title, 0).topRight(),
    )
    # meta col
    painter.drawLine(
        QRectF(x_meta, y_mid, col_meta, 0).topLeft(),
        QRectF(x_meta, y_mid, col_meta, 0).topRight(),
    )

    painter.restore()

    # ── Top-left cell: project name (large) ──────────────────────────────── #
    painter.save()
    # Dark accent band on the far left edge
    painter.setPen(QPen(Qt.PenStyle.NoPen))
    painter.setBrush(QBrush(QColor("#1E3A5F")))
    accent_w = max(6, int(8 / 72.0 * dpi))
    painter.drawRect(QRectF(x_title, y0, accent_w, tb_h))
    painter.restore()

    painter.save()
    name_font = QFont("Arial", 11)
    name_font.setBold(True)
    name_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
    painter.setFont(name_font)
    painter.setPen(QPen(QColor("#111111")))
    painter.drawText(
        QRectF(x_title + accent_w + p1, y0 + p1,
               col_title - accent_w - p1 * 2, row1_h - p1 * 2),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        layout.tb_project_name or project.name,
    )
    painter.restore()

    # ── Bottom-left cell: scale + sheet ──────────────────────────────────── #
    painter.save()
    small_font = QFont("Arial", 7)
    painter.setFont(small_font)
    painter.setPen(QPen(QColor("#444444")))
    painter.drawText(
        QRectF(x_title + accent_w + p1, y_mid + p1,
               col_title - accent_w - p1 * 2, row2_h - p1 * 2),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        f"Scale: {layout.tb_scale}    Sheet: {layout.tb_sheet}",
    )
    painter.restore()

    # ── Top-middle cell: description ─────────────────────────────────────── #
    painter.save()
    _label_cell(painter, x_meta + p1, y0 + p1, col_meta - p1 * 2, row1_h - p1 * 2,
                "DESCRIPTION", layout.tb_description or project.name, dpi)
    painter.restore()

    # ── Bottom-middle cell: drawn / checked / date / revision ────────────── #
    painter.save()
    meta_w4 = (col_meta - lw * 3) // 4
    _mini_cell(painter, x_meta,              y_mid, meta_w4, row2_h, "Drawn",   layout.tb_drawn_by,   dpi)
    _mini_cell(painter, x_meta + meta_w4,    y_mid, meta_w4, row2_h, "Checked", layout.tb_checked_by, dpi)
    _mini_cell(painter, x_meta + meta_w4*2,  y_mid, meta_w4, row2_h, "Date",    layout.info_box_date or date.today().isoformat(), dpi)
    _mini_cell(painter, x_meta + meta_w4*3,  y_mid, meta_w4, row2_h, "Rev",     layout.tb_revision,   dpi)
    painter.restore()

    # ── Right column: legend header + zone swatches ───────────────────────── #
    if layout.show_legend:
        visible_zones = [
            z for z in project.zones
            if z.visible and z.name not in layout.legend_hidden_layers
        ]
        painter.save()
        # legend column header (dark band)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(QColor("#1E3A5F")))
        hdr_h = max(int(10 / 72.0 * dpi), int(tb_h * 0.22))
        painter.drawRect(QRectF(x_legend, y0, col_legend, hdr_h))
        painter.restore()

        painter.save()
        hdr_font = QFont("Arial", 7)
        hdr_font.setBold(True)
        hdr_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        painter.setFont(hdr_font)
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(
            QRectF(x_legend + p1, y0 + 1, col_legend - p1 * 2, hdr_h - 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            (layout.legend_title or "LEGEND").upper(),
        )
        painter.restore()

        # Zone swatches — two columns inside the legend cell
        swatch_s = max(6, int(7 / 72.0 * dpi))
        row_gap  = max(1, int(1.5 / 72.0 * dpi))
        entry_h  = swatch_s + row_gap
        avail_h  = tb_h - hdr_h - p1 * 2
        max_rows = max(1, avail_h // entry_h)
        half = (len(visible_zones) + 1) // 2
        col2_w = col_legend // 2

        legend_font = QFont("Arial", 6)
        painter.save()
        painter.setFont(legend_font)
        for idx, zone in enumerate(visible_zones):
            # Two-column layout
            col_idx = idx // max(1, half)
            row_idx = idx % max(1, half) if len(visible_zones) > max_rows else idx
            if len(visible_zones) > max_rows:
                row_idx = idx % half
            else:
                row_idx = idx
                col_idx = 0

            ex = x_legend + p1 + col_idx * col2_w
            ey = y0 + hdr_h + p1 + row_idx * entry_h
            if ey + swatch_s > y0 + tb_h - 1:
                break   # no more room

            fill = QColor(zone.style.fill_color)
            fill.setAlpha(zone.style.fill_alpha)
            painter.setPen(QPen(QColor(zone.style.border_color), max(1, lw // 2)))
            painter.setBrush(QBrush(fill))
            painter.drawRect(QRectF(ex, ey, swatch_s, swatch_s))

            label = layout.legend_custom_labels.get(zone.name, zone.name)
            painter.setPen(QPen(QColor("#222222")))
            painter.drawText(
                QRectF(ex + swatch_s + max(2, p1 // 2), ey,
                       col2_w - swatch_s - p1 * 2, swatch_s),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        painter.restore()


def _label_cell(
    painter: Any, x: float, y: float, w: float, h: float,
    caption: str, value: str, dpi: int
) -> None:
    """Draw a labelled cell: small grey caption on top, larger value below."""
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QPen

    cap_h = max(int(8 / 72.0 * dpi), int(h * 0.32))
    cap_font = QFont("Arial", 6)
    val_font = QFont("Arial", 8)

    painter.setFont(cap_font)
    painter.setPen(QPen(QColor("#888888")))
    painter.drawText(
        QRectF(x, y, w, cap_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        caption.upper(),
    )
    painter.setFont(val_font)
    painter.setPen(QPen(QColor("#111111")))
    painter.drawText(
        QRectF(x, y + cap_h, w, h - cap_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        value,
    )


def _mini_cell(
    painter: Any, x: float, y: float, w: float, h: float,
    caption: str, value: str, dpi: int
) -> None:
    """A compact cell with a hairline left border, caption label, and value."""
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QPen

    lw = max(1, int(0.5 / 72.0 * dpi))
    painter.setPen(QPen(QColor("#AAAAAA"), lw))
    painter.drawLine(QRectF(x, y, 0, h).topLeft(), QRectF(x, y, 0, h).bottomLeft())

    p = max(int(2 / 72.0 * dpi), 2)
    cap_h = max(int(7 / 72.0 * dpi), int(h * 0.35))
    cap_font = QFont("Arial", 5)
    val_font = QFont("Arial", 7)

    painter.setFont(cap_font)
    painter.setPen(QPen(QColor("#888888")))
    painter.drawText(
        QRectF(x + p, y + p, w - p * 2, cap_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        caption.upper(),
    )
    painter.setFont(val_font)
    painter.setPen(QPen(QColor("#111111")))
    painter.drawText(
        QRectF(x + p, y + p + cap_h, w - p * 2, h - p * 2 - cap_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        value,
    )


# ── Info box ──────────────────────────────────────────────────────────────────

def _render_info_box(
    painter: Any, project: Project, pw: int, ph: int, margin: int, dpi: int
) -> None:
    layout = project.pdf_layout
    if not layout.show_info_box:
        return
    lines: list[str] = []
    if layout.info_box_text:
        lines.extend(layout.info_box_text.splitlines())
    if layout.info_box_author:
        lines.append(f"Author: {layout.info_box_author}")
    if layout.info_box_date:
        lines.append(f"Date: {layout.info_box_date}")
    if not lines:
        return
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QBrush, QColor, QFont, QPen

    row_h = int(11 / 72.0 * dpi)
    padding = int(6 / 72.0 * dpi)
    box_w = int(160 / 72.0 * dpi)
    box_h = row_h * len(lines) + padding * 2
    x = margin
    tb_h = _tb_height_px(pw, margin, dpi, layout.tb_enabled)
    y = ph - margin - tb_h - box_h - int(4 / 72.0 * dpi)

    painter.save()
    painter.setPen(QPen(QColor("#AAAAAA")))
    painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
    painter.drawRect(QRectF(x, y, box_w, box_h))
    painter.setPen(QPen(QColor("#333333")))
    painter.setFont(QFont("Helvetica", 7))
    for i, line in enumerate(lines):
        painter.drawText(
            QRectF(x + padding, y + padding + row_h * i, box_w - padding * 2, row_h),
            0x81, line
        )
    painter.restore()


# ── Keynote table ─────────────────────────────────────────────────────────────

def _render_keynote_table(
    painter: Any, project: Project, pw: int, ph: int, margin: int, dpi: int
) -> None:
    keynoted = sorted(
        [k for k in project.keypoints if k.keynote_number is not None],
        key=lambda k: k.keynote_number,
    )
    if not keynoted:
        return
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QFont, QPen

    row_h = int(11 / 72.0 * dpi)
    x = margin
    tb_h = _tb_height_px(pw, margin, dpi, project.pdf_layout.tb_enabled)
    y = ph - margin - tb_h - row_h * len(keynoted) - int(4 / 72.0 * dpi)

    painter.save()
    font_bold = QFont("Helvetica", 8)
    font_bold.setBold(True)
    painter.setFont(font_bold)
    painter.setPen(QPen(QColor("#333333")))
    half_page = (pw - 2 * margin) // 2
    painter.drawText(QRectF(x, y - row_h, half_page, row_h), 0x81, t("Key Points"))

    painter.setFont(QFont("Helvetica", 7))
    for kp in keynoted:
        label = f"  {kp.keynote_number}.  {kp.info_card.title}  —  {kp.info_card.subtitle}"
        painter.drawText(QRectF(x, y, half_page, row_h), 0x81, label[:80])
        y += row_h

    painter.restore()


# ── Floating legend (standalone, when title block is disabled) ───────────────

def _render_floating_legend(
    painter: Any, project: Project, pw: int, ph: int, margin: int, dpi: int
) -> None:
    """Draw a compact floating legend box at top-right when tb_enabled is False."""
    layout = project.pdf_layout
    visible_zones = [
        z for z in project.zones
        if z.visible and z.name not in layout.legend_hidden_layers
    ]
    if not visible_zones:
        return

    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QBrush, QColor, QFont, QPen

    p        = int(6   / 72.0 * dpi)
    swatch_s = int(8   / 72.0 * dpi)
    entry_h  = swatch_s + int(2 / 72.0 * dpi)
    title_h  = int(11  / 72.0 * dpi)
    box_w    = int(120 / 72.0 * dpi)
    box_h    = title_h + p + entry_h * len(visible_zones) + p
    x = pw - margin - box_w
    y = margin

    painter.save()
    painter.setPen(QPen(QColor("#555555"), max(1, int(0.5 / 72.0 * dpi))))
    painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
    painter.drawRect(QRectF(x, y, box_w, box_h))

    hdr_font = QFont("Arial", 7)
    hdr_font.setBold(True)
    painter.setFont(hdr_font)
    painter.setPen(QPen(QColor("#111111")))
    painter.drawText(
        QRectF(x + p, y + p // 2, box_w - p * 2, title_h),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        (layout.legend_title or "Legend").upper(),
    )

    lbl_font = QFont("Arial", 6)
    painter.setFont(lbl_font)
    lw = max(1, int(0.5 / 72.0 * dpi))
    for i, zone in enumerate(visible_zones):
        ey = y + title_h + p + i * entry_h
        fill = QColor(zone.style.fill_color)
        fill.setAlpha(zone.style.fill_alpha)
        painter.setPen(QPen(QColor(zone.style.border_color), lw))
        painter.setBrush(QBrush(fill))
        painter.drawRect(QRectF(x + p, ey, swatch_s, swatch_s))
        label = layout.legend_custom_labels.get(zone.name, zone.name)
        painter.setPen(QPen(QColor("#222222")))
        painter.drawText(
            QRectF(x + p + swatch_s + max(2, p // 3), ey,
                   box_w - p * 2 - swatch_s, swatch_s),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
    painter.restore()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_item(layout: "PDFLayout", item_type: LayoutItemType):
    for item in layout.items:
        if item.item_type == item_type:
            return item
    return None
