from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
import uuid
from datetime import datetime
import base64
from werkzeug.utils import secure_filename
import git
from github import Github
import tempfile

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')  # Format: username/repository-name

# Allowed extensions for image upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_id():
    """Generate a unique member ID"""
    return f"TR{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"

def save_to_github(file_path, content, commit_message, is_binary=False):
    """Save content to GitHub repository"""
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return False, "GitHub configuration missing"
        
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        
        try:
            # Try to get existing file
            file = repo.get_contents(file_path)
            if is_binary:
                repo.update_file(file_path, commit_message, content, file.sha)
            else:
                repo.update_file(file_path, commit_message, content, file.sha)
        except:
            # File doesn't exist, create new
            if is_binary:
                repo.create_file(file_path, commit_message, content)
            else:
                repo.create_file(file_path, commit_message, content)
        
        return True, "Success"
    except Exception as e:
        return False, str(e)

def get_from_github(file_path):
    """Get content from GitHub repository"""
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return None, "GitHub configuration missing"
        
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        file = repo.get_contents(file_path)
        return file.decoded_content.decode('utf-8'), None
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/verify')
def verify():
    return render_template('verify.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        # Get form data
        name = request.form.get('name')
        branch = request.form.get('branch')
        email = request.form.get('email')
        department = request.form.get('department')
        
        # Validate required fields
        if not all([name, branch, email, department]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        
        # Handle file upload
        if 'photo' not in request.files:
            return jsonify({'success': False, 'message': 'Photo is required'})
        
        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({'success': False, 'message': 'No photo selected'})
        
        if not allowed_file(photo.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload PNG, JPG, JPEG, or GIF'})
        
        # Generate unique ID
        member_id = generate_unique_id()
        
        # Create member data
        member_data = {
            'id': member_id,
            'name': name,
            'branch': branch,
            'email': email,
            'department': department,
            'date_joined': datetime.now().isoformat(),
            'photo_path': f'Photos/{member_id}.{photo.filename.rsplit(".", 1)[1].lower()}'
        }
        
        # Save photo to GitHub
        photo_content = base64.b64encode(photo.read()).decode('utf-8')
        photo_success, photo_error = save_to_github(
            member_data['photo_path'],
            photo_content,
            f"Add photo for member {member_id}",
            is_binary=True
        )
        
        if not photo_success:
            return jsonify({'success': False, 'message': f'Failed to save photo: {photo_error}'})
        
        # Save member details to GitHub
        details_path = f'Details/{member_id}.json'
        details_success, details_error = save_to_github(
            details_path,
            json.dumps(member_data, indent=2),
            f"Add member details for {member_id}"
        )
        
        if not details_success:
            return jsonify({'success': False, 'message': f'Failed to save details: {details_error}'})
        
        # Save ID mapping
        id_mapping_path = 'Ids/id_mapping.json'
        existing_mapping, _ = get_from_github(id_mapping_path)
        
        if existing_mapping:
            id_mapping = json.loads(existing_mapping)
        else:
            id_mapping = {}
        
        id_mapping[member_id] = {
            'name': name,
            'details_path': details_path,
            'photo_path': member_data['photo_path']
        }
        
        mapping_success, mapping_error = save_to_github(
            id_mapping_path,
            json.dumps(id_mapping, indent=2),
            f"Update ID mapping for {member_id}"
        )
        
        if not mapping_success:
            return jsonify({'success': False, 'message': f'Failed to save ID mapping: {mapping_error}'})
        
        return jsonify({
            'success': True,
            'message': 'Member registered successfully!',
            'member_id': member_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Registration failed: {str(e)}'})

@app.route('/api/verify', methods=['POST'])
def api_verify():
    try:
        member_id = request.form.get('member_id')
        
        if not member_id:
            return jsonify({'success': False, 'message': 'Member ID is required'})
        
        # Get member details from GitHub
        details_path = f'Details/{member_id}.json'
        member_details, error = get_from_github(details_path)
        
        if error or not member_details:
            return jsonify({'success': False, 'message': 'Member not found'})
        
        member_data = json.loads(member_details)
        
        return jsonify({
            'success': True,
            'member': {
                'id': member_data['id'],
                'name': member_data['name'],
                'branch': member_data['branch'],
                'email': member_data['email'],
                'department': member_data['department'],
                'date_joined': member_data['date_joined']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Verification failed: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True)