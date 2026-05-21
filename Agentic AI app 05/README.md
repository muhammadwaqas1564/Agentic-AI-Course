# DocChat — RAG Document Assistant

A minimal RAG (Retrieval-Augmented Generation) web app built with Flask, LangChain, FAISS, and OpenRouter.

---

## Folder Structure

```
rag-app/
├── app.py                    # Flask application
├── requirements.txt
├── .env.example
├── .gitignore
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
├── utils/
│   ├── __init__.py
│   ├── document_processor.py  # PDF/DOCX extraction + chunking
│   ├── vector_store.py         # FAISS embeddings + search
│   └── llm_client.py           # OpenRouter API client
├── uploads/                   # Uploaded files (auto-created)
└── vectorstore/               # FAISS index + chunks (auto-created)
```

---

## Setup

### 1. Clone / download the project
```bash
cd rag-app
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> Note: `sentence-transformers` will download the `all-MiniLM-L6-v2` model (~90 MB) on first run.

### 4. Configure API key

Get a free key from [openrouter.ai](https://openrouter.ai)

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. Run the app
```bash
python app.py
```

Open: [http://localhost:5000](http://localhost:5000)

---

## Usage

1. Upload a PDF or DOCX file using the sidebar
2. Wait for processing (text extraction + FAISS indexing)
3. Ask questions in the chat interface
4. The AI answers **only** from the uploaded document

---

## Configuration

Edit these values in the source files as needed:

| Setting | File | Default |
|---|---|---|
| Chunk size | `utils/document_processor.py` | 800 |
| Chunk overlap | `utils/document_processor.py` | 100 |
| Top-K retrieval | `app.py` | 3 |
| LLM model | `utils/llm_client.py` | `meta-llama/llama-3-8b-instruct:free` |
| Max file size | `app.py` | 16 MB |

---

## Tech Stack

- **Flask** — web framework
- **LangChain** — text splitting
- **sentence-transformers** — embeddings (`all-MiniLM-L6-v2`)
- **FAISS** — vector similarity search
- **PyPDF2** — PDF text extraction
- **python-docx** — DOCX text extraction
- **OpenRouter** — LLM API (free Llama 3 8B)
