import os
import time
from celery import Celery
from core.llmcodes.Chunk import PDFProcessor
from core.vector_store import get_chroma_client
from core.database import Session
from core.prompt import prompt_template

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"


celery_app = Celery("tasks")


celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_track_started=True,
    result_extended=True
)

@celery_app.task(name="process_pdf_task")
def process_pdf_task(file_path: str , chat_id : int):
    print(f"Starting background processing for: {file_path}")
    chroma_client = get_chroma_client()
    try:
        pdf_processor = PDFProcessor(chromadb_client=chroma_client,
                                      chat_id=chat_id, 
                                      file_path=file_path)
    except Exception as e:
        print(f"Error occurred while initializing PDFProcessor for {file_path}: {e}")
        raise
    print(f"Loading and splitting PDF: {file_path}")
    try:
        result = pdf_processor.process()
    except Exception as e:
        print("error happened while processing pdf.",str(e))
        raise
    print(f"Finished processing for: {file_path}")
    return {"status": "completed", "processed_file": file_path, "result": result}

@celery_app.task(name="send_message_task")
def send_message_task(message: str, chat_id: int , chat_history: list = []):
    print(f"Processing message for chat ID {chat_id}: {message}")
    chroma_client = get_chroma_client()
    collection = None
    try:
        collection = chroma_client.get_collection(name=f"chat_{chat_id}")
    except Exception as e:
        print(f"no such collection as chat_{chat_id}")
    if collection:
        context = collection.query(query_texts=[message] , n_results=5)
        if context and context.get('documents') and context['documents'][0]:
            text_chunks = context['documents'][0]
            context_str = "\n\n---\n\n".join(text_chunks)
        else:
            context_str = "No relevant document context found."
    else:
        context_str = ""
    chat_history_str = "\n".join([f"{entry['sender']}: {entry['content']}" for entry in chat_history])
    final_prompt = prompt_template.format(
        context=context_str,
        chat_history=chat_history_str,
        user_query=message
    )
    
    return {"status": "completed", "prompt": final_prompt}