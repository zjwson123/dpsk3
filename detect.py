from ultralytics import YOLO
import cv2
import os

def detect_defects(image_path):
    # Load the model
    model = YOLO("yolov8/best.pt")

    # Perform detection
    results = model(image_path)

    # Process results
    labels = []
    for result in results:
        for box in result.boxes:
            label = model.names[int(box.cls[0])]
            confidence = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()

            labels.append({
                'label': label,
                'confidence': confidence,
                'xmin': xyxy[0],
                'ymin': xyxy[1],
                'xmax': xyxy[2],
                'ymax': xyxy[3],
                'bbox': xyxy
            })

    # Save the annotated image
    annotated_img = results[0].plot()
    annotated_path = os.path.join('app/static/uploads', 'annotated_' + os.path.basename(image_path))
    cv2.imwrite(annotated_path, annotated_img)

    return {
        'labels': labels,
        'annotated_image': annotated_path
    }


