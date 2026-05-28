import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File , status , HTTPException ,Depends ,Response 
from celery.result import AsyncResult
from celery import chain
from core.worker import celery_app, process_pdf_task  , send_message_task
from core.database import init_db ,Session , get_session
from core.schemas import Chat
from core.vector_store import get_chroma_client
from typing import Optional

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    
app = FastAPI(title="Async Document Processing API",lifespan=lifespan)
UPLOAD_DIR = r"/app/uploads" 
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/send_message/")
async def create_upload_file( message: str, chat_id: Optional[int] = None ,session: Session = Depends(get_session), file: Optional[UploadFile] = File(None)):
    if message and not chat_id:
        new_chat = Chat()
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)
        chat_id = new_chat.id
    if not chat_id:
        raise HTTPException(status_code=400, detail="Chat ID is required.")
    chat = session.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")
    
    file_path = None
    if file:
        if file.content_type.split("/")[-1] != "pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
        os.makedirs(os.path.join(UPLOAD_DIR, str(chat_id)), exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, str(chat_id), file.filename)
        content = await file.read()

        if os.path.exists(file_path):
            raise HTTPException(status_code=400, detail="File already exists.")
        with open(file_path, "wb") as f:
            try:
                f.write(content)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error occurred while saving file: {str(e)}")
    if file_path:
        workflow = chain(
            process_pdf_task.si(file_path, chat_id),
            send_message_task.si(message, chat_id )
        )
        task_execution = workflow.delay()  
        return{
        "result": "Processing started in background.",
        "filename": file.filename,
        "task_id": task_execution.id
    }

    else:
        task_execution = send_message_task.delay(message, chat_id)
        return {
        "result": "Message processing started in background.",
        "task_id": task_execution.id
    }


    

@app.get("/result/{task_id}")
def get_result(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state == "PENDING":
        return {"status": "Processing"}
    elif result.state == "SUCCESS":
        return {"status": "Completed", "result": result.result}
    elif result.state == "FAILURE":
        return {"status": "Failed", "error": str(result.info)}
    else:
        return {"status": result.state}
    
@app.get("/collections/")
def get_collection():
    chroma_client = get_chroma_client()
    try:
        collections = chroma_client.list_collections()
        result = {}
        for i , collection in enumerate(collections):
            result[f"Collection {i+1}"] = collection.name
        return result
    except Exception as e:
        return {"error": f"Error retrieving collection: {str(e)}"}
