import os
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

MODEL_NAME = 'all-MiniLM-L6-v2'
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def create_vector_store(chunks: list[str], save_path: str):
    """Create FAISS vector store from text chunks and save to disk."""
    model = _get_model()

    # Create embeddings
    embeddings = model.encode(chunks, show_progress_bar=False)
    embeddings = np.array(embeddings, dtype='float32')

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Inner product = cosine after normalization
    index.add(embeddings)

    # Save index and chunks
    os.makedirs(save_path, exist_ok=True)
    faiss.write_index(index, os.path.join(save_path, 'index.faiss'))

    with open(os.path.join(save_path, 'chunks.pkl'), 'wb') as f:
        pickle.dump(chunks, f)


def load_vector_store(save_path: str):
    """Load FAISS index and chunks from disk."""
    index = faiss.read_index(os.path.join(save_path, 'index.faiss'))

    with open(os.path.join(save_path, 'chunks.pkl'), 'rb') as f:
        chunks = pickle.load(f)

    return {'index': index, 'chunks': chunks}


def search_similar_chunks(vector_store: dict, query: str, top_k: int = 3) -> list[str]:
    model = _get_model()

    query_embedding = model.encode([query])
    query_embedding = np.array(query_embedding, dtype='float32')

    faiss.normalize_L2(query_embedding)

    index = vector_store['index']
    chunks = vector_store['chunks']

    k = min(top_k, len(chunks))

    scores, indices = index.search(query_embedding, k)

    results = []

    print("\n===== SEARCH RESULTS =====")

    for score, idx in zip(scores[0], indices[0]):

        print(f"Score: {score}")

        if idx != -1:
            print(chunks[idx][:300])

            results.append(chunks[idx])

    return results
