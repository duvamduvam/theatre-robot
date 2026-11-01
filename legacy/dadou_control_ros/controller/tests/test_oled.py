import unittest

from controller.gui.pillow.ImageGenerator import ImageGenerator
#from controller.gui.pillow.tk-pillow-gui


class MyTestCase(unittest.TestCase):
    def test_oled(self):
        #root = tk.Tk()
        #root.title("Fenêtre avec Image Mise à Jour")

        image_generator = ImageGenerator()
        #app = KeyListenerApp(root, image_generator)
        #keyboard_listener = KeyboardListener(image_generator)

        #root.mainloop()


if __name__ == '__main__':
    unittest.main()
