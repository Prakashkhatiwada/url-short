
from flask import Flask, request, redirect, jsonify, render_template
from flask_cors import CORS
import pymysql
import pymysql.cursors
import string
import random
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configuration - Uses environment variables with defaults
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '12345'),
    'database': os.environ.get('DB_NAME', 'url_shortener'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000/')
if not BASE_URL.endswith('/'):
    BASE_URL += '/'
SHORT_CODE_LENGTH = 4

def get_db():
    """Get database connection."""
    conn = pymysql.connect(**DB_CONFIG)
    return conn

def init_db():
    """Initialize the database with required tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INT AUTO_INCREMENT PRIMARY KEY,
            original_url TEXT NOT NULL,
            short_code VARCHAR(20) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INT DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def generate_short_code(length=SHORT_CODE_LENGTH):
    """Generate a unique random short code."""
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(characters, k=length))
        # Check if code already exists
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM urls WHERE short_code = %s', (code,))
        if cursor.fetchone() is None:
            conn.close()
            return code
        conn.close()

def is_valid_url(url):
    """Basic URL validation."""
    return url.startswith(('http://', 'https://'))

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Serve the frontend page."""
    return render_template('index.html')

@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    """API endpoint to create a shortened URL."""
    data = request.get_json()
    
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    
    original_url = data['url'].strip()
    
    # Validate URL
    if not original_url:
        return jsonify({'error': 'URL cannot be empty'}), 400
    
    if not is_valid_url(original_url):
        return jsonify({'error': 'Invalid URL. Must start with http:// or https://'}), 400
    
    # Check if URL already exists
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT short_code FROM urls WHERE original_url = %s', (original_url,))
    existing = cursor.fetchone()
    
    if existing:
        short_code = existing['short_code']
    else:
        # Generate new short code
        short_code = generate_short_code()
        cursor.execute(
            'INSERT INTO urls (original_url, short_code) VALUES (%s, %s)',
            (original_url, short_code)
        )
        conn.commit()
    
    conn.close()
    
    short_url = BASE_URL + short_code
    
    return jsonify({
        'success': True,
        'original_url': original_url,
        'short_url': short_url,
        'short_code': short_code
    })

@app.route('/api/stats/<short_code>', methods=['GET'])
def get_stats(short_code):
    """Get statistics for a shortened URL."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT original_url, short_code, created_at, click_count FROM urls WHERE short_code = %s',
        (short_code,)
    )
    url_data = cursor.fetchone()
    conn.close()
    
    if not url_data:
        return jsonify({'error': 'Short URL not found'}), 404
    
    return jsonify({
        'original_url': url_data['original_url'],
        'short_code': url_data['short_code'],
        'short_url': BASE_URL + url_data['short_code'],
        'created_at': url_data['created_at'],
        'click_count': url_data['click_count']
    })

@app.route('/api/urls', methods=['GET'])
def get_all_urls():
    """Get all shortened URLs."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM urls ORDER BY created_at DESC')
    urls = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'urls': [{
            'id': url['id'],
            'original_url': url['original_url'],
            'short_url': BASE_URL + url['short_code'],
            'short_code': url['short_code'],
            'created_at': url['created_at'],
            'click_count': url['click_count']
        } for url in urls]
    })

@app.route('/<short_code>')
def redirect_to_url(short_code):
    """Redirect short URL to original URL."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT original_url FROM urls WHERE short_code = %s', (short_code,))
    url_data = cursor.fetchone()
    
    if not url_data:
        conn.close()
        return render_template('404.html'), 404
    
    # Increment click count
    cursor.execute(
        'UPDATE urls SET click_count = click_count + 1 WHERE short_code = %s',
        (short_code,)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_data['original_url'])

@app.route('/api/delete/<short_code>', methods=['DELETE'])
def delete_url(short_code):
    """Delete a shortened URL."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM urls WHERE short_code = %s', (short_code,))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Short URL not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'URL deleted successfully'})

# ==================== MAIN ====================

if __name__ == '__main__':
    init_db()
    print("\n🔗 URL Shortener is running!")
    print(f"📍 Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
