# src/rag/ingest_advisories.py
"""
Load advisory documents (PDF or .txt) into the agronomy_chunks vector store.

Folder layout (you supply real Punjab advisories):
    data/advisories/
        rice_blast_punjab_2026.pdf
        wheat_yellow_rust_advisory.txt
        ...
Filename (before extension) is used as the default disease_key/source tag.

    python -m src.rag.ingest_advisories                 # real embeddings
    python -m src.rag.ingest_advisories --mock          # offline test
"""
import os, sys, glob, argparse
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from src.rag.embedder import Embedder

ADV_DIR = "data/advisories"
CHUNK_CHARS = 900
OVERLAP = 150


def read_text(path):
    if path.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            return [(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(PdfReader(path).pages)]
        except Exception as e:
            print(f"  ⚠️  PDF read failed ({e}); install pypdf or use .txt")
            return []
    with open(path, encoding="utf-8") as f:
        return [(1, f.read())]


def chunk(text):
    text = " ".join(text.split())
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK_CHARS])
        i += CHUNK_CHARS - OVERLAP
    return [c for c in out if c.strip()]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mock", action="store_true")
    ap.add_argument("--dir", default=ADV_DIR); args = ap.parse_args()

    dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "").replace("+psycopg2", "")
    conn = psycopg2.connect(dsn); register_vector(conn); cur = conn.cursor()
    emb = Embedder(mock=args.mock)

    files = glob.glob(os.path.join(args.dir, "*.pdf")) + glob.glob(os.path.join(args.dir, "*.txt"))
    if not files:
        print(f"❌ No PDFs/txt in {args.dir}/ — add advisory documents first."); sys.exit(1)

    total = 0
    for path in files:
        tag = os.path.splitext(os.path.basename(path))[0]
        crop = "rice" if "rice" in tag.lower() else ("wheat" if "wheat" in tag.lower() else None)
        for page, text in read_text(path):
            for ch in chunk(text):
                vec = np.array(emb.embed(ch, task="retrieval_document"), dtype=float)
                cur.execute(
                    "INSERT INTO agronomy_chunks (source, disease_key, crop, page, content, last_updated, embedding) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (tag, tag, crop, page, ch, "see source document", vec))
                total += 1
        conn.commit()
        print(f"  ✅ {os.path.basename(path)} -> chunks embedded")
    print(f"\n✅ Ingested {total} chunks into agronomy_chunks")
    conn.close()


if __name__ == "__main__":
    main()