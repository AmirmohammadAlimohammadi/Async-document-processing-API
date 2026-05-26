from fastapi import FastAPI
from typing import Annotated
from fastapi import FastAPI, File, UploadFile
import os
UPLOAD_DIR = "uploads/"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI with Docker and Redis"}

@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile):
    if not file:
        return {"message": "No file sent"}
    content = await file.read()
    content_type = file.content_type.split("/")[-1]
    if content_type != "pdf":
        return {"error" : f"Only pdf files are accepted not {content_type}" }
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        try:
            f.write(content)
        except FileExistsError:
            return {"error " : "file already exists"}
    return {
        "result": "ok",
        "filename": file.filename,
        "saved_path": file_path
    }