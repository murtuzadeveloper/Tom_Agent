"""
Transparent fullscreen overlay for interactive screen region selection (Mode B).
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor

class RegionSelectorWidget(QWidget):
    """Fullscreen translucent widget to select a rectangular screen region."""

    region_selected = Signal(tuple)  # (left, top, width, height)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self.start_pos: QPoint = QPoint()
        self.end_pos: QPoint = QPoint()
        self.is_selecting = False

    def start_selection(self):
        """Displays overlay over all screens."""
        self.showFullScreen()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.globalPosition().toPoint()
            self.end_pos = self.start_pos
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            rect = QRect(self.start_pos, self.end_pos).normalized()
            self.close()
            if rect.width() > 10 and rect.height() > 10:
                self.region_selected.emit((rect.left(), rect.top(), rect.width(), rect.height()))
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.is_selecting = False
            self.close()
            self.cancelled.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw semi-transparent dark mask over entire screen
        mask_color = QColor(10, 12, 20, 140)
        painter.fillRect(self.rect(), mask_color)

        if self.is_selecting:
            selection_rect = QRect(self.start_pos, self.end_pos).normalized()

            # Clear selected rectangle so user sees through clearly
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.GlobalColor.transparent)

            # Draw glowing violet/blue border around selection
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            border_pen = QPen(QColor(99, 102, 241), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.drawRect(selection_rect)

            # Draw dimension tooltip
            dim_text = f" {selection_rect.width()} × {selection_rect.height()} px (ESC to cancel) "
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(Qt.GlobalColor.white)
            painter.fillRect(
                selection_rect.left(),
                max(0, selection_rect.top() - 25),
                210,
                22,
                QColor(26, 28, 41, 230)
            )
            painter.drawText(
                selection_rect.left() + 5,
                max(0, selection_rect.top() - 9),
                dim_text
            )
        else:
            # Help text before drag
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
            painter.setPen(QColor(230, 230, 240))
            help_msg = "Click and drag to select screen region. Press ESC to cancel."
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, help_msg)
