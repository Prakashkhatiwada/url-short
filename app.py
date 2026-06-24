from flask import Flask, request, redirect, jsonify, render_template
from flask_cors import CORS
import sqlite3
import string
import random
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'url_shortener.db'))
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000/')
if not BASE_URL.endswith('/'):
    BASE_URL += '/'
SHORT_CODE_LENGTH = 4

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            click_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

def generate_short_code(length=SHORT_CODE_LENGTH):
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choices(characters, k=length))
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM urls WHERE short_code = ?', (code,))
        if cursor.fetchone() is None:
            conn.close()
            return code
        conn.close()

def is_valid_url(url):
    return url.startswith(('http://', 'https://'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'URL is required'}), 400
    original_url = data['url'].strip()
    if not original_url:
        return jsonify({'error': 'URL cannot be empty'}), 400
    if not is_valid_url(original_url):
        return jsonify({'error': 'Invalid URL. Must start with http:// or https://'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT short_code FROM urls WHERE original_url = ?', (original_url,))
    existing = cursor.fetchone()
    if existing:
        short_code = existing['short_code']
    else:
        short_code = generate_short_code()
        cursor.execute(
            'INSERT INTO urls (original_url, short_code) VALUES (?, ?)',
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT original_url, short_code, created_at, click_count FROM urls WHERE short_code = ?',
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
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT original_url FROM urls WHERE short_code = ?', (short_code,))
    url_data = cursor.fetchone()
    if not url_data:
        conn.close()
        return render_template('404.html'), 404
    cursor.execute(
        'UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?',
        (short_code,)
    )
    conn.commit()
    conn.close()
    return redirect(url_data['original_url'])

@app.route('/api/delete/<short_code>', methods=['DELETE'])
def delete_url(short_code):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM urls WHERE short_code = ?', (short_code,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Short URL not found'}), 404
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'URL deleted successfully'})

if __name__ == '__main__':
    init_db()
    print("\n URL Shortener is running!")
    print(f" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
