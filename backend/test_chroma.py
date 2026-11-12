from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

embeddings = OllamaEmbeddings(
    model="nomic-embed-text"
)

db = Chroma(
    collection_name="studysync",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

print("Connected Successfully")