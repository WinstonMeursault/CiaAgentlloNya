"""Unit tests for core.knowledge (chunking, formatting, RAG retrieval)."""

from core.knowledge import KnowledgeBase, chunkText


class _FakeEmbedder:
    """Deterministic embedder: vector = [len(text)] (no model download)."""

    def __init__(self) -> None:
        self.calls = []

    def embed(self, texts):
        self.calls.extend(texts)
        return [[float(len(text))] for text in texts]


class _FakeStore:
    """In-memory stand-in for a vector store."""

    def __init__(self) -> None:
        self.added = []
        self.queries = []
        self.nextResults = []
        self.raiseOnQuery = False

    def add(self, ids, embeddings, documents, metadatas) -> None:
        self.added.append((ids, embeddings, documents, metadatas))

    def query(self, embedding, topK):
        self.queries.append((embedding, topK))
        if self.raiseOnQuery:
            raise RuntimeError("store down")
        return self.nextResults


class TestChunkText:
    def test_empty_input(self):
        assert chunkText("") == []
        assert chunkText("   ") == []

    def test_shorter_than_chunk(self):
        assert chunkText("hello", chunkSize=100) == ["hello"]

    def test_split_with_overlap(self):
        # length 10, chunk 4, overlap 1 -> step 3
        assert chunkText("0123456789", chunkSize=4, overlap=1) == ["0123", "3456", "6789"]

    def test_nonpositive_chunk_returns_whole(self):
        assert chunkText("abc", chunkSize=0) == ["abc"]


class TestFormat:
    def test_empty(self):
        assert KnowledgeBase.format([]) == ""

    def test_formats_title_and_text(self):
        results = [
            {"title": "T1", "text": "body1"},
            {"source": "s2", "text": "body2"},
        ]
        out = KnowledgeBase.format(results)
        assert "[1] T1\nbody1" in out
        assert "[2] s2\nbody2" in out

    def test_missing_title_falls_back(self):
        out = KnowledgeBase.format([{"text": "x"}])
        assert "[1]" in out


class TestRetrieve:
    def _make(self, **cfg):
        embedder = _FakeEmbedder()
        store = _FakeStore()
        kb = KnowledgeBase(cfg, embedder=embedder, store=store)
        return kb, embedder, store

    def test_returns_store_results(self):
        kb, _, store = self._make()
        store.nextResults = [{"title": "t", "text": "x"}]
        assert kb.retrieve("hello") == [{"title": "t", "text": "x"}]
        # default topK=3, query vector = [len("hello")] = [5.0]
        assert store.queries == [([5.0], 3)]

    def test_empty_query_skips(self):
        kb, _, store = self._make()
        assert kb.retrieve("  ") == []
        assert store.queries == []

    def test_store_error_degrades(self):
        kb, _, store = self._make()
        store.raiseOnQuery = True
        assert kb.retrieve("hello") == []

    def test_topk_override(self):
        kb, _, store = self._make()
        kb.retrieve("hi", topK=5)
        assert store.queries == [([2.0], 5)]


class TestIndex:
    def test_indexes_supported_files(self, tmp_path):
        embedder = _FakeEmbedder()
        store = _FakeStore()
        (tmp_path / "a.md").write_text("hello world", encoding="utf-8")
        (tmp_path / "b.txt").write_text("second file", encoding="utf-8")
        (tmp_path / "skip.pdf").write_text("ignored", encoding="utf-8")
        kb = KnowledgeBase({"doc_dir": str(tmp_path)}, embedder=embedder, store=store)
        assert kb.index() == 2  # one short chunk per supported doc
        assert len(store.added) == 2
        for ids, embeddings, documents, metadatas in store.added:
            assert len(ids) == 1
            assert metadatas[0]["source"].endswith((".md", ".txt"))

    def test_missing_dir_returns_zero(self, tmp_path):
        embedder = _FakeEmbedder()
        store = _FakeStore()
        kb = KnowledgeBase({"doc_dir": str(tmp_path / "nope")}, embedder=embedder, store=store)
        assert kb.index() == 0
        assert store.added == []
