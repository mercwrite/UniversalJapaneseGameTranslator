from PyQt6 import QtWidgets, QtCore, QtGui
from error_handler import safe_execute


class TextBoxOverlay(QtWidgets.QLabel):
    # Signal emitted when position or size changes
    geometry_changed = QtCore.pyqtSignal(int, int, int, int)  # x, y, width, height
    # Signal emitted when the overlay is closed via its close button
    close_requested = QtCore.pyqtSignal()
    # Signals emitted when user starts/stops dragging or resizing
    interaction_started = QtCore.pyqtSignal()
    interaction_finished = QtCore.pyqtSignal()

    def __init__(self, x, y, w, h, initial_opacity=200, bg_color="#0D0D0D", text_color="#EEEEEE"):
        super().__init__()
        self.setGeometry(x, y, w, h)

        # State variable to hold opacity
        self.bg_opacity = initial_opacity

        # Custom colors
        self.bg_color = QtGui.QColor(bg_color)
        self.text_color = text_color

        # Window Flags - frameless, no-focus to prevent game stalling
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)

        # Mouse interaction state
        self.drag_start_position = None
        self.resize_edge = None
        self.resize_start_geometry = None
        self.resize_handle_size = 10
        self.min_size = 50

        # Close button visibility state
        self.close_button_visible = False

        # Hover state for visual feedback
        self.hover_edge = None

        # Text settings
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText("Translated Text Goes Here...")

        # Set text style with custom color
        self._apply_text_style()

        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

        # Create close button (initially hidden)
        self.close_button = QtWidgets.QPushButton("×", self)
        self.close_button.setFixedSize(26, 26)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 60, 60, 180);
                border: 1px solid rgba(120, 120, 120, 120);
                border-radius: 13px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 20px;
                font-family: Arial, sans-serif;
                padding: 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 220);
                border-color: rgba(160, 160, 160, 180);
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: rgba(100, 100, 100, 240);
            }
        """)
        self.close_button.hide()  # Hidden by default
        self.close_button.clicked.connect(self._on_close_clicked)
        self.update_close_button_position()

        self.show()
        self._apply_noactivate_style()

    def _apply_noactivate_style(self):
        """Apply Win32 WS_EX_NOACTIVATE to prevent game focus loss on click."""
        try:
            import ctypes
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
        except Exception:
            pass

    def _on_close_clicked(self):
        """Handle close button click - emit signal so controller can clean up."""
        self.close_requested.emit()

    def update_close_button_position(self):
        """Update close button position to top-right corner."""
        margin = 6
        self.close_button.move(
            self.width() - self.close_button.width() - margin,
            margin
        )

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Handle resize events to reposition close button."""
        super().resizeEvent(event)
        self.update_close_button_position()

    def enterEvent(self, event: QtGui.QEnterEvent) -> None:
        """Show close button when mouse enters the widget."""
        super().enterEvent(event)
        self.close_button_visible = True
        self.close_button.show()
        self.update()

    def leaveEvent(self, event: QtCore.QEvent) -> None:
        """Hide close button when mouse leaves the widget."""
        super().leaveEvent(event)
        self.close_button_visible = False
        self.close_button.hide()
        self.hover_edge = None
        self.update()

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to set opacity")
    def set_background_opacity(self, alpha: int) -> None:
        """Update the background opacity and trigger a repaint."""
        try:
            alpha = max(0, min(255, int(alpha)))
            self.bg_opacity = alpha
            self.update()
        except Exception:
            pass

    def _apply_text_style(self) -> None:
        """Apply text stylesheet with current text color."""
        self.setStyleSheet(f"""
            color: {self.text_color};
            font-size: 14px;
            font-weight: 400;
            font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
            padding: 12px 16px;
            line-height: 1.5;
            background-color: transparent;
        """)

    def set_bg_color(self, color_hex: str) -> None:
        """Update the overlay background color."""
        self.bg_color = QtGui.QColor(color_hex)
        self.update()

    def set_text_color(self, color_hex: str) -> None:
        """Update the overlay text color."""
        self.text_color = color_hex
        self._apply_text_style()
        self.update()

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to update text")
    def update_text(self, text: str) -> None:
        """Update the overlay text."""
        try:
            if text is None:
                text = ""
            text = str(text)[:1000]
            self.setText(text)
        except Exception:
            pass

    def get_resize_edge(self, pos: QtCore.QPoint) -> str | None:
        """Determine which resize edge/corner the mouse is over."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        handle_size = self.resize_handle_size
        
        # Don't allow resizing from top-right corner if close button is visible
        close_button_rect = self.close_button.geometry()
        if self.close_button_visible and close_button_rect.contains(pos):
            return None

        # Check corners first (but skip top-right if close button is there)
        if x < handle_size and y < handle_size:
            return "nw"
        elif x >= w - handle_size and y < handle_size:
            # Skip if mouse is over close button area
            if not (self.close_button_visible and close_button_rect.contains(pos)):
                return "ne"
        elif x < handle_size and y >= h - handle_size:
            return "sw"
        elif x >= w - handle_size and y >= h - handle_size:
            return "se"
        # Check edges
        elif y < handle_size:
            # Skip top edge if mouse is over close button
            if not (self.close_button_visible and close_button_rect.contains(pos)):
                return "n"
        elif y >= h - handle_size:
            return "s"
        elif x < handle_size:
            return "w"
        elif x >= w - handle_size:
            # Skip right edge if mouse is over close button
            if not (self.close_button_visible and close_button_rect.contains(pos)):
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

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press for dragging and resizing."""
        # Don't process if clicking on close button
        if self.close_button.underMouse():
            event.accept()
            return

        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.resize_edge = self.get_resize_edge(event.pos())
            if self.resize_edge is None:
                # Dragging mode - store offset from top-left corner
                self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            else:
                # Resizing mode - store current global position and geometry
                self.drag_start_position = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
            self.interaction_started.emit()
        event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move for cursor changes and dragging/resizing."""
        if self.drag_start_position is None:
            # Not dragging - just update cursor based on edge
            edge = self.get_resize_edge(event.pos())
            self.setCursor(self.get_cursor_for_edge(edge))
            # Update hover state for visual feedback
            if edge != self.hover_edge:
                self.hover_edge = edge
                self.update()
        elif event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            if self.resize_edge is None:
                # Dragging mode - move the window
                new_pos = event.globalPosition().toPoint() - self.drag_start_position
                self.move(new_pos)
                self._emit_geometry_changed()
            else:
                # Resizing mode - adjust size based on edge/corner
                global_pos = event.globalPosition().toPoint()
                delta = global_pos - self.drag_start_position

                # Start with original geometry from when resizing started
                start_rect = self.resize_start_geometry
                new_x = start_rect.x()
                new_y = start_rect.y()
                new_width = start_rect.width()
                new_height = start_rect.height()

                edge = self.resize_edge

                # Handle horizontal resizing
                if "e" in edge:
                    # Dragging east edge - increase width
                    new_width = start_rect.width() + delta.x()
                elif "w" in edge:
                    # Dragging west edge - move left and increase width
                    new_width = start_rect.width() - delta.x()
                    new_x = start_rect.x() + delta.x()

                # Handle vertical resizing
                if "s" in edge:
                    # Dragging south edge - increase height
                    new_height = start_rect.height() + delta.y()
                elif "n" in edge:
                    # Dragging north edge - move up and increase height
                    new_height = start_rect.height() - delta.y()
                    new_y = start_rect.y() + delta.y()

                # Apply minimum size constraints
                if new_width < self.min_size:
                    if "w" in edge:
                        # When dragging west edge, don't move if at minimum
                        new_x = start_rect.x() + start_rect.width() - self.min_size
                    new_width = self.min_size

                if new_height < self.min_size:
                    if "n" in edge:
                        # When dragging north edge, don't move if at minimum
                        new_y = start_rect.y() + start_rect.height() - self.min_size
                    new_height = self.min_size

                # Apply new geometry
                self.setGeometry(new_x, new_y, new_width, new_height)
                self._emit_geometry_changed()
        event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release to stop dragging/resizing."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag_start_position = None
            self.resize_edge = None
            self.resize_start_geometry = None
            # Update cursor based on current position
            edge = self.get_resize_edge(event.pos())
            self.setCursor(self.get_cursor_for_edge(edge))
            self.interaction_finished.emit()
        event.accept()

    @safe_execute(default_return=None, log_errors=False, error_message="Failed to emit geometry changed")
    def _emit_geometry_changed(self) -> None:
        """Emit signal with current geometry."""
        try:
            rect = self.geometry()
            if rect.width() > 0 and rect.height() > 0:
                self.geometry_changed.emit(rect.x(), rect.y(), rect.width(), rect.height())
        except Exception:
            pass

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Draw a rounded translucent rectangle with modern border."""
        try:
            painter = QtGui.QPainter(self)
            if not painter.isActive():
                return

            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

            # Semi-transparent background with custom color
            brush_color = QtGui.QColor(self.bg_color.red(), self.bg_color.green(), self.bg_color.blue(), self.bg_opacity)
            painter.setBrush(QtGui.QBrush(brush_color))

            # Border color - highlight if hovering over resize edge or dragging
            if self.hover_edge or self.resize_edge:
                # Brighter border when hovering over resize edge
                pen_color = QtGui.QColor(100, 160, 220, 220)
                border_width = 2
            else:
                # Normal subtle border
                border_alpha = min(200, int(self.bg_opacity * 0.8))
                pen_color = QtGui.QColor(80, 80, 80, border_alpha)
                border_width = 1

            painter.setPen(QtGui.QPen(pen_color, border_width))

            # Draw rounded rectangle with more rounded corners
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)

            # Draw the text on top
            super().paintEvent(event)
        except Exception:
            try:
                super().paintEvent(event)
            except Exception:
                pass
