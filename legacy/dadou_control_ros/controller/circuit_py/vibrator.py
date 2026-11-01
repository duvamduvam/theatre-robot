import time

import pwmio


class Vibrator:

    mode = None
    current_step = 0
    step_nb = 100
    vibrating = False
    ascending = True
    last_vibration = 0
    vibration_time_step = 0.03

    def __init__(self, pin):
        self.vibrator = pwmio.PWMOut(pin, frequency=50)

    def click(self):
        self.mode = "click"
        self.vibrating = True
        self.ascending = True

    def process(self):
        if self.vibrating and time.monotonic() > (self.last_vibration + self.vibration_time_step):
            if self.ascending:
                if self.current_step >= self.step_nb:
                    self.ascending = False
                else:
                    self.current_step += 1
            else:
                if self.current_step == 0:
                    self.vibrating = False
                    return
                self.current_step -= 1

            duty_cycle = int(self.current_step * 65535 / self.step_nb)
            #print("vibration step {} duty cycle {}".format(self.current_step, duty_cycle))
            self.vibrator.duty_cycle = duty_cycle
            self.last_vibration = time.monotonic()
