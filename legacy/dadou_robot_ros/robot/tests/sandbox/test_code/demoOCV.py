

import cv2

#import socket


#tests avec ffmpeg
#https://trac.ffmpeg.org/wiki/Capture/Webcam

#stream avec ffmpeg
#https://trac.ffmpeg.org/wiki/Capture/Webcam

#### Activation du flux du drone
##sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)



#device = cv2.VideoCapture(0)
device = cv2.VideoCapture("udp://@:12345")
#Streaming : ffmpeg -f v4l2 -framerate 25 -video_size 640x480 -i /dev/video0 output.mkv
#https://www.baeldung.com/linux/ffmpeg-webcam-stream-video




while True :
    read_status, raw_image = device.read()
    cv2.imshow('test', raw_image)
    input_key = cv2.waitKey(1)
    if input_key == 27:  # 27 is the ESC key
        break
cv2.destroyAllWindows()


