# -*- coding: utf-8 -*-
"""
Framework-agnostic iOS-style widget grid engine.

This module deliberately imports ONLY from PyQt6 (never from aqt / the addon)
so it can be developed and unit-tested in a standalone Qt harness. The settings
package wraps these classes and injects Anki-specific data (translations,
config, colour/icon pickers) from the outside.

Public building blocks:
    WidgetSpec        - metadata describing one placeable widget
    paint_preview     - draws a native mini-preview of a widget onto a painter
    GridTile          - a single placed tile (rounded card + preview + label)
    iOSGridCanvas     - the animated grid with live drag-to-reflow
    WidgetGalleryDialog - the "add a widget" gallery (two groups, previews)
"""

from PyQt6.QtCore import (
    Qt, QRect, QRectF, QPoint, QPointF, QSize, QTimer, QEvent, QByteArray,
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, pyqtSignal,
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush, QFont, QPixmap, QLinearGradient,
    QFontMetrics, QIcon,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QSizePolicy, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
)


# --------------------------------------------------------------------------- #
#  Palette helper                                                             #
# --------------------------------------------------------------------------- #

def _mix(a, b, t):
    """Linear blend of two QColors, t in [0,1]."""
    a = QColor(a); b = QColor(b)
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def _readable_on(color):
    c = QColor(color)
    lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
    return QColor("#111827") if lum > 0.6 else QColor("#ffffff")


class Palette:
    """Small colour bundle the grid draws from. Built from the settings theme."""

    def __init__(self, is_dark=False, accent="#00A982", fg=None, card=None,
                 border=None, canvas=None):
        self.is_dark = is_dark
        self.accent = QColor(accent)
        if is_dark:
            self.fg = QColor(fg or "#f3f4f6")
            self.muted = QColor("#9ca3af")
            self.card = QColor(card or "#242424")
            self.card_alt = _mix(self.card, "#ffffff", 0.06)
            self.border = QColor(border or "#3a3a3a")
            self.canvas = QColor(canvas or "#1b1b1b")
            self.slot = QColor(255, 255, 255, 14)
            self.slot_border = QColor(255, 255, 255, 26)
        else:
            self.fg = QColor(fg or "#111827")
            self.muted = QColor("#6b7280")
            self.card = QColor(card or "#ffffff")
            self.card_alt = _mix(self.card, "#000000", 0.04)
            self.border = QColor(border or "#e5e7eb")
            self.canvas = QColor(canvas or "#f4f4f5")
            self.slot = QColor(0, 0, 0, 10)
            self.slot_border = QColor(0, 0, 0, 20)


# --------------------------------------------------------------------------- #
#  Widget spec                                                                #
# --------------------------------------------------------------------------- #

class WidgetSpec:
    """Everything the grid/gallery needs to know about one placeable widget."""

    def __init__(self, wid, name, kind="onigiri", preview="card",
                 default_span=(1, 1), min_span=(1, 1), max_span=(1, 1),
                 color=None, icon_pixmap=None, has_preview=True,
                 fixed_rows=None, extra=None):
        self.wid = wid                      # stable widget id / hook id
        self.name = name                    # display name (already translated)
        self.kind = kind                    # "onigiri" | "external" | "bento"
        self.preview = preview              # preview painter key
        self.default_span = default_span    # (rows, cols)
        self.min_span = min_span
        self.max_span = max_span
        self.color = QColor(color) if color else None
        self.icon_pixmap = icon_pixmap      # optional QPixmap identity icon
        self.has_preview = has_preview      # external no-preview -> colour+icon chip
        self.fixed_rows = fixed_rows        # if set, row span is locked to this
        self.extra = extra or {}            # orientation, etc.

    def clamp_span(self, rs, cs):
        rmin, cmin = self.min_span
        rmax, cmax = self.max_span
        if self.fixed_rows:
            rs = self.fixed_rows
        else:
            rs = max(rmin, min(rmax, rs))
        cs = max(cmin, min(cmax, cs))
        return rs, cs


# --------------------------------------------------------------------------- #
#  Preview painting                                                           #
# --------------------------------------------------------------------------- #

def paint_preview(painter, rect, spec, pal, radius=16):
    """Draw a native mini-preview of `spec` inside `rect` (a QRectF)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Base card.
    _fill_round(painter, rect, pal.card, radius)

    # Fixed padding so small widgets don't get squeezed out of existence
    r = _pad(rect, 10)
    
    if r.width() < 10 or r.height() < 10:
        painter.restore()
        return

    # Draw Title centered with word wrap
    painter.setPen(pal.fg)
    f2 = QFont(painter.font())
    f2.setBold(False)
    f2.setWeight(QFont.Weight.Normal)
    f2.setPixelSize(13)
    painter.setFont(f2)
    
    # In PyQt6, drawText accepts an int for flags.
    opt = int(Qt.AlignmentFlag.AlignCenter.value) | int(Qt.TextFlag.TextWordWrap.value)
    painter.drawText(r, opt, spec.name or "")

    painter.restore()

def _fill_round(painter, rect, color, radius):
    path = QPainterPath()
    path.addRoundedRect(QRectF(rect), radius, radius)
    painter.fillPath(path, QColor(color))

def _pad(rect, dx, dy=None):
    if dy is None:
        dy = dx
    return QRectF(rect).adjusted(dx, dy, -dx, -dy)


# --------------------------------------------------------------------------- #
#  Grid tile                                                                  #
# --------------------------------------------------------------------------- #

class GridTile(QWidget):
    """A placed widget on the canvas: rounded card, preview, name caption."""

    def __init__(self, spec, canvas):
        super().__init__(canvas)
        self.spec = spec
        self.canvas = canvas
        self.row = 0
        self.col = 0
        self.row_span, self.col_span = spec.default_span
        self.display_name = spec.name
        self._press_pos = None
        self._dragging = False
        self._hovered = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    # ---- painting ----
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pal = self.canvas.pal
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = 18

        # shadow-ish base border
        paint_preview(p, rect, self._live_spec(), pal, radius)

        # border
        pen = QPen(pal.border, 1)
        if self._dragging:
            pen = QPen(pal.accent, 2)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(); path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        p.drawPath(path)

        # hover remove button
        if self._hovered and not self._dragging:
            self._draw_remove(p, pal)
        p.end()

    def _live_spec(self):
        s = self.spec
        s.name = self.display_name
        return s



    def _remove_rect(self):
        return QRectF(self.width() - 26, 6, 20, 20)

    def _draw_remove(self, p, pal):
        r = self._remove_rect()
        p.setBrush(QColor(30, 30, 30, 190)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(r)
        pen = QPen(QColor("#ffffff"), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        c = r.center(); d = 4
        p.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        p.drawLine(QPointF(c.x() - d, c.y() + d), QPointF(c.x() + d, c.y() - d))

    # ---- interaction ----
    def enterEvent(self, e):
        self._hovered = True; self.update()

    def leaveEvent(self, e):
        self._hovered = False; self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self._remove_rect().contains(QPointF(e.position())):
            self.canvas.remove_tile(self)
            return
        self._press_pos = e.position().toPoint()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._press_pos is None:
            return
        if not self._dragging:
            if (e.position().toPoint() - self._press_pos).manhattanLength() < 6:
                return
            self._dragging = True
            self.canvas.begin_drag(self, self._press_pos)
        self.canvas.update_drag(self, e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if self._dragging:
            self._dragging = False
            self.canvas.end_drag(self)
        self._press_pos = None

    def contextMenuEvent(self, e):
        self.canvas.tile_context_menu(self, e.globalPos())


# --------------------------------------------------------------------------- #
#  The animated grid canvas                                                   #
# --------------------------------------------------------------------------- #

class iOSGridCanvas(QWidget):
    """A grid of GridTiles with live drag-to-reflow and spring animations."""

    layout_changed = pyqtSignal()
    tile_removed = pyqtSignal(object)        # emits spec
    empty_clicked = pyqtSignal()             # tap on empty canvas -> open gallery
    context_requested = pyqtSignal(object, object)  # (tile, global_pos)

    ANIM_MS = 240

    MAX_ROWS = 60

    def __init__(self, pal, rows=6, cols=4, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.min_rows = max(1, rows)    # floor: grid never shows fewer than this
        self.rows = self.min_rows       # effective rows (auto-grows to fit content)
        self.cols = cols
        self.cell_h = 64
        self.gap = 12
        self.tiles = []                 # placed tiles; each owns explicit (row, col)
        self._anim_group = None
        self._fade_anims = set()        # in-flight removal fades (kept from GC)
        self._drag_tile = None
        self._drag_offset = QPoint()
        self._drag_orig = (0, 0)
        self._drag_target = None
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ---- geometry ----
    def cell_size(self):
        avail = self.width() - self.gap * (self.cols + 1)
        cw = max(24, avail / max(1, self.cols))
        return cw, self.cell_h

    def cell_rect(self, row, col, rs=1, cs=1):
        cw, ch = self.cell_size()
        x = self.gap + col * (cw + self.gap)
        y = self.gap + row * (ch + self.gap)
        w = cw * cs + self.gap * (cs - 1)
        h = ch * rs + self.gap * (rs - 1)
        return QRect(round(x), round(y), round(w), round(h))

    def sizeHint(self):
        cw, ch = self.cell_size()
        h = self.gap + self.rows * (ch + self.gap)
        return QSize(int(self.width()), int(h))

    def _sync_height(self):
        cw, ch = self.cell_size()
        h = int(self.gap + self.rows * (ch + self.gap))
        self.setFixedHeight(h)

    # ---- occupancy / free placement ----
    def _occupied_cells(self, exclude=None):
        """{(row, col): tile} for every cell currently covered by a tile."""
        occ = {}
        for t in self.tiles:
            if t is exclude:
                continue
            for rr in range(t.row, t.row + t.row_span):
                for cc in range(t.col, t.col + t.col_span):
                    occ[(rr, cc)] = t
        return occ

    def _cells_free(self, r, c, rs, cs, occ):
        if r < 0 or c < 0 or c + cs > self.cols or r + rs > self.MAX_ROWS:
            return False
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                if (rr, cc) in occ:
                    return False
        return True

    def _resolve_overlaps(self, priority=None):
        """Guarantee no two tiles share a cell. Earlier tiles keep their spot;
        later ones get pushed to the first free slot. `priority` claims its
        cells before anyone else (used after a resize)."""
        occ = {}
        order = list(self.tiles)
        if priority in order:
            order.remove(priority)
            order.insert(0, priority)
        for t in order:
            if not self._cells_free(t.row, t.col, t.row_span, t.col_span, occ):
                t.row, t.col = self._find_free_slot_in(t.row_span, t.col_span, occ)
            for rr in range(t.row, t.row + t.row_span):
                for cc in range(t.col, t.col + t.col_span):
                    occ[(rr, cc)] = t

    def _find_free_slot_in(self, rs, cs, occ):
        r = 0
        while r <= self.MAX_ROWS - rs:
            for c in range(self.cols - cs + 1):
                if self._cells_free(r, c, rs, cs, occ):
                    return r, c
            r += 1
        return 0, 0

    def _find_free_slot(self, rs, cs, exclude=None):
        """First empty area (row-major scan) big enough for an rs x cs tile."""
        occ = self._occupied_cells(exclude=exclude)
        r = 0
        while r <= self.MAX_ROWS - rs:
            for c in range(self.cols - cs + 1):
                if self._cells_free(r, c, rs, cs, occ):
                    return r, c
            r += 1
        return 0, 0

    def _effective_rows(self):
        used = self.min_rows
        for t in self.tiles:
            used = max(used, t.row + t.row_span)
        return used

    def relayout(self, animated=True):
        """Reapply every tile's own (row, col, spans) to pixel geometry.
        Positions are user-owned -> nothing gets reflowed or compacted here."""
        self.rows = self._effective_rows()
        placed = {t: (t.row, t.col, t.row_span, t.col_span) for t in self.tiles}
        self._apply_placement(placed, animated)
        self._sync_height()

    def _apply_placement(self, placed, animated):
        if self._anim_group:
            self._anim_group.stop()
            self._anim_group = None
        group = QParallelAnimationGroup(self)
        for tile, (r, c, rs, cs) in placed.items():
            tile.row, tile.col, tile.row_span, tile.col_span = r, c, rs, cs
            target = self.cell_rect(r, c, rs, cs)
            if tile is self._drag_tile:
                continue
            if animated and tile.isVisible() and tile.geometry() != target:
                anim = QPropertyAnimation(tile, b"geometry", self)
                anim.setDuration(self.ANIM_MS)
                anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                anim.setStartValue(tile.geometry())
                anim.setEndValue(target)
                group.addAnimation(anim)
            else:
                tile.setGeometry(target)
            tile.show()
        if group.animationCount():
            self._anim_group = group
            group.finished.connect(lambda: self.layout_changed.emit())
            group.start()
        else:
            self.layout_changed.emit()

    # ---- tile management ----
    def add_spec(self, spec, at_index=None, animated=True, row=None, col=None,
                 row_span=None, col_span=None):
        """Place `spec` on the canvas. Pass explicit `row`/`col` to restore a
        saved position (falls back to the first free slot if occupied);
        otherwise the tile auto-places in the first free slot."""
        tile = GridTile(spec, self)
        if row_span is None or col_span is None:
            row_span, col_span = spec.default_span
        rs, cs = spec.clamp_span(row_span, col_span)
        tile.row_span, tile.col_span = rs, cs
        if at_index is None:
            self.tiles.append(tile)
        else:
            self.tiles.insert(at_index, tile)
        occ = self._occupied_cells(exclude=tile)
        if row is not None and col is not None and self._cells_free(row, col, rs, cs, occ):
            tile.row, tile.col = row, col
        else:
            tile.row, tile.col = self._find_free_slot(rs, cs, exclude=tile)
        self.rows = self._effective_rows()
        self._sync_height()
        # spring-in
        full = self.cell_rect(tile.row, tile.col, rs, cs)
        tile.setGeometry(QRect(full.center().x() - 4, full.center().y() - 4, 8, 8))
        tile.show()
        self.relayout(animated)
        self.layout_changed.emit()
        return tile

    FADE_MS = 200

    def remove_tile(self, tile, animated=True):
        if tile not in self.tiles:
            return
        self.tiles.remove(tile)
        spec = tile.spec
        if animated:
            self._fade_out(tile)
        else:
            tile.hide(); tile.setParent(None); tile.deleteLater()
        self.relayout(animated)
        self.tile_removed.emit(spec)
        self.layout_changed.emit()

    def _fade_out(self, tile):
        """Dissolve the tile in place, then drop it. It is already out of
        self.tiles, so relayout ignores it and the neighbours slide underneath."""
        tile.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        eff = QGraphicsOpacityEffect(tile)
        eff.setOpacity(1.0)
        tile.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(self.FADE_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)

        def _drop():
            self._fade_anims.discard(anim)
            tile.hide(); tile.setParent(None); tile.deleteLater()

        anim.finished.connect(_drop)
        self._fade_anims.add(anim)   # keep alive until it finishes
        anim.start()

    def has_widget(self, wid):
        return any(t.spec.wid == wid for t in self.tiles)

    def clear(self):
        for t in list(self.tiles):
            t.hide(); t.setParent(None); t.deleteLater()
        self.tiles = []
        self._sync_height()

    # ---- drag lifecycle ----
    # Tiles are free-standing: a drag only lands on cells that are entirely
    # empty. No swapping, no shoving neighbours aside — anything else snaps
    # the tile back to where it started.
    def begin_drag(self, tile, local_press):
        self._drag_tile = tile
        self._drag_offset = local_press
        self._drag_orig = (tile.row, tile.col)
        self._drag_target = self._drag_orig
        tile.raise_()
        eff = QGraphicsDropShadowEffect(tile)
        eff.setBlurRadius(28); eff.setColor(QColor(0, 0, 0, 120)); eff.setOffset(0, 8)
        tile.setGraphicsEffect(eff)

    def _cell_from_topleft(self, point):
        """Cell whose origin the tile's top-left is nearest to. Using the
        top-left (not the centre) keeps multi-cell tiles from biasing a full
        cell down/right, which used to land them on occupied ground."""
        cw, ch = self.cell_size()
        c = int(round((point.x() - self.gap) / (cw + self.gap)))
        r = int(round((point.y() - self.gap) / (ch + self.gap)))
        return r, c

    def update_drag(self, tile, global_pos):
        if tile is not self._drag_tile:
            return
        local = self.mapFromGlobal(global_pos)
        new_top_left = local - self._drag_offset
        tile.move(new_top_left)

        rs, cs = tile.row_span, tile.col_span
        r, c = self._cell_from_topleft(new_top_left)
        r = max(0, min(self.MAX_ROWS - rs, r))
        c = max(0, min(self.cols - cs, c))

        occ = self._occupied_cells(exclude=tile)
        # only a fully empty footprint is a valid drop; otherwise snap back
        self._drag_target = (r, c) if self._cells_free(r, c, rs, cs, occ) else None

        needed = max(self._effective_rows(), r + rs)
        if needed != self.rows:
            self.rows = needed
            self._sync_height()
        self.update()

    def end_drag(self, tile):
        tile.setGraphicsEffect(None)
        r, c = self._drag_target if self._drag_target is not None else self._drag_orig
        occ = self._occupied_cells(exclude=tile)
        if not self._cells_free(r, c, tile.row_span, tile.col_span, occ):
            # last-resort guard: never leave two tiles stacked
            if self._cells_free(*self._drag_orig, tile.row_span, tile.col_span, occ):
                r, c = self._drag_orig
            else:
                r, c = self._find_free_slot_in(tile.row_span, tile.col_span, occ)
        tile.row, tile.col = r, c
        self._drag_tile = None
        self._drag_target = None
        self.relayout(animated=True)
        self.layout_changed.emit()

    # ---- events ----
    def resizeEvent(self, e):
        self.rows = self._effective_rows()
        self._sync_height()
        for tile in self.tiles:
            if tile is not self._drag_tile:
                tile.setGeometry(self.cell_rect(tile.row, tile.col, tile.row_span, tile.col_span))

    def mousePressEvent(self, e):
        # tap on empty area opens the gallery
        if e.button() == Qt.MouseButton.LeftButton:
            self.empty_clicked.emit()

    def tile_context_menu(self, tile, global_pos):
        self.context_requested.emit(tile, global_pos)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # empty slot hints
        occ = set()
        for t in self.tiles:
            for rr in range(t.row, t.row + t.row_span):
                for cc in range(t.col, t.col + t.col_span):
                    occ.add((rr, cc))
        for r in range(self.rows):
            for c in range(self.cols):
                if (r, c) in occ:
                    continue
                rect = self.cell_rect(r, c)
                path = QPainterPath()
                path.addRoundedRect(QRectF(rect).adjusted(1, 1, -1, -1), 16, 16)
                pen = QPen(self.pal.slot_border, 1, Qt.PenStyle.DashLine)
                p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
        # "add" hint in first empty slot
        if not self.tiles:
            p.setPen(self.pal.muted)
            f = QFont(p.font()); f.setPixelSize(14); p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "Tap to add a widget")
        p.end()

    def set_grid(self, min_rows, cols, animated=True):
        self.min_rows = max(1, min_rows)
        self.cols = max(1, cols)
        # clamp any tile wider than the new column count, or now hanging off the edge
        for t in self.tiles:
            if t.col_span > self.cols:
                t.col_span = self.cols
            if t.col + t.col_span > self.cols:
                t.col = max(0, self.cols - t.col_span)
        # clamping can stack tiles on the same cell -> spread them back out
        self._resolve_overlaps()
        self.relayout(animated=animated)


# --------------------------------------------------------------------------- #
#  Gallery dialog                                                             #
# --------------------------------------------------------------------------- #

class GalleryCard(QFrame):
    """A selectable widget card in the gallery."""
    clicked = pyqtSignal(object)  # spec

    def __init__(self, spec, pal, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.pal = pal
        self.setFixedSize(150, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, e):
        self._hover = True; self.update()

    def leaveEvent(self, e):
        self._hover = False; self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.spec)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pal = self.pal
        outer = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        _fill_round(p, outer, pal.card, 18)
        preview_rect = outer.adjusted(14, 14, -14, -14)
        paint_preview(p, preview_rect, self.spec, pal, 14)
        pen = QPen(pal.accent if self._hover else pal.border, 2 if self._hover else 1)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(); path.addRoundedRect(outer.adjusted(0.5, 0.5, -0.5, -0.5), 18, 18)
        p.drawPath(path)
        p.end()


class FlowArea(QWidget):
    """Simple wrapping flow of fixed cards."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards = []
        self.h_gap = 14
        self.v_gap = 14

    def add_card(self, card):
        card.setParent(self)
        self.cards.append(card)
        card.show()

    def clear(self):
        for c in self.cards:
            c.hide(); c.setParent(None); c.deleteLater()
        self.cards = []

    def resizeEvent(self, e):
        self._relayout()

    def _relayout(self):
        if not self.cards:
            self.setMinimumHeight(0)
            return
        cw = self.cards[0].width()
        ch = self.cards[0].height()
        per_row = max(1, (self.width() + self.h_gap) // (cw + self.h_gap))
        x = 0; y = 0; col = 0
        for i, c in enumerate(self.cards):
            c.move(x, y)
            col += 1
            if col >= per_row:
                col = 0; x = 0; y += ch + self.v_gap
            else:
                x += cw + self.h_gap
        rows = (len(self.cards) + per_row - 1) // per_row
        self.setMinimumHeight(rows * (ch + self.v_gap))


# Material "close" glyph, embedded so this module stays PyQt6-only (no addon
# filesystem lookups). Same artwork as
# system_files/system_icons/unavailable_for_users/cancel.svg.
_CANCEL_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    b'<path fill="none" stroke="currentColor" stroke-linecap="round" '
    b'stroke-linejoin="round" stroke-width="2" d="M18 6L6 18M6 6l12 12"/></svg>'
)


def _cancel_icon(color, size=18):
    """Render the embedded cancel glyph tinted to ``color`` as a QIcon."""
    renderer = QSvgRenderer(QByteArray(_CANCEL_SVG))
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(p)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


class _HoverIconButton(QPushButton):
    """Push button that swaps its icon on hover (QIcon Active mode is
    unreliable across styles, so swap explicitly)."""
    def __init__(self, normal_icon, hover_icon, parent=None):
        super().__init__(parent)
        self._normal_icon = normal_icon
        self._hover_icon = hover_icon
        self.setIcon(self._normal_icon)

    def enterEvent(self, e):
        self.setIcon(self._hover_icon); super().enterEvent(e)

    def leaveEvent(self, e):
        self.setIcon(self._normal_icon); super().leaveEvent(e)


class WidgetGalleryDialog(QDialog):
    """Two-group widget gallery. Emits widget_chosen(spec) on selection."""
    widget_chosen = pyqtSignal(object)

    def __init__(self, pal, onigiri_specs, external_specs, strings=None, parent=None):
        super().__init__(parent)
        self.pal = pal
        self.strings = strings or {}
        self._drag_offset = None
        self.setWindowTitle(self.strings.get("gallery_title", "Widget Gallery"))
        # Chill picker chrome: frameless, translucent, rounded — mirrors
        # FontPickerDialog / DeckIconPickerDialog instead of a full window.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(560, 600)
        # Poppins, never heavier than Regular (400). The family is registered
        # into Qt at profile open via fonts.register_poppins_qt(); setting it on
        # the dialog also reaches the cards, whose names are painted with
        # painter.font() rather than a stylesheet.
        gallery_font = QFont("Poppins")
        gallery_font.setWeight(QFont.Weight.Normal)
        self.setFont(gallery_font)
        self._build(onigiri_specs, external_specs)

    def _t(self, key, default):
        return self.strings.get(key, default)

    def _build(self, onigiri_specs, external_specs):
        pal = self.pal

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self._container = QFrame()
        self._container.setObjectName("GalleryContainer")
        self._container.setStyleSheet(
            f"*{{font-family:'Poppins';font-weight:400;}}"
            f"QFrame#GalleryContainer{{background:{pal.canvas.name()};"
            f"border-radius:20px;border:1px solid {pal.border.name()};}}")
        outer.addWidget(self._container)

        root = QVBoxLayout(self._container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header: title + subtitle on the left, close button on the right ──
        head = QHBoxLayout()
        head.setContentsMargins(22, 18, 14, 0)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        header = QLabel(self._t("gallery_title", "Widget Gallery"))
        header.setStyleSheet(
            f"font-family:'Poppins';font-size:19px;font-weight:400;"
            f"color:{pal.fg.name()};background:transparent;")
        sub = QLabel(self._t("gallery_subtitle", "Tap a widget to drop it onto your grid"))
        sub.setStyleSheet(f"font-family:'Poppins';font-size:12px;font-weight:400;"
                          f"color:{pal.muted.name()};background:transparent;")
        title_col.addWidget(header)
        title_col.addWidget(sub)
        head.addLayout(title_col, 1)

        close_btn = _HoverIconButton(
            _cancel_icon(pal.fg.name(), 16),
            _cancel_icon(pal.canvas.name(), 16),
        )
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setFixedSize(34, 34)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet(
            f"QPushButton{{background:{pal.card.name()};border:1px solid {pal.border.name()};"
            f"border-radius:17px;}}"
            f"QPushButton:hover{{background:{pal.fg.name()};border-color:{pal.fg.name()};}}")
        head.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)
        root.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                             "QScrollBar:vertical{background:transparent;width:10px;}"
                             "QScrollBar::handle:vertical{background:rgba(128,128,128,0.5);"
                             "border-radius:5px;min-height:24px;}"
                             "QScrollBar::add-line,QScrollBar::sub-line{height:0;}")
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(22, 0, 18, 22)
        body_l.setSpacing(10)

        self._add_section(body_l, self._t("gallery_onigiri", "Onigiri Widgets"), onigiri_specs)
        self._add_section(body_l, self._t("gallery_external", "External Add-ons"), external_specs)
        body_l.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ── Frameless drag: grab anywhere on the dialog body to move it ──────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (event.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def _add_section(self, parent_layout, title, specs):
        if not specs:
            return
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"font-family:'Poppins';font-size:13px;font-weight:400;letter-spacing:0.04em;"
            f"text-transform:uppercase;color:{self.pal.muted.name()};padding-top:8px;")
        parent_layout.addWidget(lbl)
        flow = FlowArea()
        for spec in specs:
            card = GalleryCard(spec, self.pal)
            card.clicked.connect(self._on_pick)
            flow.add_card(card)
        parent_layout.addWidget(flow)

    def _on_pick(self, spec):
        self.widget_chosen.emit(spec)
        self.accept()
