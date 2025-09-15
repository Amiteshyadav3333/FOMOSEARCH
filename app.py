from flask import Flask, render_template, request, jsonify
import sqlite3
import math
import re
import time
from urllib.parse import urlparse
from db import get_conn
from datetime import datetime, timedelta

app = Flask(__name__)

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
                snippet(pages_fts, 2, '<mark>', '</mark>', ' … ', 15) AS snippet,
                bm25(pages_fts) AS rank,
                p.crawled_at,
                LENGTH(p.content) as content_length
            FROM pages_fts
            JOIN pages p ON p.id = pages_fts.page_id
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
            JOIN pages p ON p.id = pages_fts.page_id
            WHERE pages_fts MATCH ?
        """
        
        if conditions:
            count_query += " AND " + " AND ".join(conditions)
        
        count_params = [fts_query] + params[1:-2]  # Exclude LIMIT/OFFSET params
        
        return base_query, params, count_query, count_params
    
    def search(self, query, page=1, time_filter=None, sort_by='relevance'):
        """Perform advanced search"""
        start_time = time.time()
        
        try:
            operators = self.parse_search_query(query)
            
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
                
                # Add domain info and clean snippets
                for result in results:
                    result['domain'] = urlparse(result['url']).netloc
                    result['crawled_date'] = result['crawled_at'].split(' ')[0] if result['crawled_at'] else ''
                    # Clean snippet
                    if result.get('snippet'):
                        result['snippet'] = result['snippet'][:300] + '...' if len(result['snippet']) > 300 else result['snippet']
                
                # Apply exclusions (post-processing for complex logic)
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
    """Homepage with advanced search options"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>FOMO Search - Google Scale</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: arial,sans-serif; background: #fff; }
            .header { padding: 20px; text-align: center; }
            .logo { font-size: 90px; color: #4285f4; margin-bottom: 30px; }
            .search-container { max-width: 600px; margin: 0 auto; }
            .search-box { display: flex; border: 1px solid #dfe1e5; border-radius: 24px; padding: 10px 20px; }
            .search-box:hover { box-shadow: 0 2px 5px 1px rgba(64,60,67,.16); }
            .search-box input { border: none; outline: none; flex: 1; font-size: 16px; }
            .search-btn { background: #f8f9fa; border: 1px solid #f8f9fa; border-radius: 4px; color: #3c4043; cursor: pointer; font-size: 14px; margin: 11px 4px; min-width: 54px; padding: 0 16px; text-align: center; height: 36px; }
            .search-btn:hover { box-shadow: 0 1px 1px rgba(0,0,0,.1); background-color: #f1f3f4; }
            .advanced-options { margin: 20px 0; text-align: center; }
            .filters { display: inline-block; margin: 5px; }
            .filters select, .filters input { padding: 5px; margin: 0 5px; border: 1px solid #ddd; border-radius: 3px; }
            .suggestions { text-align: center; margin-top: 30px; }
            .suggestions a { display: inline-block; margin: 5px; padding: 8px 16px; background: #f1f3f4; text-decoration: none; color: #1a73e8; border-radius: 20px; }
            .stats { text-align: center; margin-top: 30px; color: #70757a; }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">🔍 FOMO</div>
            <div class="search-container">
                <form action="/search" method="GET" onsubmit="return validateSearch()">
                    <div class="search-box">
                        <input type="text" name="q" id="searchInput" placeholder="Search the web..." autocomplete="off">
                        <button type="submit" style="background: none; border: none; cursor: pointer;">🔍</button>
                    </div>
                    
                    <div class="advanced-options">
                        <div class="filters">
                            <label>Time:</label>
                            <select name="time">
                                <option value="">Any time</option>
                                <option value="day">Past day</option>
                                <option value="week">Past week</option>
                                <option value="month">Past month</option>
                                <option value="year">Past year</option>
                            </select>
                        </div>
                        
                        <div class="filters">
                            <label>Sort:</label>
                            <select name="sort">
                                <option value="relevance">Relevance</option>
                                <option value="date">Date</option>
                            </select>
                        </div>
                        
                        <div class="filters">
                            <input type="checkbox" id="exactMatch" onchange="toggleExact()">
                            <label for="exactMatch">Exact phrase</label>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <button type="submit" class="search-btn">FOMO Search</button>
                        <button type="button" class="search-btn" onclick="feelingLucky()">I'm Feeling Lucky</button>
                    </div>
                </form>
            </div>
            
            <div class="suggestions">
                <strong>Advanced search examples:</strong><br>
                <a href='/search?q="machine learning"'>Exact phrase: "machine learning"</a>
                <a href='/search?q=python -java'>Exclude: python -java</a>
                <a href='/search?q=site:stackoverflow.com'>Site: site:stackoverflow.com</a>
                <a href='/search?q=intitle:tutorial'>In title: intitle:tutorial</a>
                <a href='/search?q=inurl:github'>In URL: inurl:github</a>
            </div>
            
            <div class="stats" id="statsDiv">
                Loading database stats...
            </div>
        </div>
        
        <script>
            function validateSearch() {
                const input = document.getElementById('searchInput');
                if (!input.value.trim()) {
                    alert('Please enter a search query');
                    return false;
                }
                return true;
            }
            
            function toggleExact() {
                const input = document.getElementById('searchInput');
                const checkbox = document.getElementById('exactMatch');
                if (checkbox.checked) {
                    if (!input.value.includes('"')) {
                        input.value = '"' + input.value + '"';
                    }
                } else {
                    input.value = input.value.replace(/"/g, '');
                }
            }
            
            function feelingLucky() {
                const queries = [
                    'python tutorial', 'machine learning', 'web development',
                    'javascript frameworks', 'data science', 'artificial intelligence',
                    'react hooks', 'flask tutorial', 'algorithm', 'programming'
                ];
                const randomQuery = queries[Math.floor(Math.random() * queries.length)];
                document.getElementById('searchInput').value = randomQuery;
                document.forms[0].submit();
            }
            
            // Load database stats
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('statsDiv').innerHTML = 
                        `📊 ${data.total_pages.toLocaleString()} pages indexed • ⚡ ${data.fts_entries.toLocaleString()} searchable entries`;
                })
                .catch(() => {
                    document.getElementById('statsDiv').innerHTML = '📊 Database stats unavailable';
                });
        </script>
    </body>
    </html>
    """

@app.route('/search')
def search():
    """Advanced search results with pagination"""
    query = request.args.get('q', '').strip()
    page = int(request.args.get('page', 1))
    time_filter = request.args.get('time', '')
    sort_by = request.args.get('sort', 'relevance')
    
    if not query:
        return """
        <h2>No search query provided</h2>
        <p><a href="/">← Go back to search</a></p>
        """
    
    # Perform search
    search_results = search_engine.search(query, page, time_filter, sort_by)
    
    # Generate pagination
    def generate_pagination(current, total_pages, query, time_filter, sort_by):
        if total_pages <= 1:
            return ""
        
        pagination_html = '<div class="pagination">'
        
        # Previous button
        if current > 1:
            prev_url = f"/search?q={query}&page={current-1}&time={time_filter}&sort={sort_by}"
            pagination_html += f'<a href="{prev_url}" class="page-btn">← Previous</a>'
        
        # Page numbers (show 10 pages max)
        start_page = max(1, current - 5)
        end_page = min(total_pages, start_page + 9)
        
        if start_page > 1:
            pagination_html += f'<a href="/search?q={query}&page=1&time={time_filter}&sort={sort_by}" class="page-num">1</a>'
            if start_page > 2:
                pagination_html += '<span class="page-dots">...</span>'
        
        for i in range(start_page, end_page + 1):
            if i == current:
                pagination_html += f'<span class="page-num active">{i}</span>'
            else:
                page_url = f"/search?q={query}&page={i}&time={time_filter}&sort={sort_by}"
                pagination_html += f'<a href="{page_url}" class="page-num">{i}</a>'
        
        if end_page < total_pages:
            if end_page < total_pages - 1:
                pagination_html += '<span class="page-dots">...</span>'
            last_url = f"/search?q={query}&page={total_pages}&time={time_filter}&sort={sort_by}"
            pagination_html += f'<a href="{last_url}" class="page-num">{total_pages}</a>'
        
        # Next button
        if current < total_pages:
            next_url = f"/search?q={query}&page={current+1}&time={time_filter}&sort={sort_by}"
            pagination_html += f'<a href="{next_url}" class="page-btn">Next →</a>'
        
        pagination_html += '</div>'
        return pagination_html
    
    pagination_html = generate_pagination(
        search_results['current_page'], 
        search_results['total_pages'],
        query, time_filter, sort_by
    )
    
    # Results page HTML
    results_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{query} - FOMO Search</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: arial,sans-serif; background: #fff; }}
            .header {{ border-bottom: 1px solid #ebebeb; padding: 20px 0; }}
            .header-content {{ max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; align-items: center; }}
            .logo {{ font-size: 24px; color: #4285f4; margin-right: 30px; text-decoration: none; }}
            .search-form {{ flex: 1; max-width: 600px; }}
            .search-box {{ display: flex; border: 1px solid #dfe1e5; border-radius: 24px; padding: 10px 20px; }}
            .search-box input {{ border: none; outline: none; flex: 1; font-size: 16px; }}
            .filters {{ margin-left: 20px; }}
            .filters select {{ padding: 5px; margin: 0 5px; border: 1px solid #ddd; border-radius: 3px; }}
            
            .main {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            .results-info {{ margin-bottom: 20px; color: #70757a; }}
            .result-item {{ margin-bottom: 30px; max-width: 600px; }}
            .result-title {{ font-size: 18px; line-height: 1.3; }}
            .result-title a {{ color: #1a0dab; text-decoration: none; }}
            .result-title a:hover {{ text-decoration: underline; }}
            .result-url {{ color: #006621; font-size: 14px; margin: 5px 0; }}
            .result-snippet {{ color: #4d5156; line-height: 1.5; margin-top: 5px; }}
            .result-snippet mark {{ background: #ffeb3b; font-weight: normal; }}
            .result-meta {{ font-size: 13px; color: #70757a; margin-top: 5px; }}
            
            .pagination {{ text-align: center; margin: 40px 0; }}
            .page-btn, .page-num {{ display: inline-block; padding: 8px 16px; margin: 0 4px; text-decoration: none; color: #4285f4; }}
            .page-btn:hover, .page-num:hover {{ background: #f1f3f4; border-radius: 4px; }}
            .page-num.active {{ background: #4285f4; color: white; border-radius: 4px; }}
            .page-dots {{ color: #70757a; padding: 8px 4px; }}
            
            .no-results {{ text-align: center; padding: 40px; }}
            .search-tips {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 20px; }}
            .search-tips h4 {{ margin-bottom: 10px; }}
            .search-tips ul {{ list-style-type: none; }}
            .search-tips li {{ margin: 5px 0; }}
            
            .error {{ background: #fce8e6; color: #d93025; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-content">
                <a href="/" class="logo">🔍 FOMO</a>
                <form class="search-form" action="/search" method="GET">
                    <div class="search-box">
                        <input type="text" name="q" value="{query}" autocomplete="off">
                        <button type="submit" style="background: none; border: none; cursor: pointer;">🔍</button>
                    </div>
                    <input type="hidden" name="time" value="{time_filter}">
                    <input type="hidden" name="sort" value="{sort_by}">
                </form>
                <div class="filters">
                    <select onchange="updateFilter('time', this.value)">
                        <option value="" {'selected' if not time_filter else ''}>Any time</option>
                        <option value="day" {'selected' if time_filter == 'day' else ''}>Past day</option>
                        <option value="week" {'selected' if time_filter == 'week' else ''}>Past week</option>
                        <option value="month" {'selected' if time_filter == 'month' else ''}>Past month</option>
                        <option value="year" {'selected' if time_filter == 'year' else ''}>Past year</option>
                    </select>
                    <select onchange="updateFilter('sort', this.value)">
                        <option value="relevance" {'selected' if sort_by == 'relevance' else ''}>Relevance</option>
                        <option value="date" {'selected' if sort_by == 'date' else ''}>Date</option>
                    </select>
                </div>
            </div>
        </div>
        
        <div class="main">
            <div class="results-info">
                About {search_results['total_results']:,} results ({search_results['search_time']:.2f} seconds)
            </div>
    """
    
    if 'error' in search_results:
        results_html += f"""
            <div class="error">
                <strong>Search Error:</strong> {search_results['error']}
            </div>
        """
    elif search_results['results']:
        # Display results
        for result in search_results['results']:
            results_html += f"""
            <div class="result-item">
                <div class="result-title">
                    <a href="{result['url']}" target="_blank">{result['title'] or 'Untitled'}</a>
                </div>
                <div class="result-url">{result['url']}</div>
                <div class="result-snippet">{result.get('snippet', '')}</div>
                <div class="result-meta">
                    {result['domain']} • {result.get('crawled_date', '')} • {result.get('content_length', 0):,} characters
                </div>
            </div>
            """
        
        # Add pagination
        results_html += pagination_html
        
    else:
        # No results
        results_html += f"""
        <div class="no-results">
            <h3>Your search - <strong>{query}</strong> - did not match any documents.</h3>
            
            <div class="search-tips">
                <h4>Search Tips:</h4>
                <ul>
                    <li>• Make sure all words are spelled correctly</li>
                    <li>• Try different keywords</li>
                    <li>• Try more general keywords</li>
                    <li>• Try using quotes for exact phrases: "machine learning"</li>
                    <li>• Try excluding terms: python -java</li>
                    <li>• Try site-specific search: site:stackoverflow.com</li>
                </ul>
            </div>
            
            <p style="margin-top: 20px;">
                <a href="/">← Start a new search</a> |
                <a href="/advanced-crawl">Add more content to search</a>
            </p>
        </div>
        """
    
    results_html += """
        </div>
        
        <script>
            function updateFilter(param, value) {
                const url = new URL(window.location);
                url.searchParams.set(param, value);
                url.searchParams.delete('page'); // Reset to page 1
                window.location.href = url.toString();
            }
        </script>
    </body>
    </html>
    """
    
    return results_html

@app.route('/api/stats')
def api_stats():
    """API endpoint for database statistics"""
    try:
        with get_conn() as conn:
            total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            fts_entries = conn.execute("SELECT COUNT(*) FROM pages_fts").fetchone()[0]
            
            # Get some interesting stats
            top_domains = conn.execute("""
                SELECT 
                    substr(url, instr(url, '://') + 3, 
                           case when instr(substr(url, instr(url, '://') + 3), '/') > 0
                           then instr(substr(url, instr(url, '://') + 3), '/') - 1
                           else length(substr(url, instr(url, '://') + 3)) end) as domain,
                    COUNT(*) as count
                FROM pages 
                WHERE url LIKE 'http%'
                GROUP BY domain 
                ORDER BY count DESC 
                LIMIT 10
            """).fetchall()
            
            recent_crawls = conn.execute("""
                SELECT COUNT(*) 
                FROM pages 
                WHERE crawled_at > datetime('now', '-1 day')
            """).fetchone()[0]
            
        return jsonify({
            'total_pages': total_pages,
            'fts_entries': fts_entries,
            'recent_crawls_24h': recent_crawls,
            'top_domains': [{'domain': row[0], 'count': row[1]} for row in top_domains]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/advanced-crawl')
def advanced_crawl_page():
    """Page to start massive crawling"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Advanced Crawling - FOMO Search</title>
        <style>
            body { font-family: arial,sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            .crawl-option { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #4285f4; }
            .crawl-btn { background: #4285f4; color: white; padding: 12px 24px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            .crawl-btn:hover { background: #3367d6; }
            .warning { background: #fff3cd; color: #856404; padding: 15px; border-radius: 4px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🚀 Advanced Web Crawling</h1>
        <p>Expand your search database by crawling millions of web pages!</p>
        
        <div class="crawl-option">
            <h3>🏃 Quick Crawl (1,000 pages)</h3>
            <p>Perfect for testing. Takes about 5-10 minutes.</p>
            <button class="crawl-btn" onclick="startCrawl(1000, 10)">Start Quick Crawl</button>
        </div>
        
        <div class="crawl-option">
            <h3>🚀 Medium Crawl (50,000 pages)</h3>
            <p>Good balance of content and time. Takes 2-3 hours.</p>
            <button class="crawl-btn" onclick="startCrawl(50000, 25)">Start Medium Crawl</button>
        </div>
        
        <div class="crawl-option">
            <h3>🔥 INSANE Crawl (500,000+ pages)</h3>
            <p>Google-scale crawling! Takes 6-12 hours but gives massive content.</p>
            <button class="crawl-btn" onclick="startCrawl(500000, 50)">Start INSANE Crawl</button>
        </div>
        
        <div class="warning">
            <strong>⚠️ Important:</strong> Large crawls will consume significant bandwidth and storage. 
            Make sure you have sufficient disk space and a stable internet connection.
        </div>
        
        <p><a href="/">← Back to search</a></p>
        
        <script>
            function startCrawl(pages, workers) {
                if (confirm(`Start crawling ${pages.toLocaleString()} pages with ${workers} workers?\\n\\nThis may take several hours to complete.`)) {
                    alert('Crawling started! Check your terminal for progress.\\n\\nYou can continue using the search engine while crawling runs in the background.');
                    fetch('/api/start-crawl', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({pages: pages, workers: workers})
                    });
                }
            }
        </script>
    </body>
    </html>
    """

@app.route('/api/start-crawl', methods=['POST'])
def start_crawl():
    """API to start background crawling"""
    try:
        data = request.get_json()
        pages = data.get('pages', 1000)
        workers = data.get('workers', 10)
        
        # Start crawling in background thread
        def background_crawl():
            from advanced_crawler import MassiveCrawler
            crawler = MassiveCrawler(max_workers=workers, max_pages=pages)
            crawler.run_massive_crawl()
        
        import threading
        crawl_thread = threading.Thread(target=background_crawl)
        crawl_thread.daemon = True
        crawl_thread.start()
        
        return jsonify({'status': 'started', 'pages': pages, 'workers': workers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    print("🚀 Starting FOMO Search Engine - Google Scale!")
    print("=" * 50)
    
    # Initialize database
    from db import init_db
    init_db()
    
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)