import face_recognition
image = face_recognition.load_image_file("obama.jpeg")
face_locations = face_recognition.face_locations(image)
face_landmarks_list = face_recognition.face_landmarks(image)