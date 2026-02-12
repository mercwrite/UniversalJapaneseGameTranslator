import time

class PerformanceLogger:
    def __init__(self):
        self.t_start = 0
        self.t_ocr_start = 0
        self.t_trans_start = 0
        self.records = []

    def start_cycle(self):
        """Call this immediately when the timer ticks."""
        self.t_start = time.perf_counter()

    def start_ocr(self):
        """Call this right before OCR.scan()"""
        self.t_ocr_start = time.perf_counter()

    def start_translation(self):
        """Call this right before translator.translate()"""
        self.t_trans_start = time.perf_counter()

    def end_cycle(self):
        """Call this after the UI updates."""
        t_end = time.perf_counter()
        
        # Calculate durations in milliseconds
        ocr_duration = (self.t_trans_start - self.t_ocr_start) * 1000
        trans_duration = (t_end - self.t_trans_start) * 1000
        total_duration = (t_end - self.t_start) * 1000
        
        return {
            "ocr_ms": int(ocr_duration),
            "trans_ms": int(trans_duration),
            "total_ms": int(total_duration)
        }