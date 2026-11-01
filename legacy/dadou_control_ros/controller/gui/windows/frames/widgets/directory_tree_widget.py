import logging
import os
import tkinter as tk
import tkinter
from os import listdir
from os.path import isfile, join
from tkinter import X, TOP, ttk, NW

import PIL
from PIL import ImageTk
from PIL.Image import Image
from dadou_utils_ros.utils_static import MOUTH, X
from controller.control_static import CYAN, EYE, ICON, YELLOW, FONT3, IMAGE

from controller.gui.windows.frames.abstract.rectangle_highlighted import HighlightedRectangle
from controller.gui.visuals_object.visual_mouth import VisualMouth
from controller.gui.visuals_object.visual_eye import VisualEye
from controller.files.file_manager import FileManager
from controller.control_config import config


class DirectoryTreeWidget(tk.Frame):
    def __init__(self, parent, directory, type, *args, **kwargs):
        tk.Frame.__init__(self, parent, bg=config[CYAN], *args, **kwargs)
        style = ttk.Style(self)
        style.configure("Treeview", background=config[CYAN],
                        fieldbackground=config[CYAN], foreground=config[YELLOW], font=config[FONT3])
        self.type = type
        self.tv = ttk.Treeview(self, show='tree')
        #ybar = tk.Scrollbar(self, orient=tk.VERTICAL,
        #                    command_root=self.tv.yview)
        #self.tv.configure(yscroll=ybar.set)
        #self.tv.heading('#0', text='Dir：' + directory, anchor='w')
        self.tv.bind("<Button-1>", self.view_dir)
        path = os.path.abspath(directory)
        node = self.tv.insert('', 'end', text=path, open=True)
        self.traverse_dir(node, path)
        #ybar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tv.pack(fill=X, side=TOP)
        if self.type == IMAGE:
            self.gallery = tk.Canvas(self, height=800, bg=config[CYAN]) #GalleryWidget(self, 10, height=800)
            self.gallery.pack(fill=X, side=TOP)
            self.canvas_images = []
        else:
            self.files_var = tk.StringVar()
            self.files = tk.Listbox(self, listvariable=self.files_var, height=800, bg=config[CYAN])
            self.files.bind('<Double-Button-1>', self.send_value)
            self.files.pack(fill=X, side=TOP)
        self.pack(fill=X, side=TOP)

    def traverse_dir(self, parent,path):
        for d in os.listdir(path):
            full_path=os.path.join(path,d)
            isdir = os.path.isdir(full_path)
            if isdir:
                id = self.tv.insert(parent, 'end', text=d, open=False)
                self.traverse_dir(id,full_path)

    def set_image(self, parent, x, y, folder, image, zoom):
        canvas_image = CanvasImage(parent, folder, zoom, image)
        parent.create_window(x, y, anchor=NW, window=canvas_image.canvas)
        canvas_image.canvas.bind("<Button-1>", self.click_canvas_image)
        return canvas_image

    def click_canvas_image(self, e):
        canvas_image = self.find_canvas_image(e.widget)
        logging.info("getting image : {}".format(canvas_image.name))
        HighlightedRectangle.rectangle.set_image(canvas_image.tk_image, canvas_image.name, canvas_image.folder)

    def find_canvas_image(self, canvas_image):
        for c in self.canvas_images:
            if c.canvas == canvas_image:
                return c
        logging.error("no matching rectangle")

    def view_dir(self, event):
        #item = self.tv.selection()
        item = self.tv.identify('item',event.x,event.y)
        parent_iid = self.tv.parent(item)
        #self.tv.ancestor()
        node = []
        # go backward until reaching root
        while parent_iid != '':
            node.insert(0, self.tv.item(parent_iid)['text'])
            parent_iid = self.tv.parent(parent_iid)
        i = self.tv.item(item, "text")
        path = os.path.join(*node, i)
        self.show_folder(path)

    def send_value(self, e):
        w = e.widget
        if len(w.curselection()) > 0:
            index = int(w.curselection()[0])
            value = w.get(index)
            StaticValue.value = value
        else:
            logging.error("no line selected")

    def show_folder(self, path):
        if self.type == IMAGE:
            self.show_images(path)
        else:
            self.show_files(path)

    def show_images(self, path):

        for child in self.gallery.winfo_children():
            child.destroy()

        visual_type = None
        if EYE in path or ICON in path:
            visual_type = VisualEye()
        if MOUTH in path:
            visual_type = VisualMouth()

        #folder = ControlFactory().base_path+'/'+VISUALS+'/'+path
        items = FileManager.list_folder_files(path)

        xpos = 10
        ypos = 10
        ymargin = 10
        self.images = []
        for item in items:
            self.canvas_images.append(self.set_image(self.gallery, xpos, ypos, path, item, 8))
            ypos += ymargin + visual_type.HEIGHT * 8

    def show_files(self, path):
        items = FileManager.list_folder_files(path)
        self.files_var.set(items)


class CanvasImage:
    def __init__(self, parent, folder, zoom, name):
        self.name = name
        self.folder = folder
        pil_image = PIL.Image.open(self.folder + '/' + name)
        tk_image = ImageTk.PhotoImage(pil_image)
        self.tk_image = tk_image._PhotoImage__photo.zoom(zoom)
        #tk_image = tk_image.resize((image.width*zoom, image.height*zoom),Image.ANTIALIAS)
        self.canvas = tk.Canvas(parent, width=self.tk_image.width(), height=self.tk_image.height())
        self.canvas.create_image(0, 0, anchor=NW, image=self.tk_image)