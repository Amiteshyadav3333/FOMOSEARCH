from flask import Flask, render_template, request, jsonify, redirect
import sqlite3
import math
import re
import time
from urllib.parse import urlparse
from db import get_conn
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Pages(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), unique=True, nullable=False)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)


class AdvancedSearchEngine:
    def __init__(self):
        self.results_per_page = 20
        self.max_results = 1000  # Google shows ~1000 results max
    
    def parse_search_query(self, query):
        """Parse advanced search operators like Google"""
        operators = {
            'exact_phrase': [],
            'exclude': [],
            'site': None,
            'filetype': None,
            'intitle': [],
            'inurl': [],
            'before': None,
            'after': None,
            'terms': []
        }
        
        # Extract quoted phrases
        exact_phrases = re.findall(r'"([^"]*)"', query)
        operators['exact_phrase'] = exact_phrases
        query = re.sub(r'"[^"]*"', '', query)
        
        # Extract exclusions (-)
        exclude_terms = re.findall(r'-(\w+)', query)
        operators['exclude'] = exclude_terms
        query = re.sub(r'-\w+', '', query)
        
        # Extract site: operator
        site_match = re.search(r'site:(\S+)', query)
        if site_match:
            operators['site'] = site_match.group(1)
            query = re.sub(r'site:\S+', '', query)
        
        # Extract filetype: operator
        filetype_match = re.search(r'filetype:(\w+)', query)
        if filetype_match:
            operators['filetype'] = filetype_match.group(1)
            query = re.sub(r'filetype:\w+', '', query)
        
        # Extract intitle: operator
        intitle_matches = re.findall(r'intitle:(\w+)', query)
        operators['intitle'] = intitle_matches
        query = re.sub(r'intitle:\w+', '', query)
        
        # Extract inurl: operator
        inurl_matches = re.findall(r'inurl:(\w+)', query)
        operators['inurl'] = inurl_matches
        query = re.sub(r'inurl:\w+', '', query)
        
        # Remaining terms
        operators['terms'] = [term for term in query.split() if term.strip()]
        
        return operators
    
    def build_search_query(self, operators, page=1, time_filter=None, sort_by='relevance'):
        """Build complex SQL query based on operators"""
        conditions = []
        params = []
        
        # Base FTS5 query parts
        fts_conditions = []
        
        # Exact phrases
        for phrase in operators['exact_phrase']:
            fts_conditions.append(f'"{phrase}"')
        
        # Regular terms
        if operators['terms']:
            # Use AND for better relevance
            term_query = ' AND '.join(f'"{term}"' for term in operators['terms'])
            fts_conditions.append(f'({term_query})')
        
        # Title searches
        for term in operators['intitle']:
            fts_conditions.append(f'title:"{term}"')
        
        # Combine FTS conditions
        if fts_conditions:
            fts_query = ' AND '.join(fts_conditions)
        else:
            fts_query = '*'  # Match all if no specific terms
        
        # Site filter
        if operators['site']:
            conditions.append("p.url LIKE ?")
            params.append(f"%{operators['site']}%")
        
        # URL filter
        for term in operators['inurl']:
            conditions.append("p.url LIKE ?")
            params.append(f"%{term}%")
        
        # Time filter
        if time_filter:
            if time_filter == 'day':
                conditions.append("p.crawled_at > datetime('now', '-1 day')")
            elif time_filter == 'week':
                conditions.append("p.crawled_at > datetime('now', '-7 days')")
            elif time_filter == 'month':
                conditions.append("p.crawled_at > datetime('now', '-1 month')")
            elif time_filter == 'year':
                conditions.append("p.crawled_at > datetime('now', '-1 year')")
        
        # Build main query
        if sort_by == 'date':
            order_by = "p.crawled_at DESC"
        else:
            order_by = "bm25(pages_fts) ASC"  # Better relevance first
        
        # Pagination
        offset = (page - 1) * self.results_per_page
        
        base_query = f"""
            SELECT
                p.id,
                p.url,
                p.title,
                snippet(pages_fts, 1, '<mark>', '</mark>', ' … ', 15) AS snippet,
                bm25(pages_fts) AS rank,
                p.crawled_at,
                LENGTH(p.content) as content_length
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.rowid
            WHERE pages_fts MATCH ?
        """
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        base_query += f"""
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        
        params = [fts_query] + params + [self.results_per_page, offset]
        
        # Count query for pagination
        count_query = f"""
            SELECT COUNT(*)
            FROM pages_fts
            WHERE pages_fts MATCH ?
        """
        
        if conditions:
            count_query += " AND " + " AND ".join(conditions)
        
        count_params = [fts_query] + params[1:-2]  # Exclude LIMIT/OFFSET params
        
        return base_query, params, count_query, count_params
    
    def calculate_website_rank(self, url, title, content, query_terms):
        """Calculate ranking score - original websites get higher rank"""
        score = 0
        domain = urlparse(url).netloc.lower()
        
        # Original website bonus (main domains get higher rank)
        original_sites = {
            'youtube.com': 100, 'google.com': 95, 'facebook.com': 90,
            'twitter.com': 85, 'instagram.com': 80, 'wikipedia.org': 75,
            'github.com': 70, 'stackoverflow.com': 65, 'reddit.com': 60
        }
        
        for site, bonus in original_sites.items():
            if site in domain:
                score += bonus
                break
        
        # Domain authority bonus
        if any(tld in domain for tld in ['.com', '.org', '.net']):
            score += 20
        
        # Query relevance in title (higher weight)
        if title:
            title_lower = title.lower()
            for term in query_terms:
                if term.lower() in title_lower:
                    score += 30
        
        # Query relevance in URL
        url_lower = url.lower()
        for term in query_terms:
            if term.lower() in url_lower:
                score += 15
        
        # Content length bonus (more content = better)
        if content:
            content_len = len(content)
            if content_len > 1000:
                score += 10
            elif content_len > 500:
                score += 5
        
        return score
    
    def search(self, query, page=1, time_filter=None, sort_by='relevance'):
        """Perform advanced search with Google-like ranking"""
        start_time = time.time()
        
        try:
            operators = self.parse_search_query(query)
            query_terms = operators['terms'] + [phrase for phrase in operators['exact_phrase']]
            
            with get_conn() as conn:
                # Build and execute search query
                search_query, search_params, count_query, count_params = self.build_search_query(
                    operators, page, time_filter, sort_by
                )
                
                # Get total count
                total_results = conn.execute(count_query, count_params).fetchone()[0]
                
                # Get paginated results
                cursor = conn.execute(search_query, search_params)
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
                
                # Add domain info, ranking, and clean snippets
                for result in results:
                    result['domain'] = urlparse(result['url']).netloc
                    result['crawled_date'] = result['crawled_at'].split(' ')[0] if result['crawled_at'] else ''
                    
                    # Calculate custom ranking score
                    result['custom_rank'] = self.calculate_website_rank(
                        result['url'], result['title'], result.get('content', ''), query_terms
                    )
                    
                    # Clean snippet
                    if result.get('snippet'):
                        result['snippet'] = result['snippet'][:300] + '...' if len(result['snippet']) > 300 else result['snippet']
                
                # Sort by custom ranking if relevance sort
                if sort_by == 'relevance':
                    results.sort(key=lambda x: x['custom_rank'], reverse=True)
                
                # Apply exclusions
                if operators['exclude']:
                    filtered_results = []
                    for result in results:
                        content_lower = (result['title'] + ' ' + result.get('snippet', '')).lower()
                        if not any(exclude_term.lower() in content_lower for exclude_term in operators['exclude']):
                            filtered_results.append(result)
                    results = filtered_results
                
                search_time = time.time() - start_time
                total_pages = math.ceil(total_results / self.results_per_page)
                
                return {
                    'results': results,
                    'total_results': total_results,
                    'total_pages': total_pages,
                    'current_page': page,
                    'search_time': search_time,
                    'query': query,
                    'operators': operators,
                    'has_next': page < total_pages,
                    'has_prev': page > 1
                }
                
        except Exception as e:
            print(f"Search error: {e}")
            return {
                'results': [],
                'total_results': 0,
                'total_pages': 0,
                'current_page': 1,
                'search_time': 0,
                'query': query,
                'error': str(e),
                'has_next': False,
                'has_prev': False
            }

# Initialize search engine
search_engine = AdvancedSearchEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    time_filter = request.args.get('time')
    sort_by = request.args.get('sort', 'relevance')
    
    if not query:
        return render_template('index.html')
    
    results = search_engine.search(query, page, time_filter, sort_by)
    return render_template('results.html', **results)

@app.route('/api/voice-search', methods=['POST'])
def voice_search():
    """API for voice search processing"""
    try:
        data = request.get_json()
        transcript = data.get('transcript', '')
        if transcript:
            return jsonify({'success': True, 'query': transcript})
        return jsonify({'success': False, 'error': 'No transcript received'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/image-search', methods=['POST'])
def image_search():
    """API for camera/image search processing"""
    try:
        # This would integrate with OCR or image recognition
        # For now, return a placeholder
        return jsonify({
            'success': True, 
            'extracted_text': 'Sample extracted text from image',
            'suggested_query': 'machine learning'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/favicon.ico')
def favicon():
    return '', 204

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)