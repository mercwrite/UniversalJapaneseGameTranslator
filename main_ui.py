#Full application and translation

import sys
from PyQt6 import QtWidgets, QtCore, QtGui
import uuid
from manga_ocr import MangaOcr
from window_capture import WindowCapture
import numpy as np
from sugoi_wrapper import SugoiTranslator
from image_processor import ImagePreprocessor
from rapid_wrapper import RapidOCRWrapper
from winocr_wrapper import WindowsOCR
from qwen_wrapper import LocalVisionAI

from PyQt6 import QtWidgets, QtCore, QtGui

class TextBoxOverlay(QtWidgets.QLabel):
    def __init__(self, x, y, w, h, initial_opacity=200):
        super().__init__()
        self.setGeometry(x, y, w, h)
        
        # 1. State Variable to hold opacity
        self.bg_opacity = initial_opacity
        
        # 2. Window Flags
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint | 
            QtCore.Qt.WindowType.WindowStaysOnTopHint | 
            QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        # 3. Text Settings
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText("Waiting for text...")

        # 4. Set Font Style ONLY (Do not set background here anymore)
        self.setStyleSheet("""
            color: white; 
            font-size: 14px; 
            font-weight: bold;
            padding: 5px;
        """)
        
        self.show()

    def set_background_opacity(self, alpha):
        """
        Updates the variable and forces a repaint.
        """
        self.bg_opacity = alpha
        self.update() # This triggers paintEvent immediately

    def update_text(self, text):
        self.setText(text)

    def paintEvent(self, event):
        """
        We draw the background manually here.
        """
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # A. Define the Background Color (Grey with dynamic Alpha)
        # R=50, G=50, B=50, Alpha=self.bg_opacity
        brush_color = QtGui.QColor(50, 50, 50, self.bg_opacity)
        painter.setBrush(QtGui.QBrush(brush_color))

        # B. Define the Border (Faint white)
        pen_color = QtGui.QColor(255, 255, 255, 50)
        painter.setPen(QtGui.QPen(pen_color, 1))

        # C. Draw the Rounded Rectangle
        # rect() gets the current size of the label
        # 10, 10 is the X and Y radius for the corners
        painter.drawRoundedRect(self.rect(), 10, 10)

        # D. Draw the Text
        # We call super() LAST so the text is drawn ON TOP of the rectangle
        super().paintEvent(event)

class Snipper(QtWidgets.QWidget):
    region_selected = QtCore.pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()

        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint | 
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        # This ensures the overlay covers all your screens, not just the primary one
        screen_geometry = QtWidgets.QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(screen_geometry)

        self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
        self.show()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        
        # 100 is a light dim. Increase to 200 for a darker dim.
        painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 80)) 

        if self.begin == self.end:
            return
            
        pen = QtGui.QPen(QtGui.QColor('red'))
        pen.setWidth(2)
        painter.setPen(pen)

        # Clear/Transparent fill for the selected box so you can see the text clearly
        painter.setBrush(QtGui.QColor(0, 0, 0, 0)) 
        
        rect = QtCore.QRect(self.begin, self.end)
        painter.drawRect(rect.normalized())

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = self.begin
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        rect = QtCore.QRect(self.begin, self.end).normalized()
        
        # Handle cases where user just clicked without dragging
        if rect.width() < 10 or rect.height() < 10:
            self.close()
            return

        selection = {
            'left': int(rect.x()),
            'top': int(rect.y()),
            'width': int(rect.width()),
            'height': int(rect.height())
        }
        
        self.region_selected.emit(selection)
        self.close()

class ControllerWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Overlay Manager")
        self.resize(400, 400)

        # --- Data Storage ---
        # Dictionary to hold data: 
        # { 'uuid_string': { 'rect': dict, 'overlay': TextBoxOverlay_Object } }
        self.active_regions = {} 

        self.last_images = {}

        # --- UI Layout ---
        layout = QtWidgets.QVBoxLayout()
        
        slider_layout = QtWidgets.QHBoxLayout()
        
        self.lbl_opacity = QtWidgets.QLabel("Background Opacity: 80%")
        slider_layout.addWidget(self.lbl_opacity)
        
        self.slider_opacity = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(0, 255) # 0 = Invisible, 255 = Solid
        self.slider_opacity.setValue(200)    # Default start value (~80%)
        self.slider_opacity.valueChanged.connect(self.update_opacity)
        slider_layout.addWidget(self.slider_opacity)
        
        layout.addLayout(slider_layout)

        # List of active regions
        self.region_list = QtWidgets.QListWidget()
        layout.addWidget(self.region_list)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_add = QtWidgets.QPushButton("Add New Region")
        self.btn_add.clicked.connect(self.activate_snipper)
        btn_layout.addWidget(self.btn_add)

        self.btn_del = QtWidgets.QPushButton("Delete Selected")
        self.btn_del.clicked.connect(self.delete_region)
        btn_layout.addWidget(self.btn_del)
        
        layout.addLayout(btn_layout)

        self.btn_start = QtWidgets.QPushButton("Start Translation")
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self.toggle_translation)
        layout.addWidget(self.btn_start)

        self.win_cap = WindowCapture()


        # Add Dropdown for Game Selection
        self.combo_games = QtWidgets.QComboBox()
        self.combo_games.addItems(self.win_cap.list_window_names())
        self.combo_games.currentIndexChanged.connect(self.select_game_window)
        layout.addWidget(QtWidgets.QLabel("Select Game Window:"))
        layout.addWidget(self.combo_games)

        # Add a Refresh Button (games might open after this app)
        btn_refresh = QtWidgets.QPushButton("Refresh Window List")
        btn_refresh.clicked.connect(self.refresh_window_list)
        layout.addWidget(btn_refresh)

        self.setLayout(layout)

        # --- Backend ---
        #self.mocr = MangaOcr()
        path_to_model = "sugoi_model" 
        self.vision_ai = LocalVisionAI()
        self.translator = SugoiTranslator(path_to_model, device="auto")
        self.timer = QtCore.QTimer()
        self.timer.setInterval(100) # 2 seconds
        self.timer.timeout.connect(self.run_batch_pipeline)
        
    def update_opacity(self):
        current_val = self.slider_opacity.value() # Returns 0-255
        self.lbl_opacity.setText(f"Background Opacity: {int(current_val/255*100)}%")

        for rid, data in self.active_regions.items():
            # This calls the NEW set_background_opacity function above
            data['overlay'].set_background_opacity(current_val)

    def on_region_added(self, area):
        """
        Updated to use the slider's current value for new boxes.
        """
        self.show()
        region_id = str(uuid.uuid4())[:8]

        # Get current slider value so the new box matches existing ones
        current_opacity = self.slider_opacity.value()

        # Create overlay with current opacity
        overlay = TextBoxOverlay(
            area['left'], area['top'], 
            area['width'], area['height'],
            initial_opacity=current_opacity
        )
        
        self.active_regions[region_id] = {
            'rect': area,
            'overlay': overlay
        }

    def calculate_image_diff(self, img1, img2):
        """
        Returns a 'difference score' between two images.
        0 = Identical.
        Higher numbers = More different.
        """
        if img1 is None or img2 is None:
            return 1000.0 # Force update if no history
        
        # Ensure sizes match (handling resize edge cases)
        if img1.size != img2.size:
            return 1000.0

        # Convert to Grayscale (L) and then to NumPy Array
        # We use grayscale because color changes (lighting effects) matter less than text shapes
        arr1 = np.array(img1.convert('L'), dtype=np.int16)
        arr2 = np.array(img2.convert('L'), dtype=np.int16)

        # Calculate absolute difference
        diff = np.abs(arr1 - arr2)
        
        # Return the mean difference (average change per pixel)
        return np.mean(diff)


    def refresh_window_list(self):
        current = self.combo_games.currentText()
        self.combo_games.clear()
        self.combo_games.addItems(self.win_cap.list_window_names())
        self.combo_games.setCurrentText(current)

    def select_game_window(self):
        title = self.combo_games.currentText()
        self.win_cap.set_window_by_title(title)

    def activate_snipper(self):
        self.hide() # Hide controller
        self.snipper = Snipper()
        self.snipper.region_selected.connect(self.on_region_added)
        self.snipper.show()

    def on_region_added(self, area):
        self.show() # Show controller
        
        # 1. Generate a unique ID
        region_id = str(uuid.uuid4())[:8] # Short UUID
        
        # 2. Create the Overlay Window immediately
        overlay = TextBoxOverlay(
            area['left'], area['top'], 
            area['width'], area['height']
        )
        
        # 3. Store the data
        self.active_regions[region_id] = {
            'rect': area,
            'overlay': overlay
        }

        # 4. Add to List Widget for management
        item_text = f"Region {region_id} - ({area['width']}x{area['height']})"
        list_item = QtWidgets.QListWidgetItem(item_text)
        list_item.setData(QtCore.Qt.ItemDataRole.UserRole, region_id) # Store ID in the item
        self.region_list.addItem(list_item)

    def delete_region(self):
        # Get selected item
        selected_items = self.region_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            # Retrieve ID
            region_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
            
            # Close the actual overlay window
            if region_id in self.active_regions:
                self.active_regions[region_id]['overlay'].close()
                del self.active_regions[region_id]
            
            # Remove from list UI
            self.region_list.takeItem(self.region_list.row(item))

    def toggle_translation(self):
        if self.btn_start.isChecked():
            self.btn_start.setText("Stop Translation")
            self.timer.start()
        else:
            self.btn_start.setText("Start Translation")
            self.timer.stop()

    def run_batch_pipeline(self):
        """
        Runs OCR on ALL active regions.
        """
        if not self.active_regions or not self.win_cap.hwnd:
            return
        
        full_window_img = self.win_cap.screenshot()
        win_x, win_y, _, _ = self.win_cap.get_window_rect()

        for rid, data in self.active_regions.items():
            screen_rect = data['rect']

            # Convert Screen Coords -> Relative Window Coords
            # If the game is at Screen (100, 100) and the box is at Screen (150, 150)
            # The crop needs to be at Window (50, 50)
            rel_x = screen_rect['left'] - win_x
            rel_y = screen_rect['top'] - win_y
            rel_w = screen_rect['width']
            rel_h = screen_rect['height']

             # Safety check: Ensure crop is inside the window
            if rel_x < 0 or rel_y < 0:
                print(f"Region {rid} is outside the game window!")
                continue

            # Crop using Pillow
            current_crop = full_window_img.crop((rel_x, rel_y, rel_x + rel_w, rel_y + rel_h))
            


            #processed_crop = ImagePreprocessor.process(
            #    current_crop, 
            #    upscale_factor=3.5, 
            #)

            last_img = self.last_images.get(rid)
            diff_score = self.calculate_image_diff(current_crop, last_img)

            if diff_score < 2.0:
                continue
        
            self.last_images[rid] = current_crop
            # OCR
            jap_text = self.vision_ai.analyze(current_crop, mode="ocr")
            # Translate
            eng_text = self.translator.translate(jap_text)

            print(jap_text)
            print(eng_text)
            
            # Update the overlay object's text
            data['overlay'].update_text(eng_text)


# --- Entry Point ---
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())