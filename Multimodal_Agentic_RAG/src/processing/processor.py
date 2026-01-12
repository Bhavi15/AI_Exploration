import os
import re
import csv
import fitz  # PyMuPDF
import pdfplumber
import nltk
from nltk.tokenize import sent_tokenize

nltk.download("punkt")  # for sentence tokenization

# ---------------------------
# Project paths
# ---------------------------
pdf_folder = r"c:\Users\pbhav\projects\AI_Exploration\Multimodal_Agentic_RAG\data\raw"
project_root = os.getcwd()  # works in scripts & notebooks
output_path = os.path.join(project_root, "data", "processed")
images_path = os.path.join(output_path, "images")
tables_path = os.path.join(output_path, "tables")

os.makedirs(images_path, exist_ok=True)
os.makedirs(tables_path, exist_ok=True)


# Heading detection regex
# ---------------------------
HEADING_REGEX = re.compile(
    r"""
    ^(
        (item\s+\d+[a-z]?)|
        (risk\s+factors?)|
        (management['’]s\s+discussion)|
        (financial\s+statements?)|
        (notes?\s+to\s+the\s+financial\s+statements?)|
        ([A-Z][A-Z\s]{4,})
    )$
    """,
    re.IGNORECASE | re.VERBOSE
)

# ---------------------------
# Parameters
# ---------------------------
MAX_CHARS = 4000  # max characters per chunk
OVERLAP = 200     # overlap characters between chunks

# ---------------------------
# Helper functions
# ---------------------------

def extract_images(page, pdf_basename, page_num):
    """Extract images from a PyMuPDF page and save them."""
    images_on_page = []
    for img_index, img_info in enumerate(page.get_images(full=True)):
        xref = img_info[0]
        img_dict = page.parent.extract_image(xref)
        image_bytes = img_dict["image"]
        image_ext = img_dict.get("ext", "png")
        image_filename = os.path.join(
            images_path,
            f"{pdf_basename}_page{page_num}_img{img_index}.{image_ext}"
        )
        with open(image_filename, "wb") as f:
            f.write(image_bytes)
        images_on_page.append(image_filename)
    return images_on_page

def extract_tables(pdf_path, page_num, pdf_basename):
    """Extract tables using pdfplumber and return filenames + table text."""
    tables_on_page = []
    table_text_combined = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        tables = page.extract_tables()
        for t_index, table in enumerate(tables):
            table_file = os.path.join(
                tables_path,
                f"{pdf_basename}_page{page_num}_table{t_index+1}.csv"
            )
            with open(table_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in table:
                    row_clean = [c.strip() if c else "" for c in row]
                    writer.writerow(row_clean)
                    table_text_combined.append(" | ".join(row_clean))
            tables_on_page.append(table_file)
    return tables_on_page, table_text_combined

def merge_lines_to_paragraphs(text_lines):
    """Merge lines into proper paragraphs with heading awareness."""
    paragraphs = []
    current = []
    for line in text_lines:
        clean = line.strip()
        if not clean:
            if current:
                paragraph_text = " ".join(current)
                if len(paragraph_text) > 50:
                    paragraphs.append(paragraph_text)
                current = []
            continue

        if HEADING_REGEX.match(clean):
            if current:
                paragraph_text = " ".join(current)
                if len(paragraph_text) > 50:
                    paragraphs.append(paragraph_text)
                current = []
            paragraphs.append(clean)
        else:
            current.append(clean)

    if current:
        paragraph_text = " ".join(current)
        if len(paragraph_text) > 50:
            paragraphs.append(paragraph_text)

    # Merge small paragraphs (<500 chars) with next
    merged_paragraphs = []
    i = 0
    while i < len(paragraphs):
        text = paragraphs[i]
        while i + 1 < len(paragraphs) and len(text) < 500:
            text += " " + paragraphs[i+1]
            i += 1
        merged_paragraphs.append(text)
        i += 1

    return merged_paragraphs

def recursive_sentence_chunking(text, max_chars=MAX_CHARS, overlap=OVERLAP):
    """Split text into sentence-aware chunks recursively if too long."""
    if len(text) <= max_chars:
        return [text]

    sentences = sent_tokenize(text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current += " " + s if current else s
        else:
            chunks.append(current)
            current = s
    if current:
        chunks.append(current)

    # Apply overlap
    final_chunks = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            final_chunks.append(chunk)
        else:
            final_chunks.append(chunks[i-1][-overlap:] + " " + chunk)
    return final_chunks

# ---------------------------
# Main processing
# ---------------------------

texts = []

if not os.path.exists(pdf_folder):
    raise ValueError(f"No PDF folder found at {pdf_folder}")

pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
if not pdf_files:
    raise ValueError(f"No PDF files found in {pdf_folder}")

for pdf_file in pdf_files:
    pdf_path = os.path.join(pdf_folder, pdf_file)
    pdf_basename = os.path.splitext(pdf_file)[0]
    print(f"Processing: {pdf_file}")

    doc = fitz.open(pdf_path)
    for page_num, page in enumerate(doc, start=1):
        # 1. Extract text lines
        blocks = page.get_text("blocks")
        lines = [blk[4].strip() for blk in blocks if blk[4].strip()]

        # 2. Merge lines into paragraphs
        paragraphs = merge_lines_to_paragraphs(lines)

        # 3. Extract images
        images_on_page = extract_images(page, pdf_basename, page_num)

        # 4. Extract tables
        tables_on_page, table_text_list = extract_tables(pdf_path, page_num, pdf_basename)

        # 5. Combine paragraph + table text
        table_text_combined = "\n".join(table_text_list)

        for para in paragraphs:
            full_text = para
            if table_text_combined:
                full_text += "\n" + table_text_combined

            # 6. Recursive sentence chunking
            chunks = recursive_sentence_chunking(full_text)

            # 7. Store multimodal metadata
            for chunk in chunks:
                texts.append({
                    "text": chunk,
                    "page_number": page_num,
                    "source": pdf_file,
                    "images": images_on_page,
                    "tables": tables_on_page
                })

    doc.close()

print(f"✅ Finished processing {len(pdf_files)} PDFs. Total chunks created: {len(texts)}")
