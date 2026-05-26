import os
from fastapi import FastAPI, UploadFile, File
from celery.result import AsyncResult
from core.worker import celery_app, process_pdf_task 

app = FastAPI(title="Async Document Processing API")
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile = File(...)):
    if not file:
        return {"message": "No file sent"}
    
    content = await file.read()
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)
        
    task = process_pdf_task.delay(file_path)
    
    return {
        "result": "Processing started in background.",
        "filename": file.filename,
        "task_id": task.id
    }

@app.get("/result/{task_id}")
def get_result(task_id: str):
    # Passing app=celery_app links the request directly to the backend settings configured in worker.py
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state == "PENDING":
        return {"status": "Processing"}
    elif result.state == "SUCCESS":
        return {"status": "Completed", "result": result.result}
    elif result.state == "FAILURE":
        return {"status": "Failed", "error": str(result.info)}
    else:
        return {"status": result.state}