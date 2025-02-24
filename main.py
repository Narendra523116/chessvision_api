import io
import os
import tempfile
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image, UnidentifiedImageError
import uvicorn
from routes.segmentation import segment_chess_board
from routes.detection import detect_pieces
from routes.fen_generator import gen_fen
from routes.chess_review import analyze_pgn
from typing import List, Dict, Any, Union
from pydantic import BaseModel
import asyncio
import sys
import tracemalloc
from fastapi import requests
import base64

tracemalloc.start()


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


app = FastAPI()

class DetectionResults(BaseModel):
    boxes: list
    confidences: list
    classes: list

class FileUpload(BaseModel):
    file_data : str


@app.get("/test")
async def read_root():
    return {
        "name": "Narendra",
        "age": 20,
        "Gender": "Male"
    }
    

@app.post("/getFen")
async def get_fen(file : UploadFile = File(), perspective : str = Form("w"), next_to_move : str = Form("w")):

    if perspective not in ["w" , "b"]:
        return JSONResponse(content={"error" : "Perspective should be w (white) or b (black)"}, status_code=500)
    
    if next_to_move not in ["w" , "b"]:
        return JSONResponse(content={"error" : "next to move should be w (white) or b (black)"}, status_code=500)
    

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
        
        fen = gen_fen(detection_results, perspective, next_to_move)
        if not fen:
            return JSONResponse(content={"error": "FEN generation failed", "details": "Invalid input data"}, status_code=500)

        return JSONResponse(content={"FEN": fen}, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={"error": "Unexpected error occurred", "details": str(e)}, status_code=500)
    
@app.post('/getReview')
async def getReview(file_upload: FileUpload):  
    print(os.getcwd())
    print("call recieved")

    if not file_upload.file_data:
        return JSONResponse(content={"error": "Empty file uploaded"}, status_code=400)
    try:
        file_data = base64.b64decode(file_upload.file_data)
        # Save the uploaded file to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pgn") as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name

        # Analyze the PGN file
        analysis_result = analyze_pgn(tmp_file_path)

        # Clean up the temporary file
        os.remove(tmp_file_path)

        if not analysis_result:
            return JSONResponse(content={"error": "No game found in the PGN file"}, status_code=400)
        return analysis_result
    
    except Exception as e:
        return  JSONResponse(content={"error": "Unexpected error occurred", "details": str(e)}, status_code=500)
    

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)