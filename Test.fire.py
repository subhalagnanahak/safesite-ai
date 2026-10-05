"""Check what the fire/smoke model sees in fire.mp4.

Put this file in the project folder (next to app.py) and run:  python test_fire.py
"""
import cv2
from ultralytics import YOLO

MODEL = 'static/models/fire_smoke.pt'
VIDEO = 'fire.mp4'
SAMPLES = 40  # how many frames to check, spread evenly across the video

model = YOLO(MODEL)
print('Classes:', model.names)

cap = cv2.VideoCapture(VIDEO)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
if total <= 0:
    raise SystemExit(f'Could not read {VIDEO}. Run this from the project folder.')
step = max(total // SAMPLES, 1)

for size in (640, 960):
    best = {name: (0.0, -1) for name in model.names.values()}
    hits = {name: 0 for name in model.names.values()}
    for idx in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        for result in model(frame, conf=0.05, imgsz=size, verbose=False):
            for box in result.boxes:
                name = model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                if conf > best[name][0]:
                    best[name] = (conf, idx)
                if conf >= 0.25:
                    hits[name] += 1
    print(f'\n--- image size {size} ---')
    for name, (conf, idx) in best.items():
        print(f'{name}: best confidence {conf:.2f} (frame {idx}), detections at 0.25 or higher: {hits[name]}')