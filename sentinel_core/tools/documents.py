"""Document Q&A: index the user's PDFs/Word/text files locally, search by
meaning, cite sources. Everything stays on-device (fastembed + sqlite-vec).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from langchain_core.tools import tool

from .. import embeddings
from ..store import Store

logger = logging.getLogger(__name__)

EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILES = 150
MAX_FILE_MB = 20
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
TIME_BUDGET_S = 120

_store: Store | None = None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join((page.extract_text() or "") for page in reader.pages[:100])
    if suffix == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8", errors="replace")


def _chunks(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    out = []
    start = 0
    while start < len(text):
        out.append(text[start : start + CHUNK_CHARS])
        start += CHUNK_CHARS - CHUNK_OVERLAP
    return out[:400]


def _index_folder_blocking(folder: Path) -> str:
    store = _get_store()
    model = embeddings._get_model()
    deadline = time.monotonic() + TIME_BUDGET_S
    files = [
        p
        for p in sorted(folder.rglob("*"))
        if p.suffix.lower() in EXTENSIONS and p.is_file()
        and p.stat().st_size <= MAX_FILE_MB * 1024 * 1024
    ][:MAX_FILES]
    indexed = skipped = failed = 0
    for path in files:
        if time.monotonic() > deadline:
            return (
                f"Time budget hit: indexed {indexed}, skipped {skipped} unchanged, "
                f"{failed} failed; run again to continue."
            )
        mtime = path.stat().st_mtime
        if store.doc_file_mtime(str(path)) == mtime:
            skipped += 1
            continue
        try:
            chunks = _chunks(_extract_text(path))
            if not chunks:
                failed += 1
                continue
            store.delete_doc_file(str(path))
            vectors = list(model.embed(chunks))
            for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False)):
                chunk_id = store.add_doc_chunk(str(path), mtime, i, chunk)
                store.index_doc_chunk(chunk_id, list(vector))
            indexed += 1
        except Exception:  # noqa: BLE001 — one bad file must not stop the batch
            logger.exception("Indexing failed for %s", path)
            failed += 1
    stats = store.doc_stats()
    return (
        f"Indexed {indexed} files ({skipped} unchanged, {failed} failed). "
        f"Library now: {stats['files']} files, {stats['chunks']} chunks."
    )


@tool
async def index_documents(folder: str) -> str:
    """Index a folder of documents (.pdf, .docx, .txt, .md) so their content
    becomes searchable. Re-run to pick up changes; unchanged files are skipped.

    Args:
        folder: folder path, e.g. "C:/Users/me/Documents" or "~/Downloads".
    """
    path = Path(os.path.expandvars(os.path.expanduser(folder.strip())))
    if not path.is_dir():
        return f"Not a folder: {path}"
    return await asyncio.to_thread(_index_folder_blocking, path)


@tool
async def search_documents(question: str, limit: int = 6) -> str:
    """Search the indexed documents by meaning and return the most relevant
    passages with their source file paths. Index folders first if empty.

    Args:
        question: what to look for.
        limit: max passages.
    """
    store = _get_store()
    if store.doc_stats()["chunks"] == 0:
        return "No documents indexed yet — ask the user which folder to index."
    try:
        results = store.doc_search(await embeddings.embed_async(question), limit=limit)
    except Exception:  # noqa: BLE001
        logger.exception("Document search failed")
        return "Document search is unavailable right now."
    if not results:
        return "Nothing relevant found in the indexed documents."
    parts = [
        f"[{Path(r['path']).name} — chunk {r['chunk_index']}]\n{r['text'][:500]}"
        for r in results
    ]
    return "\n\n".join(parts)


@tool
def documents_status() -> str:
    """How many files and text chunks are currently indexed."""
    stats = _get_store().doc_stats()
    return f"Indexed: {stats['files']} files, {stats['chunks']} chunks."


TOOLS = [index_documents, search_documents, documents_status]
