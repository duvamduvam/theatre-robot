import logging

from controller.gui.gui_utils import GuiUtils


class ImageObserverFeedBack:
    def __init__(self, canvas, image_frame, x, y, image_type):
        self.x = x
        self.y = y
        self.image_type = image_type
        self.canvas = canvas
        self.image_frame = image_frame
        self.current_image_name = ""
        self.current_image = None
        self.update_image()

    def update_image(self):
        image = self.image_frame.current_image()
        if image and self.current_image_name != image:
            logging.debug("update image {}".format(image))
            self.current_image_name = image
            self.canvas.update()
            self.current_image = GuiUtils.copy_image(self.canvas, image, x=self.x, y=self.y)
            #self.current_image = GuiUtils.set_image(self.canvas, self.x, self.y, self.image_type, image, 10)
            self.canvas.update()
        self.canvas.after(50, self.update_image)
