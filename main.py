import io
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
from routes.segmentation import segment_chess_board
from routes.detection import detect_pieces
from routes.fen_generator import gen_fen
from typing import List, Dict, Any, Union
from pydantic import BaseModel

app = FastAPI()

class DetectionResults(BaseModel):
    boxes: list
    confidences: list
    classes: list

@app.get("/")
async def read_root():
    return {
        "name": "Narendra",
        "age": 20,
        "Gender": "Male"
    }

@app.post("/getSeg")
async def get_seg(file: UploadFile = File(...)):
    print(f'Image received: {file.filename}')

    try:
        image_content = await file.read()
        if not image_content:
            return JSONResponse(content={"error": "Empty file uploaded"}, status_code=400)

        try:
            image = Image.open(io.BytesIO(image_content))
        except UnidentifiedImageError:
            return JSONResponse(content={"error": "Invalid image format"}, status_code=400)

        # If segment_chess_board is async, use `await`, otherwise remove `await`
        segmented_image = await segment_chess_board(image)

        if isinstance(segmented_image, dict):
            return JSONResponse(content=segmented_image, status_code=400)

        # Save to in-memory bytes
        img_bytes = io.BytesIO()
        segmented_image.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        print("Image successfully processed and returned")
        return StreamingResponse(
            img_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "inline; filename=output.png"}
        )


    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

@app.post("/getCoords")
async def get_coords(file: UploadFile = File(...)):
    try:
        image_content = await file.read()

        if not image_content:
            print("No image found")
            return JSONResponse(content={"error": "Empty file uploaded"}, status_code=400)

        try:
            image = Image.open(io.BytesIO(image_content))
        except UnidentifiedImageError:
            return JSONResponse(content={"error": "Invalid image format"}, status_code=400)

        detection_results = await detect_pieces(image)

        if "error" in detection_results:
            return JSONResponse(content=detection_results, status_code=400)

        print("Image successfully processed and returned")
        return JSONResponse(content={"detections": detection_results}, status_code=200)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return JSONResponse(content={"error": "Unexpected error occurred", "details": str(e)}, status_code=500)
    

@app.post("/getFen")
async def get_fen(file : UploadFile = File(), perspective : str = "w" | "b"):

    if perspective not in ["w" , "b"]:
        return JSONResponse(content={"error" : "Perspective should be w (white) or b (black)"}, status_code=500)
    
    try:
        image_content = await file.read()
        if not image_content:
            return JSONResponse(content={"error": "Empty file uploaded"}, status_code=400)

        try:
            image = Image.open(io.BytesIO(image_content))
        except UnidentifiedImageError:
            return JSONResponse(content={"error": "Invalid image format"}, status_code=400)

        segmented_image = await segment_chess_board(image)
        if isinstance(segmented_image, dict):
            return JSONResponse(content=segmented_image, status_code=400)

        segmented_image = segmented_image.resize((224, 224))

        detection_results = await detect_pieces(segmented_image)
        if "error" in detection_results:
            return JSONResponse(content=detection_results, status_code=400)
        
        fen = gen_fen(detection_results, perspective)
        if not fen:
            return JSONResponse(content={"error": "FEN generation failed", "details": "Invalid input data"}, status_code=500)

        return JSONResponse(content={"FEN": fen}, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={"error": "Unexpected error occurred", "details": str(e)}, status_code=500)
