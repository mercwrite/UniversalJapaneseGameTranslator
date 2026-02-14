from PyQt6 import QtWidgets, QtCore, QtGui


class Snipper(QtWidgets.QWidget):
    region_selected = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()

        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # Ensure the overlay covers all screens, not just the primary one
        screen_geometry = QtWidgets.QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(screen_geometry)

        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.show()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
        painter = QtGui.QPainter(self)

        # Light dim over the whole screen
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 80))

        if self.begin == self.end:
            return

        pen = QtGui.QPen(QtGui.QColor("red"))
        pen.setWidth(2)
        painter.setPen(pen)

        # Transparent fill for the selected box so you can see the text clearly
        painter.setBrush(QtGui.QColor(0, 0, 0, 0))

        rect = QtCore.QRect(self.begin, self.end)
        painter.drawRect(rect.normalized())

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
        rect = QtCore.QRect(self.begin, self.end).normalized()

        # Handle cases where user just clicked without dragging
        if rect.width() < 10 or rect.height() < 10:
            self.hide()
            return

        selection = {
            "left": int(rect.x()),
            "top": int(rect.y()),
            "width": int(rect.width()),
            "height": int(rect.height()),
        }

        self.region_selected.emit(selection)

        # Always hide (never close) - controller handles deletion
        self.hide()

