import os
from langchain.text_splitter import RecursiveCharacterTextSplitter


def extract_text(filepath: str) -> str:
    """Extract text from PDF or DOCX file."""
    ext = filepath.rsplit('.', 1)[1].lower()

    if ext == 'pdf':
        return _extract_from_pdf(filepath)
    elif ext == 'docx':
        return _extract_from_docx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_from_pdf(filepath: str) -> str:
    """Extract text from PDF using PyPDF2."""
    import PyPDF2

    text = []
    with open(filepath, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)

    return '\n'.join(text)


def _extract_from_docx(filepath: str) -> str:
    """Extract text from DOCX using python-docx."""
    from docx import Document

    doc = Document(filepath)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return '\n'.join(paragraphs)


def split_into_chunks(text: str) -> list[str]:
    """Split text into chunks using LangChain's text splitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]
