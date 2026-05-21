"""
ResearchFlow Lite - Multi-Agent Research Assistant
Main Flask Application Entry Point
"""

import os
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from agents.supervisor import SupervisorAgent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize Supervisor Agent
supervisor = SupervisorAgent()

@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/research', methods=['POST'])
def research():
    """
    Handle research requests
    Expects JSON: {"topic": "research topic"}
    Returns: JSON with research results
    """
    try:
        data = request.get_json()
        topic = data.get('topic', '').strip()
        
        if not topic:
            return jsonify({'error': 'Please provide a research topic'}), 400
        
        logger.info(f"Starting research on topic: {topic}")
        
        # Execute multi-agent workflow
        result = supervisor.process_query(topic)
        
        logger.info(f"Research completed for topic: {topic}")
        return jsonify({
            'success': True,
            'topic': topic,
            'research_result': result
        })
        
    except Exception as e:
        logger.error(f"Error processing research: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'ResearchFlow Lite'})

if __name__ == '__main__':
    # Run Flask app
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)