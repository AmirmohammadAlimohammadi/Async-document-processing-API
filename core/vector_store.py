import os
import chromadb

def get_chroma_client():
    """
    Dynamically generates a fresh HttpClient connection. 
    Safe against process forking and cross-container lockups.
    """
    chroma_host = os.getenv("CHROMA_HOST", "chroma")
    chroma_port = os.getenv("CHROMA_PORT", "8000")
    
    return chromadb.HttpClient(
        host=chroma_host, 
        port=int(chroma_port)
    )