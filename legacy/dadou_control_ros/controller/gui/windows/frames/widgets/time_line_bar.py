from dadou_utils_ros.audios.time_singleton import TimeSingleton


class TimeLineBar:
    def __init__(self, canvas):
        self.canvas = canvas
        self.last_pos = 15

        self.time_line = self.canvas.create_line(self.last_pos, 0, self.last_pos, 100, width=5)
        self.canvas.tag_bind(self.time_line, '<Enter>', self.object_enter_event)
        self.canvas.tag_bind(self.time_line, '<B1-Motion>', self.user_move)
        self.canvas.tag_bind(self.time_line, '<Leave>', self.release_line)

        self.follow_audio()


    def release_line(self, event):
        self.canvas.itemconfigure(self.time_line, width=5)

    #def change_object(self, e):
    #    e.widget.configure(bg='red')

    def user_move(self, event):
        self.move(event.x)

    def follow_audio(self):
        self.canvas.after(200, self.follow_audio)
        progress = TimeSingleton.get_percentage_pos()
        if progress != 0:
            pos = int(progress * self.canvas.winfo_width())
            self.move(pos)

    def move(self, pos_x):
        self.canvas.move(self.time_line, pos_x - self.last_pos, 0)  # <--- Use Canvas.move method.
        self.last_pos = pos_x
        #logging.info("Coordinates of the object are:", str(self.canvas.coords(self.time_line)))

    def object_enter_event(self, event):
        self.canvas.itemconfigure(self.time_line, width=10)




