import cv2
import numpy as np
import pickle

rectW,rectH=107,48

cap = cv2.VideoCapture("carPark.mp4")

if not cap.isOpened():
    raise RuntimeError("No se pudo abrir carPark.mp4")

video_fps = cap.get(cv2.CAP_PROP_FPS)
frame_delay = max(1, round(1000 / video_fps)) if video_fps > 0 else 33

with open('carParkPos', 'rb') as f:
    posList = pickle.load(f)

def check(imgPro):
    spaceCount = 0
    for pos in posList:
        x,y = pos
        crop = imgPro[y: y+rectH, x: x+rectW]
        count = cv2.countNonZero(crop)
        if count < 900:
            spaceCount += 1
            color = (0, 255, 0)
            thick = 5
        else:
            color = (0, 0, 255)
            thick = 2

        cv2.rectangle(img, pos, (x + rectW, y + rectH), color, thick)
    cv2.rectangle(img, (45, 30), (250, 75), (180, 0, 180), -1)
    cv2.putText(img, f'Libres: {spaceCount}/{len(posList)}', (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

while True:
    ok, img = cap.read()
    if not ok or img is None:
        break

    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3,3), 1)
    trhe=cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 16)
    blur = cv2.medianBlur(trhe, 5)
    kernel = np.ones((3,3), np.uint8)
    dillate=cv2.dilate(blur, kernel, iterations=1)
    check(dillate)
    cv2.imshow("Image", img)
    if cv2.waitKey(frame_delay) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()