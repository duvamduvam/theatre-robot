from pynput import keyboard
import threading

class KeyListener:
    def __init__(self):
        self.last_key = None
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.lock = threading.Lock()
        self.listener.start()

    def on_press(self, key):
        with self.lock:
            try:
                self.last_key = key.char
            except AttributeError:
                # For special keys like space, enter, etc.
                self.last_key = str(key)

        # Start a timer to reset the last key after 5 seconds
        timer = threading.Timer(5.0, self.reset_key)
        timer.start()

    def reset_key(self):
        with self.lock:
            self.last_key = None

    def lastkey(self):
        with self.lock:
            return self.last_key
