# embeddings.py

import json
from pathlib import Path
import torch
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

# ---------------------------
# Paths
# ---------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed"
VECTORSTORE_PATH = PROJECT_ROOT / "vectorstore"
SUMMARIES_FILE = PROCESSED_PATH / "summaries.json"

# ---------------------------
# Load summaries
# ---------------------------
if not SUMMARIES_FILE.exists():
    raise FileNotFoundError(f"{SUMMARIES_FILE} not found at {SUMMARIES_FILE}")

with open(SUMMARIES_FILE, "r", encoding="utf-8") as f:
    summaries = json.load(f)

# ---------------------------
# Initialize SentenceTransformer via HuggingFaceEmbeddings
# ---------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": device}
)

# ---------------------------
# Create LangChain Documents
# ---------------------------
documents = [
    Document(
        page_content=chunk["summary"],
        metadata={"source": chunk["source"], "page_number": chunk["page_number"]}
    )
    for chunk in summaries
]

# ---------------------------
# Create Chroma vectorstore
# ---------------------------
vectorstore = Chroma.from_documents(
    documents=documents,
    embedding=embedding_model,
    persist_directory=str(VECTORSTORE_PATH)  # automatically persists
)

print(f"✅ Vectorstore created with {len(documents)} chunks at {VECTORSTORE_PATH}")