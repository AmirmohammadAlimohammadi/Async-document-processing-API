import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File , status , HTTPException ,Depends 
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from celery import chain
from core.worker import celery_app, process_pdf_task  , send_message_task
from core.database import init_db ,Session , get_session
from core.schemas import Chat, Message
from core.vector_store import get_chroma_client
from typing import Optional

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    
app = FastAPI(title="Rag Chatbot",lifespan=lifespan)
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
        raise HTTPException(status_code=400, 
                            detail="Chat ID is required.")
    chat = session.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, 
        detail="Chat not found.")
    
    if not message:
        raise HTTPException(status_code=400, 
                            detail="Message is required.")
    
    file_path = None
    if file:
        if file.content_type.split("/")[-1] != "pdf":
            raise HTTPException(status_code=400, 
                                detail="Only PDF files are allowed.")
        
        os.makedirs(os.path.join(UPLOAD_DIR, str(chat_id)), exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, str(chat_id), file.filename)
        content = await file.read()

        if os.path.exists(file_path):
            raise HTTPException(status_code=400, 
                                detail="File already exists.")
        with open(file_path, "wb") as f:
            try:
                f.write(content)
            except Exception as e:
                raise HTTPException(status_code=500, 
                                    detail=f"Error occurred while saving file: {str(e)}")
    chat_history = []
    chat = session.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()
    for msg in chat:
        chat_history.append({"sender": msg.sender, "content": msg.content})
    if file_path:
        workflow = chain(
            process_pdf_task.si(file_path, chat_id),
            send_message_task.si(message, chat_id , chat_history)
        )
        task_execution = workflow.delay()  
        content = {
        "message" : "File was uploaded and being processed. As soon as file processing is done sending message process will be started.",
        "chat_id" : chat_id,
        "query" : message,
        "filename": file.filename,
        "task_id": task_execution.id
        }
    
    else:
        task_execution = send_message_task.delay(message, chat_id , chat_history)
        content = {
        "message": "Sending message process has been started.",
        "chat_id" : chat_id,
        "query": message,
        "task_id": task_execution.id
    }
    response = JSONResponse(content=content, 
                            status_code=status.HTTP_202_ACCEPTED)
    return response

@app.get("/result/{task_id}")
def get_result(task_id: str, session: Session = Depends(get_session)):
    result = AsyncResult(task_id, app=celery_app)
    
    if result.state == "PENDING":
        return {"status": "Processing"}
    
    elif result.state == "SUCCESS":
        data = result.result
        chat_id = data.get("chat_id")

        query = Message(chat_id=chat_id , 
                        sender="user" , 
                        content=data.get("query"))
        
        answer = Message(chat_id=chat_id , 
                         sender="LLM" , 
                         content=data.get("answer"))
        session.add(query)
        session.add(answer)
        session.commit()
        session.refresh(query)
        session.refresh(answer)
        return JSONResponse(content=result.result, 
                            status_code=status.HTTP_200_OK)

    elif result.state == "FAILURE":
        return {"status": "Failed", 
                "error": str(result.info)}
    
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
