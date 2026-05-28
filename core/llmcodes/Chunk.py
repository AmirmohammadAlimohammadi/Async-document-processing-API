import os
import chromadb
from chromadb.utils.embedding_functions import GoogleGeminiEmbeddingFunction
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter 

class PDFProcessor:
    def __init__(self, chromadb_client: chromadb.Client, chat_id: int, file_path: str, chunk_size: int = 200, chunk_overlap: int = 50):
        self.chromadb_client = chromadb_client
        self.chat_id = chat_id
        self.file_path = file_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is missing!")
            
        # FIX: Re-add api_key properly. If your library version throws an error on task_type or dimension, 
        # providing just api_key and model_name is the safest alternative pattern.
        try:
            self.embedding_function = GoogleGeminiEmbeddingFunction(
            model_name="gemini-embedding-2"
            )
        except Exception as e:
            print(f"error while loading embedding function. : {e}")
            raise

    def load_and_split(self):
        try:
            loader = PyPDFLoader(self.file_path)
        except Exception as e:
            print(f"error while initiating pypdfloader. : {e}")
            raise
        try:
            documents = loader.load()
        except Exception as e:
            print(f"error while loading loading. : {e}")
            raise
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", ". ", " "]
        )
        except Exception as e:
            print(f"error while loading text splitter. : {e}")
            raise
        try:
            chunks = text_splitter.split_documents(documents)
        except Exception as e:
            print(f"error while chunking the pdf. : {e}")
            raise
        return chunks

    def add_to_vector_store(self, chunks: list):
        # FIX 1: Prepended 'chat_' to guarantee valid non-numeric naming strings
        # FIX 2: Changed parameter key name to 'embedding_function' (singular)
        try:
            collection = self.chromadb_client.get_or_create_collection(
                name=f"chat_{self.chat_id}",
                embedding_function=self.embedding_function
            )
        except Exception as e:
            print(f"error while loading collection. : {e}")
        
        current_count = collection.count()
        documents_to_add = []
        ids_to_add = []
        metadatas_to_add = []
        embeddings_to_add = []
        
        for index, chunk in enumerate(chunks):
            
            chunk_id = current_count + index + 1
            documents_to_add.append(chunk.page_content)
            ids_to_add.append(str(chunk_id))
            embeddings_to_add.append(self.embedding_function([chunk.page_content])[0])
            metadata = dict(chunk.metadata)
            metadata["chat_id"] = self.chat_id
            metadatas_to_add.append(metadata)
            
        if documents_to_add:
            try:
                collection.add(
                    documents=documents_to_add,
                    ids=ids_to_add,
                    metadatas=metadatas_to_add,
                    embeddings = embeddings_to_add
                )
            except Exception as e:
                print(f"error while adding to the collection. : {e}")
                print(len(documents_to_add), len(ids_to_add), len(metadatas_to_add))
                

    def process(self):
        chunks = self.load_and_split()
        self.add_to_vector_store(chunks)
        return "PDF processing complete. Chunks added to vector store."