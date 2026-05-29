import os
import time
import logging
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from core.llmcodes.Chunk import PDFProcessor
from core.vector_store import get_chroma_client
from core.database import Session
from core.prompt import prompt_template
from langchain_google_genai import ChatGoogleGenerativeAI
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

logger = logging.getLogger("celery_worker")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s - %(levelname)s - %(name)s]: %(message)s")
celery_app = Celery("tasks")


celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_track_started=True,
    result_extended=True,
    task_time_limit=300,
    task_soft_time_limit=270,
)

@celery_app.task(name="process_pdf_task",
                bind=True,
                autoretry_for=(Exception,), 
                retry_backoff=True,      
                max_retries=3)
def process_pdf_task(self , file_path: str , chat_id : int):
    logger.info(f"Starting PDF {file_path} processing task {self.request.id} for Chat: {chat_id}")
    
    try:
        chroma_client = get_chroma_client()
        pdf_processor = PDFProcessor(chromadb_client=chroma_client,
                                      chat_id=chat_id, 
                                      file_path=file_path)
        logger.info(f"Extracting, chunking, and embedding file: {file_path}")
        result = pdf_processor.process()
        logger.info(f"Successfully indexed document items into Vector Store for Chat: {chat_id}")
        return {"status": "completed", "file": file_path , "result": result}
    except SoftTimeLimitExceeded:
        logger.error(f"Task timed out softly for file {file_path}. Cleaning allocations.")
        raise
    except Exception as exc:
        logger.error(f"Fatal error during execution of process_pdf_task: {exc}", exc_info=True)
        raise self.retry(exc=exc)

@celery_app.task(name="send_message_task" , 
                bind=True,
                autoretry_for=(Exception,),
                retry_backoff=True,
                max_retries=3)
def send_message_task(self, message: str, chat_id: int , chat_history: list = []):
    logger.info(f"Executing RAG pipeline task {self.request.id} for Chat ID: {chat_id}")
    
    collection = None
    try:
        chroma_client = get_chroma_client()
        try:
            collection = chroma_client.get_collection(name=f"chat_{chat_id}")
        except Exception as vec_err:
            logger.warning(f"No semantic collection metadata loaded for chat_{chat_id}: {vec_err}")
            context_str = "No document context available."
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
        logger.info(f"Invoking LLM Core (gemini-2.5-flash) for Chat: {chat_id}")
        model = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            temperature=0, 
            top_p=0.95,  
            max_tokens=1000,
            timeout=None,
            max_retries=2,
            api_key=os.getenv("GEMINI_API_KEY"),
        )
        answer = model.invoke(final_prompt)
        logger.info(f"Task cycle {self.request.id} successfully finished.")
        response = {"query" : message,
                    "answer" : answer.text,
                    "context" : context_str, 
                    "chat_id" : chat_id}
    
        return response
    except Exception as exc:
        logger.error(f"Error handling pipeline context generation: {exc}", exc_info=True)
        raise self.retry(exc=exc)