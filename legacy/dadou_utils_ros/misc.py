import fcntl
import io
import logging
import os
import platform
import random
import re
import socket
import subprocess
from os.path import exists


import filetype
from urllib import request

class Misc:

    @staticmethod
    def is_input_ok(msg):
        regexp = re.compile('[^0-9a-zA-Z <>.]+')
        if regexp.search(msg):
            logging.error("wrong input ".format(msg))
            return False
        else:
            return True

    @staticmethod
    def exec_shell(command):
        logging.info("exec shell command {}".format(command))
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #logging.info(stream.read())

    @staticmethod
    def exec_shell2(command):
        logging.info("exec shell command {}".format(command))
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            return result
        except Exception as e:
            return False

    @staticmethod
    def non_block_read(output):
        fd = output.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        try:
            return output.read()
        except:
            return ""

    @staticmethod
    def to_bool(value):
        """
           Converts 'something' to boolean. Raises exception for invalid formats
               Possible True  values: 1, True, "1", "TRue", "yes", "y", "t"
               Possible False values: 0, False, None, [], {}, "", "0", "faLse", "no", "n", "f", 0.0, ...
        """
        if str(value).lower() in ("yes", "y", "true",  "t", "1"): return True
        if str(value).lower() in ("no",  "n", "false", "f", "0", "0.0", "", "none", "[]", "{}"): return False
        raise Exception('Invalid value for boolean conversion: ' + str(value))

    @staticmethod
    def convert_to_array(value: str):
        to_return = value.replace("\'", "")
        to_return = to_return.replace(",", "")
        to_return = to_return.replace("(", "")
        to_return = to_return.replace(")", "")
        return to_return.split()

    @staticmethod
    def is_audio(file: str):
        if not exists(file):
            return
        kind = filetype.guess(file)
        if kind is None:
            print('Cannot guess file type!')
            return False
        else:
            return 'audio' in kind.mime

    @staticmethod
    def has_attr(msg, attr):
        return msg and hasattr(msg, attr) and msg[attr]

    @staticmethod
    def cast_int(str_input):
        if isinstance(str_input, int):
            return str_input
        try:
            return int(str_input)
        except (TypeError, ValueError) as e:
            logging.error("can't cast {} to int".format(str))

    @staticmethod
    def cast_float(str_input):
        if isinstance(str_input, float):
            return str_input
        try:
            return float(str_input)
        except (TypeError, ValueError) as e:
            logging.error("can't cast {} to float".format(str))

    @staticmethod
    def internet_connected():
        try:
            # connect to the host -- tells us if the host is actually
            # reachable
            sock = socket.create_connection(("www.google.com", 80))
            if sock is not None:
                sock.close
            return True
        except OSError:
            pass
        return False

    @staticmethod
    def wifi_connected():
        try:
            request.urlopen('http://192.168.1.1', timeout=1)
            return True
        except (request.URLError, TimeoutError) as err:
            return False

    @staticmethod
    def get_system_type():
        os_name = os.name
        platform_name = platform.system()
        logging.info("os.name {} plateform {}".format(os_name, platform_name))
        return "truc"

        #logging.info("os.name {} plateform {}".format(name, platform))
        #return uname.machine

    @staticmethod
    def is_raspberrypi():
        try:
            # Tente de lire le fichier qui contient le modèle de l'appareil
            with open('/proc/device-tree/model', 'r') as file:
                model_info = file.read()
            # Recherche la chaîne de caractères "Raspberry Pi" dans le contenu
            return 'Raspberry Pi' in model_info
        except FileNotFoundError:
            # Le fichier n'existe pas, donc probablement pas un Raspberry Pi
            return False

    @staticmethod
    def is_docker():
        try:
            with open('/proc/1/cgroup', 'rt') as f:
                return 'docker-arm64' in f.read() or 'kubepods' in f.read()
        except Exception:
            return False
    @staticmethod
    def mapping(v, in_min: int, in_max: int, out_min: int, out_max: int):
        # Check that the value is at least in_min
        if v < in_min:
            v = in_min
        # Check that the value is at most in_max
        if v > in_max:
            v = in_max
        return (v - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

    @staticmethod
    def percentage(value, min_value, max_value):
        return ((value - min_value)/(max_value-min_value))*100

    @staticmethod
    def random_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))
    @staticmethod
    def get_raspberry_pi_model():
        result = subprocess.run(['cat', '/proc/cpuinfo'], stdout=subprocess.PIPE)
        cpuinfo = result.stdout.decode('utf-8')

        for line in cpuinfo.splitlines():
            if line.startswith("Model"):
                return line.strip()

        return "Modèle non trouvé"