from ultralytics import YOLO
from PIL import Image
import os 

curr = os.getcwd()
detect_model_path = os.path.join(curr, 'models', 'chessDetection3d.pt')
detect_model = YOLO(detect_model_path)

async def detect_pieces(image : Image):
    if image is None:
        print("No image is there")
        return {"error" : "No image detected"}
    
    results = detect_model.predict(image)

    if not results or len(results) == 0:
        print("No results are there")
        return {"error" : "No results found"}
    
    boxes = results[0].boxes.xyxy.tolist()  
    confidences = results[0].boxes.conf.tolist()  
    classes = results[0].boxes.cls.tolist()  

    class_names = []

    for idx in classes:
        class_names.append(detect_model.names[idx])

    return {
        "boxes": boxes,
        "confidences": confidences,
        "classes": class_names
    }
