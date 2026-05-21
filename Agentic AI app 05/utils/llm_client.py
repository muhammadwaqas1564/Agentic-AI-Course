import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
# MODEL = 'meta-llama/llama-3-8b-instruct:free'
# MODEL = 'mistralai/mistral-7b-instruct:free'
# MODEL = 'deepseek/deepseek-r1-0528-qwen3-8b'
MODEL = 'openrouter/free'
API_URL = 'https://openrouter.ai/api/v1/chat/completions'


def get_answer(question: str, context_chunks: list[str]) -> str:
    """Get answer from LLM using retrieved context chunks."""

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env file")

    context = '\n\n---\n\n'.join(context_chunks)

    system_prompt = """You are a precise document assistant. Your ONLY job is to answer questions based strictly on the provided document context.

RULES:
1. Answer ONLY using information from the provided context.
2. If the answer is not in the context, respond with exactly: "Information not available in uploaded document."
3. Do not use any external knowledge or make assumptions beyond the context.
4. Be concise and factual.
5. Do not mention that you are using a context or document in your answer — just answer naturally."""

    user_prompt = f"""Context from document:
{context}

Question: {question}

Answer based strictly on the context above:"""

    headers = {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:5000',
        'X-Title': 'RAG Document Chat'
    }

    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'max_tokens': 300,
        'temperature': 0.1
    }

    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

    data = response.json()
    # answer = data['choices'][0]['message']['content'].strip()
    # return answer if answer else "Information not available in uploaded document."
    return data['choices'][0]['message']['content']