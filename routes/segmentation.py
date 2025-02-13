from ultralytics import YOLO
from PIL import Image

seg_model = YOLO(r'D:\venv\chess-vision\models\SegModel (1).pt')

async def segment_chess_board(image : Image):
    if image is None:
        return {"error" : "No image found" }    
    
    results = seg_model.predict(image)

    if not results or len(results) == 0:
        return {"error" : "No chessboard detected"}

    if len(results) > 1:
        return {"error" : "Multiple  chess boards found in the image"}
    
    xywh = results[0].boxes.xyxy[0].tolist()
    x_min, y_min, x_max, y_max = map(int, xywh)
    
    segmented_image = image.crop((x_min, y_min, x_max, y_max)) 

    return segmented_image