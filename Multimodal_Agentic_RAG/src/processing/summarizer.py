import os
import json
import csv
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
import torch

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

# ============================================================
# 1️⃣ LOAD ENV
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY in .env")

# ============================================================
# 2️⃣ PATHS
# ============================================================
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed"
CHUNKS_FILE = PROCESSED_PATH / "chunks.json"
SUMMARIES_FILE = PROCESSED_PATH / "summaries.json"

if not CHUNKS_FILE.exists():
    raise FileNotFoundError(f"chunks.json not found at {CHUNKS_FILE}")

# ============================================================
# 3️⃣ INIT MODELS
# ============================================================

# Text + tables
text_llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.1-8b-instant",
    temperature=0.2,
    max_tokens=250,
)

# Images
VISION_MODEL_ID = "Qwen/Qwen2-VL-7B-Instruct"
vision_processor = AutoProcessor.from_pretrained(VISION_MODEL_ID)
vision_model = Qwen2VLForConditionalGeneration.from_pretrained(
    VISION_MODEL_ID,
    torch_dtype=torch.float16,
    device_map="auto"  # uses GPU if available, else CPU
)

# ============================================================
# 4️⃣ HELPERS
# ============================================================

def read_table_csv(csv_path: str) -> str:
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(" | ".join(cell.strip() if cell else "" for cell in row))
    return "\n".join(rows)


def summarize_text_and_tables(text: str, table_files: list[str]) -> str:
    context = f"Text:\n{text}\n"
    for t in table_files:
        context += f"\nTable:\n{read_table_csv(t)}\n"
    prompt = f"""
Summarize this financial document chunk for investors.
- Be concise
- Preserve numbers, dates, trends
- Do not hallucinate
{context}
"""
    return text_llm.invoke([HumanMessage(content=prompt)]).content.strip()


def summarize_image(image_path: str) -> str:
    image = Image.open(image_path).convert("RGB")
    prompt = "Summarize this financial document image. Preserve numbers, charts, trends. No hallucination."
    inputs = vision_processor(images=image, text=prompt, return_tensors="pt").to(vision_model.device)
    with torch.no_grad():
        outputs = vision_model.generate(**inputs, max_new_tokens=200, temperature=0.2)
    return vision_processor.decode(outputs[0], skip_special_tokens=True)


# ============================================================
# 5️⃣ LOAD CHUNKS
# ============================================================
with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"✅ Loaded {len(chunks)} chunks")

# ============================================================
# 6️⃣ SUMMARIZE
# ============================================================
summaries = []

for idx, chunk in enumerate(chunks, start=1):
    print(f"Summarizing {idx}/{len(chunks)} | {chunk['source']} | page {chunk['page_number']}")
    table_files = [str(Path(p)) for p in chunk.get("tables", []) if Path(p).exists()]

    try:
        text_summary = summarize_text_and_tables(chunk.get("text", ""), table_files)
    except Exception as e:
        text_summary = f"Text summary failed: {e}"

    image_summaries = []
    for img in chunk.get("images", []):
        img_path = Path(img)
        if img_path.exists():
            try:
                image_summaries.append(summarize_image(img_path))
            except Exception as e:
                image_summaries.append(f"Image summary failed: {e}")

    final_summary = text_summary
    if image_summaries:
        final_summary += "\n\nImage Insights:\n" + "\n".join(image_summaries)

    summaries.append({
        "chunk_id": f"{chunk['source']}_{idx}",
        "source": chunk['source'],
        "page_number": chunk['page_number'],
        "summary": final_summary
    })

# ============================================================
# 7️⃣ SAVE SUMMARIES
# ============================================================
with open(SUMMARIES_FILE, "w", encoding="utf-8") as f:
    json.dump(summaries, f, indent=2, ensure_ascii=False)

print(f"✅ Saved summaries to {SUMMARIES_FILE}")
