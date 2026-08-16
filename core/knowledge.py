"""
Semantic knowledge base (RAG) module for the nekomimi bot.

Provides a local, offline retrieval-augmented generation backend:

- "chunkText" splits documents into overlapping chunks.
- "KnowledgeBase" indexes documents under a directory - embedding them with
  "fastembed"/BGE and storing vectors in a persistent local "chromadb" - and
  retrieves the top-k most similar chunks for a query.

Heavy dependencies ("fastembed", "chromadb") are imported lazily inside the
concrete embedder/store backends, so importing this module stays cheap and the
RAG path can be disabled entirely by configuration (see
"core/config/configExample.yaml" -> "llm.enhance.rag").
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

#: Document extensions indexed by default.
SUPPORTED_EXTENSIONS = frozenset({".md", ".txt"})


def chunkText(text: str, chunkSize: int = 800, overlap: int = 100) -> List[str]:
    """Split "text" into overlapping chunks of roughly "chunkSize" chars.

    Args:
        text: Raw document text.
        chunkSize: Target chunk length in characters; must be positive.
        overlap: Number of characters shared between adjacent chunks.

    Returns:
        A list of non-empty chunk strings, or an empty list for empty input.
    """
    text = text.strip()
    if not text:
        return []
    if chunkSize <= 0:
        return [text]
    overlap = max(0, min(overlap, chunkSize - 1))
    step = chunkSize - overlap
    if step <= 0:
        step = chunkSize
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunkSize, length)
        chunks.append(text[start:end])
        if end >= length:
            break
        start += step
    return chunks


class Embedder:
    """Minimal embedding interface implemented by concrete backends."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts into a list of float vectors."""
        raise NotImplementedError


class VectorStore:
    """Minimal vector-store interface implemented by concrete backends."""

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        """Upsert documents with their embeddings and metadata."""
        raise NotImplementedError

    def query(self, embedding: List[float], topK: int) -> List[Dict[str, Any]]:
        """Return the top-k most similar documents for a query embedding."""
        raise NotImplementedError


class FastEmbedEmbedder(Embedder):
    """Local ONNX embeddings via "fastembed" (BGE), loaded lazily."""

    def __init__(self, modelName: str = "BAAI/bge-small-zh-v1.5") -> None:
        """Store the model name; the model itself loads on first use."""
        self.modelName = modelName
        self._model = None

    def _ensureModel(self):
        """Import and instantiate the fastembed model exactly once."""
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.modelName)
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts, returning plain Python float lists."""
        model = self._ensureModel()
        vectors = model.embed(texts)
        return [[float(value) for value in vector] for vector in vectors]


class ChromaStore(VectorStore):
    """Persistent "chromadb" collection, loaded lazily."""

    def __init__(self, persistDirectory: str, collectionName: str = "knowledge") -> None:
        """Store the persistence path; the client loads on first use."""
        self.persistDirectory = persistDirectory
        self.collectionName = collectionName
        self._collection = None

    def _ensureCollection(self):
        """Import and open the chromadb collection exactly once."""
        if self._collection is None:
            import chromadb

            client = chromadb.PersistentClient(path=self.persistDirectory)
            # Embeddings are always supplied explicitly, so no default embedding
            # function (and therefore no model download) is ever triggered.
            self._collection = client.get_or_create_collection(
                name=self.collectionName, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    @staticmethod
    def _sanitizeMeta(meta: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce metadata to chromadb-compatible primitives (no "None")."""
        out: Dict[str, Any] = {}
        for key, value in meta.items():
            if value is None:
                value = ""
            if isinstance(value, (str, int, float, bool)):
                out[key] = value
            else:
                out[key] = str(value)
        return out

    def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        collection = self._ensureCollection()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=[self._sanitizeMeta(meta) for meta in metadatas],
        )

    def query(self, embedding: List[float], topK: int) -> List[Dict[str, Any]]:
        collection = self._ensureCollection()
        raw = collection.query(query_embeddings=[embedding], n_results=topK)
        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]
        results: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            meta = metadatas[index] if index < len(metadatas) else {}
            if not isinstance(meta, dict):
                meta = {}
            results.append(
                {
                    "id": ids[index] if index < len(ids) else "",
                    "text": document,
                    "source": meta.get("source", ""),
                    "title": meta.get("title", ""),
                    "chunk_index": meta.get("chunk_index", index),
                    "distance": distances[index] if index < len(distances) else None,
                }
            )
        return results


class KnowledgeBase:
    """Indexes and queries a local semantic knowledge base.

    Attributes:
        docDir: Directory scanned for supported document extensions.
        chunkSize: Target chunk length in characters.
        chunkOverlap: Overlap between adjacent chunks.
        topK: Default number of chunks to retrieve per query.
        embedder: Embedding backend (defaults to "FastEmbedEmbedder").
        store: Vector store backend (defaults to a persistent "ChromaStore").
    """

    def __init__(
        self,
        config: Dict[str, Any],
        embedder: Optional[Embedder] = None,
        store: Optional[VectorStore] = None,
    ) -> None:
        """Initialize from the "enhance.rag" config dict.

        Args:
            config: The "enhance.rag" mapping (empty dict is acceptable).
            embedder: Optional custom embedding backend (tests/fakes).
            store: Optional custom vector store backend (tests/fakes).
        """
        self.logger = logger.bind(module="knowledge")
        self.config = config or {}
        self.docDir = str(self.config.get("doc_dir", "./core/knowledge"))
        self.chunkSize = int(self.config.get("chunk_size", 800))
        self.chunkOverlap = int(self.config.get("chunk_overlap", 100))
        self.topK = int(self.config.get("top_k", 3))

        defaultDbPath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "database", "rag_store"
        )
        dbPath = str(self.config.get("db_path") or defaultDbPath)

        self.embedder = embedder or FastEmbedEmbedder(
            str(self.config.get("embedding_model", "BAAI/bge-small-zh-v1.5"))
        )
        self.store = store or ChromaStore(persistDirectory=dbPath)

    def index(self, docDir: Optional[str] = None) -> int:
        """Index all supported documents under "docDir" into the store.

        Args:
            docDir: Directory to scan; defaults to "self.docDir".

        Returns:
            Number of chunks added (0 if the directory is missing/empty).
        """
        root = Path(docDir or self.docDir)
        if not root.is_dir():
            self.logger.warning(f"RAG doc_dir not found, skipping index: {root}")
            return 0
        count = 0
        for filePath in sorted(root.rglob("*")):
            if not filePath.is_file() or filePath.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                text = filePath.read_text(encoding="utf-8")
            except OSError as exc:
                self.logger.warning(f"Failed to read {filePath}: {exc}")
                continue
            for idx, chunk in enumerate(chunkText(text, self.chunkSize, self.chunkOverlap)):
                self._indexChunk(filePath, idx, chunk)
                count += 1
        if count:
            self.logger.info(f"Indexed {count} chunks into RAG store.")
        return count

    def _indexChunk(self, filePath: Path, idx: int, chunk: str) -> None:
        """Embed and upsert a single chunk with its source metadata."""
        relative = str(filePath)
        chunkId = f"{relative}:{idx}"
        embedding = self.embedder.embed([chunk])[0]
        self.store.add(
            ids=[chunkId],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[
                {
                    "source": relative,
                    "title": filePath.stem,
                    "chunk_index": idx,
                    "updated_at": str(int(filePath.stat().st_mtime)),
                }
            ],
        )

    def retrieve(self, query: str, topK: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the top-k most similar chunks for "query".

        Any embedding/store error degrades to an empty list so the persona
        answer is never blocked by the RAG path.
        """
        query = (query or "").strip()
        if not query:
            return []
        topK = topK or self.topK
        if topK <= 0:
            return []
        try:
            embedding = self.embedder.embed([query])[0]
            return self.store.query(embedding, topK)
        except Exception as exc:
            self.logger.warning(f"RAG retrieval failed: {exc}")
            return []

    @staticmethod
    def format(results: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into one background-information block."""
        if not results:
            return ""
        blocks: List[str] = []
        for index, result in enumerate(results, start=1):
            title = result.get("title") or result.get("source") or f"片段 {index}"
            text = str(result.get("text", "")).strip()
            blocks.append(f"[{index}] {title}\n{text}")
        return "\n\n".join(blocks)
