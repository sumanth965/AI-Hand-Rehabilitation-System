"""
Threaded Webcam Stream for the Zero-Keyboard AI Physiotherapy System.
High-performance non-blocking capture to keep the main loop at 60 FPS.
"""

import cv2
import threading
import time


class WebcamStream:
    """High-performance non-blocking threaded webcam capture"""
    
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height
        self.stream = None
        self.grabbed = False
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.init_done = False
        self.init_error = False
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self
    
    def _update(self):
        # Open camera in background thread to prevent blocking Pygame GUI thread
        try:
            self.stream = cv2.VideoCapture(self.src)
            if not self.stream.isOpened():
                raise RuntimeError("Failed to open camera")
            
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.stream.set(cv2.CAP_PROP_FPS, 30)
            self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            grabbed, frame = self.stream.read()
            if grabbed and frame is not None:
                with self.lock:
                    self.grabbed = grabbed
                    self.frame = frame
            self.init_done = True
        except Exception as e:
            print(f"Background camera initialization failed: {e}")
            self.init_error = True
            self.init_done = True
            return
            
        while self.running:
            try:
                grabbed, frame = self.stream.read()
                if grabbed and frame is not None:
                    with self.lock:
                        self.grabbed = grabbed
                        self.frame = frame
            except Exception:
                pass  # Never crash the tracking thread
            time.sleep(0.001)

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return self.grabbed, self.frame.copy()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        if self.stream is not None:
            try:
                self.stream.release()
            except Exception:
                pass
