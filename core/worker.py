import os
import time
from celery import Celery


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
def process_pdf_task(file_path: str):
    print(f"Starting background processing for: {file_path}")
    time.sleep(15)
    print(f"Finished processing for: {file_path}")
    return {"status": "completed", "processed_file": file_path, "result": "Dummy AI summary text"}