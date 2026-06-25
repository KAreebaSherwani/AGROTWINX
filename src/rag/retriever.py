# src/rag/retriever.py
"""
Retrieve the most relevant advisory chunks for a query using pgvector cosine
distance (<=>). Returns chunks WITH their source + page for citation.

Used by the disease detector to ground treatment advice in real documents.
"""
import os
import numpy as np
import psycopg2, psycopg2.extras
from pgvector.psycopg2 import register_vector
from src.rag.embedder import Embedder


class AdvisoryRetriever:
    def __init__(self, mock_embed: bool = False):
        dsn = os.getenv("DATABASE_URL", "").replace("+asyncpg", "").replace("+psycopg2", "")
        self.conn = psycopg2.connect(dsn)
        register_vector(self.conn)
        self.embedder = Embedder(mock=mock_embed)

    def search(self, query: str, k: int = 3, disease_key: str | None = None):
        qvec = np.array(self.embedder.embed(query, task="retrieval_query"), dtype=float)
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where = ""
        params = [qvec]
        if disease_key:
            where = "WHERE disease_key = %s"
            params = [disease_key, qvec]  # filter first, then order by distance
            sql = (f"SELECT source, page, crop, disease_key, content, last_updated, "
                   f"1 - (embedding <=> %s) AS similarity "
                   f"FROM agronomy_chunks {where} ORDER BY embedding <=> %s LIMIT %s")
            params = [qvec, disease_key, qvec, k]
        else:
            sql = ("SELECT source, page, crop, disease_key, content, last_updated, "
                   "1 - (embedding <=> %s) AS similarity "
                   "FROM agronomy_chunks ORDER BY embedding <=> %s LIMIT %s")
            params = [qvec, qvec, k]
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()