import os
import json
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from utils.document_processor import extract_text, split_into_chunks
from utils.vector_store import create_vector_store, load_vector_store, search_similar_chunks
from utils.llm_client import get_answer

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx'}

VECTORSTORE_PATH = 'vectorstore'
document_loaded = {'status': False, 'filename': ''}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF and DOCX are allowed.'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Extract text from document
        text = extract_text(filepath)
        if not text.strip():
            return jsonify({'error': 'Could not extract text from document.'}), 400

        # Split into chunks
        chunks = split_into_chunks(text)
        if not chunks:
            return jsonify({'error': 'Document too small to process.'}), 400

        # Create vector store
        create_vector_store(chunks, VECTORSTORE_PATH)

        document_loaded['status'] = True
        document_loaded['filename'] = filename

        return jsonify({
            'success': True,
            'filename': filename,
            'chunks': len(chunks),
            'message': f'Document processed successfully. {len(chunks)} chunks created.'
        })

    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500


@app.route('/chat', methods=['POST'])
def chat():
    if not document_loaded['status']:
        return jsonify({'error': 'Please upload a document first.'}), 400

    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    user_message = data['message'].strip()
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    try:
        # Load vector store and search
        vector_store = load_vector_store(VECTORSTORE_PATH)
        relevant_chunks = search_similar_chunks(vector_store, user_message, top_k=3)

        if not relevant_chunks:
            return jsonify({'response': 'Information not available in uploaded document.'})

        # Get answer from LLM
        answer = get_answer(user_message, relevant_chunks)
        return jsonify({'response': answer})

    except Exception as e:
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500


@app.route('/status', methods=['GET'])
def status():
    return jsonify(document_loaded)


if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('vectorstore', exist_ok=True)
    app.run(debug=True, port=5000)
