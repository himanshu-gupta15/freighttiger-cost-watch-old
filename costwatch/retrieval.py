"""Small in-memory vector index (TF-IDF + cosine similarity).

Used twice: to rank context notes for a flagged route-week, and to find result rows
relevant to a free-text question. TF-IDF is exact and deterministic, needs no model
download, and is plenty for a corpus this size; an embedding model can be swapped in
behind the same `search` interface if the notes grow.
"""

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def tokenize(text: str) -> list[str]:
    """Lowercase, drop stop words, strip a few suffixes so 'flooding' matches 'flood'."""
    tokens = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in ENGLISH_STOP_WORDS:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        tokens.append(word)
    return tokens


class VectorIndex:
    def __init__(self, items: list, texts: list[str]):
        self.items = items
        self.vectorizer = TfidfVectorizer(tokenizer=tokenize, lowercase=False, token_pattern=None,
                                          ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(texts)

    def search(self, query: str, k: int | None = None) -> list[tuple[object, float]]:
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        # Round before sorting so float noise can never reorder ties; ties break on position.
        ranked = sorted(range(len(self.items)), key=lambda i: (-round(float(scores[i]), 6), i))
        return [(self.items[i], round(float(scores[i]), 4)) for i in ranked[:k]]


def note_index(notes) -> VectorIndex:
    return VectorIndex(notes, [f"{n.applies_to}. {n.text}" for n in notes])
