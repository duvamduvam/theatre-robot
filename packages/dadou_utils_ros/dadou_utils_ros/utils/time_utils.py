import logging

import time


class TimeUtils:

    @staticmethod
    def formatted_time(time_stamp):
        mlsec = repr(time_stamp).split('.')[1][:2]
        return time.strftime("%M:%S:{}".format(mlsec), time.localtime(time_stamp))

    @staticmethod
    def current_milli_time():
        #return round(time.time() * 1000)
        return round(time.time() * 1000)

    @staticmethod
    def get_milli_time(sec):
        return sec * 1000

    @staticmethod
    def is_time(last_time, time_out) -> bool:
        #logging.debug(" last_time is int : " + str(isinstance(last_time, int)) + " -> " + str(
        #    last_time) + " timeout is int : " + str(
        #    isinstance(time_out, int)) + " -> " + str(
        #    time_out))
        current = TimeUtils.current_milli_time()
        is_time = False
        try:
            is_time = ((current - last_time) - time_out) > 0
        except TypeError:
            logging.error("is_time = (" + str(current) + " - " + str(last_time) + ") - " + str(time_out) + ") > 0)")
            # logging.debug("last time: " + str(last_time) + " current time : " + str(current) +
            #              " time step : " + str(time_out) + " is time : " + str(is_time))
        return is_time
