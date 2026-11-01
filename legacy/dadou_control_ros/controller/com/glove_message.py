import logging

from dadou_utils_ros.utils_static import KEY, ANGLO


class GloveMessage:

    def decrypt(self, input):
        msg = {}
        if not input or len(input) == 0:
            logging.warning("decrypt glove message empty")
        else:
            msg[KEY] = input[0]
            if len(input) == 5:
                msg[ANGLO] = input[1:5]

        return msg
