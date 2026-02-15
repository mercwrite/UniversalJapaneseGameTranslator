"""Reusable custom Qt widgets for the controller UI."""

from PyQt6 import QtWidgets, QtCore, QtGui


class ModernComboBox(QtWidgets.QComboBox):
    """Custom ComboBox with animated arrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_popup_shown = False

    def showPopup(self):
        """Override to show popup below and track state."""
        self.is_popup_shown = True
        self.update()
        super().showPopup()

    def hidePopup(self):
        """Override to track state."""
        self.is_popup_shown = False
        self.update()
        super().hidePopup()

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Custom paint to draw arrow."""
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Draw arrow on the right side
        arrow_x = self.width() - 24
        arrow_y = self.height() // 2

        painter.setPen(QtGui.QPen(QtGui.QColor(170, 170, 170), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap))

        if self.is_popup_shown:
            # Down-pointing triangle when open
            triangle = QtGui.QPolygon([
                QtCore.QPoint(arrow_x - 4, arrow_y - 2),
                QtCore.QPoint(arrow_x + 4, arrow_y - 2),
                QtCore.QPoint(arrow_x, arrow_y + 3)
            ])
        else:
            # Right-pointing triangle when closed
            triangle = QtGui.QPolygon([
                QtCore.QPoint(arrow_x - 2, arrow_y - 4),
                QtCore.QPoint(arrow_x - 2, arrow_y + 4),
                QtCore.QPoint(arrow_x + 3, arrow_y)
            ])

        painter.setBrush(QtGui.QColor(170, 170, 170))
        painter.drawPolygon(triangle)


class IconButton(QtWidgets.QPushButton):
    """Custom button with icon drawing capabilities."""

    def __init__(self, icon_type: str, size: int = 32, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type
        self.icon_size = size
        self.setFixedSize(size, size)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Custom paint for modern icon buttons."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Background on hover
        if self.underMouse():
            painter.setBrush(QtGui.QColor(70, 70, 70, 150))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 6, 6)

        # Draw icon
        painter.setPen(QtGui.QPen(QtGui.QColor(220, 220, 220), 2, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin))

        center_x = self.width() // 2
        center_y = self.height() // 2

        if self.icon_type == "eye":
            # Draw eye icon
            painter.drawEllipse(center_x - 8, center_y - 4, 16, 8)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)

        elif self.icon_type == "eye-slash":
            # Draw eye with slash
            painter.drawEllipse(center_x - 8, center_y - 4, 16, 8)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)
            painter.drawLine(center_x - 10, center_y - 6, center_x + 10, center_y + 6)

        elif self.icon_type == "close":
            # Draw X icon
            painter.drawLine(center_x - 6, center_y - 6, center_x + 6, center_y + 6)
            painter.drawLine(center_x + 6, center_y - 6, center_x - 6, center_y + 6)

        elif self.icon_type == "plus":
            # Draw + icon
            line_length = self.icon_size // 3
            painter.drawLine(center_x, center_y - line_length, center_x, center_y + line_length)
            painter.drawLine(center_x - line_length, center_y, center_x + line_length, center_y)

        elif self.icon_type == "play":
            # Draw play triangle (larger to match plus icon scale)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            triangle = QtGui.QPolygon([
                QtCore.QPoint(center_x - 6, center_y - 9),
                QtCore.QPoint(center_x - 6, center_y + 9),
                QtCore.QPoint(center_x + 10, center_y)
            ])
            painter.drawPolygon(triangle)

        elif self.icon_type == "stop":
            # Draw stop square
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawRect(center_x - 6, center_y - 6, 12, 12)

        elif self.icon_type == "refresh":
            # Draw circular arrow (refresh icon)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Draw arc
            rect = QtCore.QRect(center_x - 8, center_y - 8, 16, 16)
            painter.drawArc(rect, 45 * 16, 270 * 16)
            # Draw arrow head
            arrow_points = QtGui.QPolygon([
                QtCore.QPoint(center_x + 6, center_y - 8),
                QtCore.QPoint(center_x + 6, center_y - 2),
                QtCore.QPoint(center_x + 10, center_y - 5)
            ])
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawPolygon(arrow_points)

        elif self.icon_type == "chevron-left":
            # Draw left-pointing chevron (double arrow)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # First chevron
            painter.drawLine(center_x + 2, center_y - 6, center_x - 3, center_y)
            painter.drawLine(center_x - 3, center_y, center_x + 2, center_y + 6)
            # Second chevron
            painter.drawLine(center_x + 6, center_y - 6, center_x + 1, center_y)
            painter.drawLine(center_x + 1, center_y, center_x + 6, center_y + 6)

        elif self.icon_type == "chevron-right":
            # Draw right-pointing chevron (double arrow)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # First chevron
            painter.drawLine(center_x - 6, center_y - 6, center_x - 1, center_y)
            painter.drawLine(center_x - 1, center_y, center_x - 6, center_y + 6)
            # Second chevron
            painter.drawLine(center_x - 2, center_y - 6, center_x + 3, center_y)
            painter.drawLine(center_x + 3, center_y, center_x - 2, center_y + 6)

        elif self.icon_type == "gear":
            # Draw gear/cog icon
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Outer circle (gear body)
            painter.drawEllipse(center_x - 6, center_y - 6, 12, 12)
            # Inner circle (hole)
            painter.setBrush(QtGui.QColor(220, 220, 220))
            painter.drawEllipse(center_x - 2, center_y - 2, 4, 4)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Teeth: 6 short lines radiating outward at 60-degree intervals
            import math
            for angle_deg in range(0, 360, 60):
                rad = math.radians(angle_deg)
                x1 = center_x + int(6 * math.cos(rad))
                y1 = center_y + int(6 * math.sin(rad))
                x2 = center_x + int(9 * math.cos(rad))
                y2 = center_y + int(9 * math.sin(rad))
                painter.drawLine(x1, y1, x2, y2)

        elif self.icon_type == "image-edit":
            # Draw image frame with pencil overlay
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Image frame (rectangle)
            painter.drawRect(center_x - 8, center_y - 6, 12, 12)
            # Mountain shape inside (simple triangle)
            mountain = QtGui.QPolygon([
                QtCore.QPoint(center_x - 6, center_y + 4),
                QtCore.QPoint(center_x - 2, center_y - 1),
                QtCore.QPoint(center_x + 2, center_y + 4),
            ])
            painter.drawPolyline(mountain)
            # Pencil (diagonal line in bottom-right)
            painter.drawLine(center_x + 2, center_y + 7, center_x + 9, center_y)
            # Pencil tip
            painter.drawLine(center_x + 9, center_y, center_x + 7, center_y + 1)

        elif self.icon_type == "home":
            # Draw house icon
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            # Roof (triangle)
            roof = QtGui.QPolygon([
                QtCore.QPoint(center_x, center_y - 8),
                QtCore.QPoint(center_x - 9, center_y - 1),
                QtCore.QPoint(center_x + 9, center_y - 1),
            ])
            painter.drawPolygon(roof)
            # House body (rectangle)
            painter.drawRect(center_x - 6, center_y - 1, 12, 9)
            # Door (small rectangle)
            painter.drawRect(center_x - 2, center_y + 2, 4, 6)


class OverlayListItem(QtWidgets.QWidget):
    """Custom widget for overlay list items with name, toggle, and delete button."""

    def __init__(self, name: str, region_id: str, parent=None):
        super().__init__(parent)
        self.region_id = region_id
        self.setup_ui(name)

    def setup_ui(self, name: str):
        """Set up the UI for the list item."""
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Name label on the left
        self.name_label = QtWidgets.QLabel(name)
        self.name_label.setStyleSheet("""
            color: #EEEEEE;
            background-color: transparent;
            font-size: 13px;
            font-weight: 400;
        """)
        layout.addWidget(self.name_label, 1)  # Stretch factor

        # Toggle button (Eye icon) - acts as a toggle switch
        self.toggle_btn = IconButton("eye")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)  # Enabled by default
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
        """)
        self.toggle_btn.toggled.connect(self._update_toggle_icon)
        layout.addWidget(self.toggle_btn, 0)

        # Delete button (X icon)
        self.delete_btn = IconButton("close")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.delete_btn, 0)

        self.setLayout(layout)
        self.setStyleSheet("""
            OverlayListItem {
                background-color: transparent;
                border-radius: 6px;
                padding: 2px;
            }
            OverlayListItem:hover {
                background-color: rgba(70, 70, 70, 120);
            }
        """)

    def _update_toggle_icon(self, checked: bool):
        """Update the toggle button icon based on state."""
        self.toggle_btn.icon_type = "eye" if checked else "eye-slash"
        self.toggle_btn.update()
