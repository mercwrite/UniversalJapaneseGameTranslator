import ctypes
from ctypes import windll, wintypes
from PIL import Image

# Manually define the C-Structure that is missing from wintypes
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', ctypes.c_uint32),
        ('biWidth', ctypes.c_long),
        ('biHeight', ctypes.c_long),
        ('biPlanes', ctypes.c_ushort),
        ('biBitCount', ctypes.c_ushort),
        ('biCompression', ctypes.c_uint32),
        ('biSizeImage', ctypes.c_uint32),
        ('biXPelsPerMeter', ctypes.c_long),
        ('biYPelsPerMeter', ctypes.c_long),
        ('biClrUsed', ctypes.c_uint32),
        ('biClrImportant', ctypes.c_uint32),
    ]

class WindowCapture:
    def __init__(self, window_name=None):
        self.hwnd = None
        if window_name:
            self.hwnd = windll.user32.FindWindowW(None, window_name)

    def list_window_names(self):
        """Returns a list of visible window titles."""
        titles = []
        def enum_windows_proc(hwnd, lParam):
            length = windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0 and windll.user32.IsWindowVisible(hwnd):
                buff = ctypes.create_unicode_buffer(length + 1)
                windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                titles.append(buff.value)
            return True
            
        # Define the callback type for EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        return titles

    def set_window_by_title(self, title):
        self.hwnd = windll.user32.FindWindowW(None, title)

    def get_window_rect(self):
        """Returns x, y, w, h of the window in screen coordinates."""
        if not self.hwnd: return 0,0,0,0
        rect = wintypes.RECT()
        windll.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        return rect.left, rect.top, w, h

    def screenshot(self):
        """
        Captures the specific window using PrintWindow (background capture).
        Returns a PIL Image.
        """
        if not self.hwnd: return None

        # Get Client Dimensions (Inner window area, excluding title bar)
        # Using GetClientRect ensures we don't get black borders
        rect = wintypes.RECT()
        windll.user32.GetClientRect(self.hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        if w == 0 or h == 0: return None

        # Setup Bitmaps (GDI Magic)
        hwndDC = windll.user32.GetWindowDC(self.hwnd)
        mfcDC  = windll.gdi32.CreateCompatibleDC(hwndDC)
        saveBitMap = windll.gdi32.CreateCompatibleBitmap(hwndDC, w, h)
        windll.gdi32.SelectObject(mfcDC, saveBitMap)

        # PrintWindow 
        # The '2' flag is PW_CLIENTONLY - captures content only, no window frame
        result = windll.user32.PrintWindow(self.hwnd, mfcDC, 2)

        if result == 0:
            # Fallback: Sometimes PrintWindow fails on hardware accelerated windows (chrome/electron)
            # In that case, we can try BitBlt (standard screenshot)
            windll.gdi32.BitBlt(mfcDC, 0, 0, w, h, hwndDC, 0, 0, 0x00CC0020) # SRCCOPY

        # Configure the Bitmap Header
        bmpinfo = BITMAPINFOHEADER()
        bmpinfo.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmpinfo.biWidth = w
        bmpinfo.biHeight = -h # Negative height flips the image upright (Top-Down)
        bmpinfo.biPlanes = 1
        bmpinfo.biBitCount = 32
        bmpinfo.biCompression = 0 # BI_RGB

        # Get the actual pixel data
        buffer_len = w * h * 4
        buffer = ctypes.create_string_buffer(buffer_len)
        
        windll.gdi32.GetDIBits(mfcDC, saveBitMap, 0, h, buffer, ctypes.byref(bmpinfo), 0)

        # Create PIL Image
        # Note: Windows bitmaps are usually BGRX, Pillow expects RGB or RGBA.
        image = Image.frombuffer("RGB", (w, h), buffer, "raw", "BGRX", 0, 1)

        # 7. Cleanup
        windll.gdi32.DeleteObject(saveBitMap)
        windll.gdi32.DeleteDC(mfcDC)
        windll.user32.ReleaseDC(self.hwnd, hwndDC)

        return image