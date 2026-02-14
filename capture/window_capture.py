import ctypes
from ctypes import windll, wintypes
from PIL import Image
from error_handler import safe_execute, SafeWindowCapture

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

    @safe_execute(default_return=[], log_errors=True, error_message="Failed to list window names")
    def list_window_names(self):
        """Returns a list of visible window titles."""
        titles = []
        def enum_windows_proc(hwnd, lParam):
            try:
                length = windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0 and windll.user32.IsWindowVisible(hwnd):
                    buff = ctypes.create_unicode_buffer(length + 1)
                    windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    titles.append(buff.value)
            except Exception:
                pass  # Skip windows that cause errors
            return True

        try:
            # Define the callback type for EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            windll.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
        except Exception:
            pass  # Return empty list on error
        return titles

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to set window by title")
    def set_window_by_title(self, title):
        if not title:
            self.hwnd = None
            return
        try:
            self.hwnd = windll.user32.FindWindowW(None, title)
            # Validate the window handle
            if self.hwnd and not SafeWindowCapture.is_window_valid(self.hwnd):
                self.hwnd = None
        except Exception:
            self.hwnd = None

    @safe_execute(default_return=(0, 0, 0, 0), log_errors=True, error_message="Failed to get window rect")
    def get_window_rect(self):
        """Returns x, y, w, h of the window in screen coordinates."""
        if not self.hwnd or not SafeWindowCapture.is_window_valid(self.hwnd):
            return 0, 0, 0, 0
        try:
            rect = wintypes.RECT()
            if windll.user32.GetWindowRect(self.hwnd, ctypes.byref(rect)) == 0:
                return 0, 0, 0, 0
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return 0, 0, 0, 0
            return rect.left, rect.top, w, h
        except Exception:
            return 0, 0, 0, 0

    @safe_execute(default_return=None, log_errors=True, error_message="Failed to capture screenshot")
    def screenshot(self):
        """
        Captures the specific window using PrintWindow (background capture).
        Returns a PIL Image.
        """
        if not self.hwnd or not SafeWindowCapture.is_window_valid(self.hwnd):
            return None

        hwndDC = None
        mfcDC = None
        saveBitMap = None

        try:
            # Get Client Dimensions (Inner window area, excluding title bar)
            # Using GetClientRect ensures we don't get black borders
            rect = wintypes.RECT()
            if windll.user32.GetClientRect(self.hwnd, ctypes.byref(rect)) == 0:
                return None
            w = rect.right - rect.left
            h = rect.bottom - rect.top

            if w == 0 or h == 0 or w > 10000 or h > 10000:  # Sanity check
                return None

            # Setup Bitmaps (GDI Magic)
            hwndDC = windll.user32.GetWindowDC(self.hwnd)
            if not hwndDC:
                return None

            mfcDC = windll.gdi32.CreateCompatibleDC(hwndDC)
            if not mfcDC:
                windll.user32.ReleaseDC(self.hwnd, hwndDC)
                return None

            saveBitMap = windll.gdi32.CreateCompatibleBitmap(hwndDC, w, h)
            if not saveBitMap:
                windll.gdi32.DeleteDC(mfcDC)
                windll.user32.ReleaseDC(self.hwnd, hwndDC)
                return None

            windll.gdi32.SelectObject(mfcDC, saveBitMap)

            # PrintWindow
            # The '2' flag is PW_CLIENTONLY - captures content only, no window frame
            result = windll.user32.PrintWindow(self.hwnd, mfcDC, 2)

            if result == 0:
                # Fallback: Sometimes PrintWindow fails on hardware accelerated windows (chrome/electron)
                # In that case, we can try BitBlt (standard screenshot)
                windll.gdi32.BitBlt(mfcDC, 0, 0, w, h, hwndDC, 0, 0, 0x00CC0020)  # SRCCOPY

            # Configure the Bitmap Header
            bmpinfo = BITMAPINFOHEADER()
            bmpinfo.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmpinfo.biWidth = w
            bmpinfo.biHeight = -h  # Negative height flips the image upright (Top-Down)
            bmpinfo.biPlanes = 1
            bmpinfo.biBitCount = 32
            bmpinfo.biCompression = 0  # BI_RGB

            # Get the actual pixel data
            buffer_len = w * h * 4
            if buffer_len <= 0 or buffer_len > 100000000:  # Sanity check (max ~100MB)
                return None

            buffer = ctypes.create_string_buffer(buffer_len)

            if windll.gdi32.GetDIBits(mfcDC, saveBitMap, 0, h, buffer, ctypes.byref(bmpinfo), 0) == 0:
                return None

            # Create PIL Image
            # Note: Windows bitmaps are usually BGRX, Pillow expects RGB or RGBA.
            try:
                image = Image.frombuffer("RGB", (w, h), buffer, "raw", "BGRX", 0, 1)
                if not SafeWindowCapture.validate_image(image):
                    return None
                return image
            except Exception:
                return None

        except Exception:
            return None
        finally:
            # Always cleanup resources
            try:
                if saveBitMap:
                    windll.gdi32.DeleteObject(saveBitMap)
                if mfcDC:
                    windll.gdi32.DeleteDC(mfcDC)
                if hwndDC and self.hwnd:
                    windll.user32.ReleaseDC(self.hwnd, hwndDC)
            except Exception:
                pass  # Ignore cleanup errors
