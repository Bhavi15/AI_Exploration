# retrieval_agent.py
from pathlib import Path
from langchain_chroma import Chroma

# retrieval_agent.py

# ---------------------------
# Paths
# ---------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
VECTORSTORE_PATH = PROJECT_ROOT / "vectorstore"

# ---------------------------
# Load vectorstore
# ---------------------------
vectorstore = Chroma(persist_directory=str(VECTORSTORE_PATH))
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})  # top 5 chunks

# ---------------------------
# Retrieval Agent
# ---------------------------
def retrieval_agent(query: str):
    """
    Retrieve top-k relevant chunks from the vectorstore for a given query.
    """
    docs = retriever(query)  # <- call the retriever like a function
    return docs

# ---------------------------
# Test
# ---------------------------
if __name__ == "__main__":
    query = "Bank net profit 2025"
    docs = retrieval_agent(query)
    print(f"Retrieved {len(docs)} documents")
    for d in docs:
        print(d.metadata, "\n", d.page_content[:200], "...\n")
