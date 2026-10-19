"""Local orientation suggestions using YuNet landmarks. No network."""
import threading
import sys
from pathlib import Path

LOCK = threading.Lock()


def suggest(image):
    import cv2
    import numpy as np
    with LOCK:
        cv2.setNumThreads(1)
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
        model = root / 'assets/models/face_detection_yunet_2023mar.onnx'
        sample = image.copy()
        sample.thumbnail((640, 640))
        pixels = cv2.cvtColor(np.asarray(sample.convert('RGB')), cv2.COLOR_RGB2BGR)
        detector = cv2.FaceDetectorYN.create('onnx', np.frombuffer(model.read_bytes(), dtype=np.uint8),
                                             np.empty(0, dtype=np.uint8), (320, 320), .85, .3, 1000)
        scores = []
        for quarter in range(4):
            upright = np.ascontiguousarray(np.rot90(pixels, -quarter))
            detector.setInputSize((upright.shape[1], upright.shape[0]))
            _, faces = detector.detect(upright)
            score = 0
            for face in [] if faces is None else faces:
                x, y, w, h = face[:4]
                eye_a, eye_b = face[4:6], face[6:8]
                nose, mouth_a, mouth_b = face[8:10], face[10:12], face[12:14]
                eye_y, mouth_y = (eye_a[1]+eye_b[1])/2, (mouth_a[1]+mouth_b[1])/2
                if mouth_y-eye_y > h*.18 and abs(eye_a[1]-eye_b[1]) < w*.35 and nose[1] > eye_y:
                    score += float(face[-1]) * (1 + min(1, w*h / (upright.shape[0]*upright.shape[1]) * 5))
            scores.append(score)
        ranking = sorted(range(4), key=lambda i: scores[i], reverse=True)
        best, second = ranking[:2]
        accepted = bool(scores[best] >= .9 and scores[best] >= scores[second] * 1.5 + .15)
        return {'rotation': (best*90 + 270) % 360 if accepted else 270,
                'suggested': accepted,
                'reason': 'Sugestão por rostos · confira' if accepted else 'Conferir orientação'}
