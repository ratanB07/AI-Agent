# app.py placeholder
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import uuid
import json
import numpy as np
import faiss
import hashlib
import time
from datetime import datetime, timedelta
import base64
from dotenv import load_dotenv
import requests
from pathlib import Path
import tempfile
import shutil
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Azure OpenAI configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

# Create necessary directories
UPLOAD_FOLDER = Path("uploads")
VECTOR_FOLDER = Path("vectors")
UPLOAD_FOLDER.mkdir(exist_ok=True)
VECTOR_FOLDER.mkdir(exist_ok=True)

# Configure app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'csv', 'txt', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Simple in-memory database for demo purposes
db = {
    'documents': {},
    'embeddings': {},
    'leads': {},
    'conversations': {}
}

# Initialize FAISS index
embedding_dimension = 1536  # OpenAI embeddings dimension
index = faiss.IndexFlatL2(embedding_dimension)

# Azure OpenAI API functions
def generate_completion(prompt, system_message="You are a helpful assistant."):
    """Generate a completion using Azure OpenAI API"""
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }
    
    payload = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 800
    }
    
    response = requests.post(
        f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return "Sorry, I couldn't generate a response at this time."

def generate_embeddings(text):
    """Generate embeddings using Azure OpenAI API"""
    # For demo purposes, we'll create random embeddings
    # In production, you would call the actual embedding API
    return np.random.rand(1, embedding_dimension).astype('float32')

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# Lead Research AI Agent routes
@app.route('/lead-research')
def lead_research():
    return render_template('lead_research.html')

@app.route('/api/generate-leads', methods=['POST'])
def generate_leads():
    company_name = request.json.get('company_name', '')
    if not company_name:
        return jsonify({'error': 'Company name is required'}), 400
    
    # Generate fictional decision-makers using GPT-4o
    prompt = f"""
    Generate 3 fictional decision-makers for an Australian company called "{company_name}" in the construction or manufacturing industry.
    For each person, provide:
    1. Full name
    2. Job title (CFO, CTO, Digital Transformation Lead, etc.)
    3. A fictional work email
    4. A brief description of their role
    
    Format the response as JSON with the structure:
    [
        {{
            "name": "Full Name",
            "title": "Job Title",
            "email": "email@company.com",
            "description": "Brief description"
        }}
    ]
    """
    
    try:
        response = generate_completion(prompt)
        # Try to parse the response as JSON
        leads = json.loads(response)
        
        # Store leads in our "database"
        lead_id = str(uuid.uuid4())
        db['leads'][lead_id] = {
            'company': company_name,
            'leads': leads,
            'created_at': datetime.now().isoformat(),
            'status': 'new'
        }
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'leads': leads
        })
    except json.JSONDecodeError:
        # If GPT-4o doesn't return valid JSON, format it ourselves
        fallback_leads = [
            {
                "name": "Sarah Johnson",
                "title": "Chief Financial Officer",
                "email": f"sjohnson@{company_name.lower().replace(' ', '')}.com.au",
                "description": "Oversees all financial operations and strategic financial planning."
            },
            {
                "name": "Michael Chen",
                "title": "Digital Transformation Lead",
                "email": f"mchen@{company_name.lower().replace(' ', '')}.com.au",
                "description": "Leads digital initiatives and technology adoption across the organization."
            },
            {
                "name": "David Williams",
                "title": "Operations Director",
                "email": f"dwilliams@{company_name.lower().replace(' ', '')}.com.au",
                "description": "Manages day-to-day operations and process improvement initiatives."
            }
        ]
        
        lead_id = str(uuid.uuid4())
        db['leads'][lead_id] = {
            'company': company_name,
            'leads': fallback_leads,
            'created_at': datetime.now().isoformat(),
            'status': 'new'
        }
        
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'leads': fallback_leads
        })

@app.route('/api/simulate-campaign', methods=['POST'])
def simulate_campaign():
    lead_id = request.json.get('lead_id')
    lead_index = int(request.json.get('lead_index', 0))
    
    if not lead_id or lead_id not in db['leads']:
        return jsonify({'error': 'Invalid lead ID'}), 400
    
    lead_data = db['leads'][lead_id]
    selected_lead = lead_data['leads'][lead_index]
    
    # Generate email templates
    initial_email = generate_completion(
        f"Write a professional initial outreach email to {selected_lead['name']}, {selected_lead['title']} at {lead_data['company']}, " +
        "introducing Reverend.ai's AI platform services. Keep it concise and focused on value proposition."
    )
    
    followup_1 = generate_completion(
        f"Write a follow-up email to {selected_lead['name']} after no response to the initial outreach. " +
        "Reference the previous email and add a new angle about how Reverend.ai can help their specific industry."
    )
    
    followup_2 = generate_completion(
        f"Write a final, personalized 1-on-1 follow-up to {selected_lead['name']} that's more direct and includes " +
        "a specific call to action for a demo or meeting."
    )
    
    # Simulate a positive response
    positive_response = generate_completion(
        f"Write a positive response from {selected_lead['name']} expressing interest in learning more about Reverend.ai's services " +
        "and asking about scheduling a demo."
    )
    
    # Create a conversation timeline
    now = datetime.now()
    conversation = {
        'id': str(uuid.uuid4()),
        'lead': selected_lead,
        'company': lead_data['company'],
        'timeline': [
            {
                'type': 'email',
                'direction': 'outbound',
                'subject': 'Introduction to Reverend.ai AI Platform',
                'content': initial_email,
                'date': now.isoformat(),
                'status': 'sent'
            },
            {
                'type': 'email',
                'direction': 'outbound',
                'subject': 'Re: Introduction to Reverend.ai AI Platform',
                'content': followup_1,
                'date': (now + timedelta(days=3)).isoformat(),
                'status': 'scheduled'
            },
            {
                'type': 'email',
                'direction': 'outbound',
                'subject': 'Re: Introduction to Reverend.ai AI Platform',
                'content': followup_2,
                'date': (now + timedelta(days=7)).isoformat(),
                'status': 'scheduled'
            }
        ]
    }
    
    # Store the conversation
    db['conversations'][conversation['id']] = conversation
    
    return jsonify({
        'success': True,
        'conversation_id': conversation['id'],
        'conversation': conversation
    })

@app.route('/api/simulate-response', methods=['POST'])
def simulate_response():
    conversation_id = request.json.get('conversation_id')
    
    if not conversation_id or conversation_id not in db['conversations']:
        return jsonify({'error': 'Invalid conversation ID'}), 400
    
    conversation = db['conversations'][conversation_id]
    lead = conversation['lead']
    
    # Generate a positive response
    positive_response = generate_completion(
        f"Write a positive response from {lead['name']} expressing interest in learning more about Reverend.ai's services " +
        "and asking about scheduling a demo."
    )
    
    # Add the response to the timeline
    now = datetime.now()
    response_entry = {
        'type': 'email',
        'direction': 'inbound',
        'subject': 'Re: Introduction to Reverend.ai AI Platform',
        'content': positive_response,
        'date': now.isoformat(),
        'status': 'received'
    }
    
    # Add Slack notification
    slack_notification = {
        'type': 'slack',
        'direction': 'system',
        'content': f"🎉 New lead response! {lead['name']} from {conversation['company']} has replied to your email.",
        'date': now.isoformat(),
        'status': 'sent'
    }
    
    # Add calendar booking
    calendar_booking = {
        'type': 'calendar',
        'direction': 'system',
        'content': f"Meeting with {lead['name']} - {conversation['company']} Demo",
        'date': (now + timedelta(days=2, hours=2)).isoformat(),
        'status': 'scheduled'
    }
    
    # Update the conversation
    conversation['timeline'].append(response_entry)
    conversation['timeline'].append(slack_notification)
    conversation['timeline'].append(calendar_booking)
    
    # Update the conversation in the database
    db['conversations'][conversation_id] = conversation
    
    return jsonify({
        'success': True,
        'conversation': conversation
    })

# Knowledge Q&A Agent routes
@app.route('/knowledge-qa')
def knowledge_qa():
    # Get list of uploaded documents
    documents = list(db['documents'].values())
    return render_template('knowledge_qa.html', documents=documents)

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Extract text from file (simplified for demo)
        file_content = ""
        if filename.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        elif filename.endswith('.csv'):
            file_content = f"CSV file content would be processed here: {filename}"
        elif filename.endswith('.pdf'):
            file_content = f"PDF file content would be extracted here: {filename}"
        elif filename.endswith('.docx'):
            file_content = f"DOCX file content would be extracted here: {filename}"
        
        # Generate a document summary using GPT-4o
        summary = generate_completion(
            f"Summarize the following document in 2-3 sentences:\n\n{file_content[:2000]}..."
        )
        
        # Create document record
        doc_id = str(uuid.uuid4())
        document = {
            'id': doc_id,
            'filename': filename,
            'path': file_path,
            'summary': summary,
            'uploaded_at': datetime.now().isoformat()
        }
        
        # Store document in our "database"
        db['documents'][doc_id] = document
        
        # Generate embeddings for the document (simplified)
        embeddings = generate_embeddings(file_content)
        db['embeddings'][doc_id] = embeddings
        
        # Add to FAISS index
        index.add(embeddings)
        
        return jsonify({
            'success': True,
            'document': document
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/api/ask-question', methods=['POST'])
def ask_question():
    question = request.json.get('question', '')
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    # Get document IDs to search in
    doc_ids = request.json.get('doc_ids', list(db['documents'].keys()))
    
    if not doc_ids:
        return jsonify({'error': 'No documents available to search'}), 400
    
    # Generate embedding for the question
    question_embedding = generate_embeddings(question)
    
    # In a real implementation, we would search the FAISS index
    # For demo purposes, we'll just use GPT-4o to generate an answer
    
    # Get document content (simplified)
    context = ""
    for doc_id in doc_ids[:3]:  # Limit to 3 documents for context
        if doc_id in db['documents']:
            doc = db['documents'][doc_id]
            context += f"\nDocument: {doc['filename']}\nSummary: {doc['summary']}\n"
    
    # Generate answer using GPT-4o with RAG approach
    prompt = f"""
    Based on the following document summaries, answer the user's question.
    If the answer cannot be determined from the provided information, say so.
    
    {context}
    
    User Question: {question}
    """
    
    answer = generate_completion(prompt, system_message="You are a knowledge assistant that only answers based on the provided documents.")
    
    return jsonify({
        'success': True,
        'question': question,
        'answer': answer
    })

if __name__ == "__main__":
    app.run(debug=True)

