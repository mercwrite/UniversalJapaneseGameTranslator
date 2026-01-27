from PyQt6 import QtWidgets, QtCore, QtGui
from error_handler import safe_execute


class TextBoxOverlay(QtWidgets.QLabel):
    # Signal emitted when position or size changes
    geometry_changed = QtCore.pyqtSignal(int, int, int, int)  # x, y, width, height

    def __init__(self, x, y, w, h, initial_opacity=200):
        super().__init__()
        self.setGeometry(x, y, w, h)

        # State variable to hold opacity
        self.bg_opacity = initial_opacity

        # Window Flags
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        # Remove WA_TransparentForMouseEvents to enable mouse interaction

        # Mouse interaction state
        self.drag_start_position = None
        self.resize_edge = None  # 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw', or None
        self.resize_handle_size = 8  # Size of resize handles in pixels
        self.min_size = 50  # Minimum overlay size

        # Text settings
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText("Waiting for text...")

        # Set font style only (background is drawn in paintEvent)
        self.setStyleSheet(
            """
            color: white;
            font-size: 14px;
            font-weight: bold;
            padding: 5px;
        """
        )

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

        self.show()

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to set opacity")
    def set_background_opacity(self, alpha: int) -> None:
        """Update the background opacity and trigger a repaint."""
        try:
            # Clamp opacity to valid range
            alpha = max(0, min(255, int(alpha)))
            self.bg_opacity = alpha
            self.update()  # This triggers paintEvent immediately
        except Exception:
            pass  # Already handled by decorator

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update text")
    def update_text(self, text: str) -> None:
        """Update the overlay text."""
        try:
            if text is None:
                text = ""
            # Ensure text is a string and limit length to prevent UI issues
            text = str(text)[:1000]  # Limit to 1000 characters
            self.setText(text)
        except Exception:
            pass  # Already handled by decorator

    def get_resize_edge(self, pos: QtCore.QPoint) -> str | None:
        """Determine which resize edge/corner the mouse is over."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        handle_size = self.resize_handle_size

        # Check corners first (they take priority)
        if x < handle_size and y < handle_size:
            return "nw"
        elif x >= w - handle_size and y < handle_size:
            return "ne"
        elif x < handle_size and y >= h - handle_size:
            return "sw"
        elif x >= w - handle_size and y >= h - handle_size:
            return "se"
        # Check edges
        elif y < handle_size:
            return "n"
        elif y >= h - handle_size:
            return "s"
        elif x < handle_size:
            return "w"
        elif x >= w - handle_size:
            return "e"
        return None

    def get_cursor_for_edge(self, edge: str | None) -> QtCore.Qt.CursorShape:
        """Get the appropriate cursor for a resize edge."""
        cursor_map = {
            "n": QtCore.Qt.CursorShape.SizeVerCursor,
            "s": QtCore.Qt.CursorShape.SizeVerCursor,
            "e": QtCore.Qt.CursorShape.SizeHorCursor,
            "w": QtCore.Qt.CursorShape.SizeHorCursor,
            "ne": QtCore.Qt.CursorShape.SizeBDiagCursor,
            "nw": QtCore.Qt.CursorShape.SizeFDiagCursor,
            "se": QtCore.Qt.CursorShape.SizeFDiagCursor,
            "sw": QtCore.Qt.CursorShape.SizeBDiagCursor,
        }
        return cursor_map.get(edge, QtCore.Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        """Handle mouse press for dragging and resizing."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.resize_edge = self.get_resize_edge(event.pos())
            if self.resize_edge is None:
                # Start dragging
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            else:
                # Start resizing
                self.drag_start_position = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        """Handle mouse move for cursor changes and dragging/resizing."""
        if self.drag_start_position is None:
            # Update cursor based on hover position
            edge = self.get_resize_edge(event.pos())
            self.setCursor(self.get_cursor_for_edge(edge))
        elif event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            # Currently dragging or resizing
            if self.resize_edge is None:
                # Dragging
                new_pos = event.globalPosition().toPoint() - self.drag_start_position
                self.move(new_pos)
                self._emit_geometry_changed()
            else:
                # Resizing
                current_rect = self.geometry()
                global_pos = event.globalPosition().toPoint()
                delta = global_pos - self.drag_start_position
                
                new_rect = current_rect
                edge = self.resize_edge

                # Handle horizontal resizing
                if "e" in edge:
                    new_width = current_rect.width() + delta.x()
                    if new_width >= self.min_size:
                        new_rect.setWidth(new_width)
                elif "w" in edge:
                    new_width = current_rect.width() - delta.x()
                    if new_width >= self.min_size:
                        new_rect.setX(current_rect.x() + delta.x())
                        new_rect.setWidth(new_width)

                # Handle vertical resizing
                if "s" in edge:
                    new_height = current_rect.height() + delta.y()
                    if new_height >= self.min_size:
                        new_rect.setHeight(new_height)
                elif "n" in edge:
                    new_height = current_rect.height() - delta.y()
                    if new_height >= self.min_size:
                        new_rect.setY(current_rect.y() + delta.y())
                        new_rect.setHeight(new_height)

                # Update the geometry
                if new_rect != current_rect:
                    self.setGeometry(new_rect)
                    self.drag_start_position = global_pos
                    self._emit_geometry_changed()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        """Handle mouse release to stop dragging/resizing."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_start_position = None
            self.resize_edge = None
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to emit geometry changed")
    def _emit_geometry_changed(self) -> None:
        """Emit signal with current geometry."""
        try:
            rect = self.geometry()
            # Validate geometry before emitting
            if rect.width() > 0 and rect.height() > 0:
                self.geometry_changed.emit(rect.x(), rect.y(), rect.width(), rect.height())
        except Exception:
            pass  # Already handled by decorator

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        """Draw a rounded translucent rectangle behind the text."""
        try:
            painter = QtGui.QPainter(self)
            if not painter.isActive():
                return
            
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

            # Background color (grey with dynamic alpha)
            brush_color = QtGui.QColor(50, 50, 50, self.bg_opacity)
            painter.setBrush(QtGui.QBrush(brush_color))

            # Border (faint white)
            pen_color = QtGui.QColor(255, 255, 255, 50)
            painter.setPen(QtGui.QPen(pen_color, 1))

            # Draw the rounded rectangle
            painter.drawRoundedRect(self.rect(), 10, 10)

            # Draw resize handles (small squares at corners and edges)
            handle_size = self.resize_handle_size
            handle_color = QtGui.QColor(255, 255, 255, 150)
            painter.setPen(QtGui.QPen(handle_color, 1))
            painter.setBrush(QtGui.QBrush(handle_color))

            rect = self.rect()
            # Only draw handles if widget is large enough
            if rect.width() > handle_size * 2 and rect.height() > handle_size * 2:
                # Corners
                painter.drawRect(0, 0, handle_size, handle_size)
                painter.drawRect(rect.width() - handle_size, 0, handle_size, handle_size)
                painter.drawRect(0, rect.height() - handle_size, handle_size, handle_size)
                painter.drawRect(
                    rect.width() - handle_size,
                    rect.height() - handle_size,
                    handle_size,
                    handle_size,
                )
                # Edges (centered)
                mid_x = rect.width() // 2
                mid_y = rect.height() // 2
                painter.drawRect(mid_x - handle_size // 2, 0, handle_size, handle_size)
                painter.drawRect(
                    mid_x - handle_size // 2,
                    rect.height() - handle_size,
                    handle_size,
                    handle_size,
                )
                painter.drawRect(0, mid_y - handle_size // 2, handle_size, handle_size)
                painter.drawRect(
                    rect.width() - handle_size,
                    mid_y - handle_size // 2,
                    handle_size,
                    handle_size,
                )

            # Draw the text on top of the rectangle
            super().paintEvent(event)
        except Exception:
            # Fallback: just draw text without background on error
            try:
                super().paintEvent(event)
            except Exception:
                pass

