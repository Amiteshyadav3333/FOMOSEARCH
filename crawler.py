import asyncio
import aiohttp
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, quote_plus
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import requests
from db import get_conn
from utils_text import clean_html, extract_title_from_html, normalize_url
import random
from collections import deque
import sqlite3

class MassiveCrawler:
    def __init__(self, max_workers=20, max_pages=100000, delay_range=(0.5, 2.0)):
        self.max_workers = max_workers
        self.max_pages = max_pages
        self.delay_range = delay_range
        self.crawled_urls = set()
        self.failed_urls = set()
        self.robots_cache = {}
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; MegaSearchBot/2.0; +http://example.com/bot)'
        }
        
        # URL queues for different priorities
        self.high_priority_queue = deque()  # News, blogs, forums
        self.medium_priority_queue = deque()  # Documentation, tutorials  
        self.low_priority_queue = deque()    # Other content
        
        # Statistics
        self.stats = {
            'crawled': 0,
            'failed': 0,
            'duplicates': 0,
            'robots_blocked': 0
        }

    def get_seed_urls(self):
        """Get massive list of seed URLs to start crawling"""
        return [
            # Tech & Programming
            "https://stackoverflow.com/",
            "https://github.com/",
            "https://medium.com/",
            "https://dev.to/",
            "https://hackernoon.com/",
            "https://docs.python.org/",
            "https://flask.palletsprojects.com/",
            "https://reactjs.org/",
            "https://nodejs.org/",
            "https://developer.mozilla.org/",
            
            # News & Information
            "https://news.ycombinator.com/",
            "https://reddit.com/r/programming/",
            "https://reddit.com/r/technology/",
            "https://techcrunch.com/",
            "https://arstechnica.com/",
            
            # Educational
            "https://www.khanacademy.org/",
            "https://www.coursera.org/",
            "https://www.udemy.com/",
            "https://www.freecodecamp.org/",
            
            # Wikis & Reference
            "https://en.wikipedia.org/",
            "https://stackoverflow.com/",
            "https://superuser.com/",
            "https://serverfault.com/",
            
            # Blogs & Tutorials
            "https://realpython.com/",
            "https://css-tricks.com/",
            "https://smashingmagazine.com/",
            "https://alistapart.com/",
            
            # Documentation sites
            "https://docs.djangoproject.com/",
            "https://laravel.com/docs/",
            "https://vuejs.org/",
            "https://angular.io/",
            
            # Forums & Communities
            "https://discourse.org/",
            "https://lobste.rs/",
            "https://www.indiehackers.com/"
        ]

    def check_robots_txt(self, url):
        """Check if URL is allowed by robots.txt"""
        try:
            domain = urlparse(url).netloc
            if domain in self.robots_cache:
                return self.robots_cache[domain]
            
            robots_url = f"https://{domain}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            allowed = rp.can_fetch(self.session_headers['User-Agent'], url)
            self.robots_cache[domain] = allowed
            return allowed
        except:
            return True  # If can't check robots.txt, assume allowed

    def get_priority(self, url):
        """Assign priority to URLs based on content type"""
        url_lower = url.lower()
        
        # High priority: News, blogs, recent content
        if any(keyword in url_lower for keyword in ['news', 'blog', 'article', '2024', '2023']):
            return 'high'
        
        # Medium priority: Documentation, tutorials
        if any(keyword in url_lower for keyword in ['docs', 'tutorial', 'guide', 'learn']):
            return 'medium'
        
        return 'low'

    def add_url_to_queue(self, url):
        """Add URL to appropriate priority queue"""
        if url in self.crawled_urls:
            self.stats['duplicates'] += 1
            return
        
        priority = self.get_priority(url)
        if priority == 'high':
            self.high_priority_queue.append(url)
        elif priority == 'medium':
            self.medium_priority_queue.append(url)
        else:
            self.low_priority_queue.append(url)

    def get_next_url(self):
        """Get next URL from priority queues"""
        if self.high_priority_queue:
            return self.high_priority_queue.popleft()
        elif self.medium_priority_queue:
            return self.medium_priority_queue.popleft()
        elif self.low_priority_queue:
            return self.low_priority_queue.popleft()
        return None

    def extract_content_and_links(self, url, html_content):
        """Extract content and find new URLs to crawl"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract links
            new_urls = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                full_url = normalize_url(full_url)
                
                if self.is_valid_url(full_url):
                    new_urls.append(full_url)
            
            # Extract title and content
            title = extract_title_from_html(html_content)
            content = clean_html(html_content)
            
            return title, content, new_urls
            
        except Exception as e:
            print(f"Error extracting content from {url}: {e}")
            return None, None, []

    def is_valid_url(self, url):
        """Enhanced URL validation"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Skip certain file types
            skip_extensions = [
                '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', 
                '.zip', '.exe', '.dmg', '.iso', '.mp4', '.avi',
                '.mp3', '.wav', '.doc', '.docx', '.xls', '.xlsx'
            ]
            if any(url.lower().endswith(ext) for ext in skip_extensions):
                return False
            
            # Skip certain domains
            skip_domains = [
                'facebook.com', 'twitter.com', 'instagram.com', 
                'linkedin.com', 'pinterest.com', 'youtube.com'
            ]
            if any(domain in parsed.netloc.lower() for domain in skip_domains):
                return False
            
            # Only crawl HTTP/HTTPS
            if parsed.scheme not in ['http', 'https']:
                return False
                
            return True
        except:
            return False

    def fetch_url(self, url):
        """Fetch single URL with error handling"""
        try:
            if not self.check_robots_txt(url):
                self.stats['robots_blocked'] += 1
                return None
            
            print(f"🌐 Crawling [{self.stats['crawled']+1}/{self.max_pages}]: {url}")
            
            session = requests.Session()
            session.headers.update(self.session_headers)
            
            response = session.get(url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                return None
            
            # Check content length (skip huge pages)
            if len(response.content) > 5 * 1024 * 1024:  # 5MB limit
                print(f"⚠️ Skipping large page: {len(response.content)} bytes")
                return None
            
            return response.text, response.status_code
            
        except Exception as e:
            print(f"❌ Failed to fetch {url}: {str(e)[:100]}")
            self.failed_urls.add(url)
            self.stats['failed'] += 1
            return None

    def save_page(self, url, title, content, status_code=200):
        """Save page to database with error handling"""
        try:
            # Skip if content too short
            if len(content.strip()) < 100:
                return False
            
            with get_conn() as conn:
                # Check if URL already exists
                existing = conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
                if existing:
                    return False
                
                # Insert new page
                conn.execute('''
                    INSERT INTO pages (url, title, content, status_code) 
                    VALUES (?, ?, ?, ?)
                ''', (url, title[:500], content[:50000], status_code))  # Limit lengths
                
                conn.commit()
                return True
                
        except sqlite3.IntegrityError:
            return False  # Duplicate URL
        except Exception as e:
            print(f"❌ Error saving page {url}: {e}")
            return False

    def crawl_single_url(self, url):
        """Crawl a single URL and return new URLs"""
        if url in self.crawled_urls or len(self.crawled_urls) >= self.max_pages:
            return []
        
        self.crawled_urls.add(url)
        
        # Random delay to be respectful
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
        
        # Fetch page
        result = self.fetch_url(url)
        if not result:
            return []
        
        html_content, status_code = result
        
        # Extract content and links
        title, clean_content, new_urls = self.extract_content_and_links(url, html_content)
        
        # Save to database
        if clean_content and title:
            if self.save_page(url, title, clean_content, status_code):
                self.stats['crawled'] += 1
                print(f"✅ Saved: {title[:50]}... ({len(clean_content)} chars)")
        
        return new_urls[:20]  # Limit new URLs per page

    def run_massive_crawl(self):
        """Run massive multi-threaded crawling"""
        print(f"🚀 Starting MASSIVE crawl with {self.max_workers} workers")
        print(f"🎯 Target: {self.max_pages:,} pages")
        
        # Initialize with seed URLs
        for url in self.get_seed_urls():
            self.add_url_to_queue(url)
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while (len(self.crawled_urls) < self.max_pages and 
                   (self.high_priority_queue or self.medium_priority_queue or self.low_priority_queue)):
                
                # Submit batch of URLs for processing
                futures = []
                batch_size = min(self.max_workers * 2, self.max_pages - len(self.crawled_urls))
                
                for _ in range(batch_size):
                    url = self.get_next_url()
                    if not url:
                        break
                    
                    future = executor.submit(self.crawl_single_url, url)
                    futures.append(future)
                
                if not futures:
                    break
                
                # Process completed futures
                for future in as_completed(futures):
                    try:
                        new_urls = future.result()
                        # Add new URLs to queues
                        for new_url in new_urls:
                            if len(self.crawled_urls) < self.max_pages:
                                self.add_url_to_queue(new_url)
                    except Exception as e:
                        print(f"Future error: {e}")
                
                # Print progress
                elapsed = time.time() - start_time
                rate = self.stats['crawled'] / elapsed if elapsed > 0 else 0
                print(f"\n📊 Progress: {self.stats['crawled']:,}/{self.max_pages:,} pages")
                print(f"⚡ Rate: {rate:.1f} pages/sec")
                print(f"⏱️ Elapsed: {elapsed/60:.1f} mins")
                print(f"📈 Queue sizes: H:{len(self.high_priority_queue)}, M:{len(self.medium_priority_queue)}, L:{len(self.low_priority_queue)}")
        
        # Final statistics
        total_time = time.time() - start_time
        print(f"\n🎉 CRAWLING COMPLETED!")
        print(f"✅ Successfully crawled: {self.stats['crawled']:,} pages")
        print(f"❌ Failed: {self.stats['failed']:,}")
        print(f"🔄 Duplicates skipped: {self.stats['duplicates']:,}")
        print(f"🤖 Robots blocked: {self.stats['robots_blocked']:,}")
        print(f"⏱️ Total time: {total_time/60:.1f} minutes")
        print(f"⚡ Average rate: {self.stats['crawled']/total_time:.1f} pages/sec")
        
        return self.stats['crawled']

def run_insane_crawl():
    """Run insane scale crawling"""
    crawler = MassiveCrawler(
        max_workers=50,      # 50 parallel workers
        max_pages=500000,    # Half a million pages!
        delay_range=(0.1, 1.0)  # Faster crawling
    )
    
    return crawler.run_massive_crawl()

if __name__ == "__main__":
    print("🕷️ MASSIVE WEB CRAWLER - Google Scale")
    print("=" * 50)
    
    choice = input("""
Choose crawling scale:
1. 🏃 Quick test (1,000 pages)
2. 🚀 Medium scale (50,000 pages) 
3. 🔥 INSANE scale (500,000+ pages)
4. 🌟 Custom scale

Enter choice (1-4): """).strip()
    
    if choice == "1":
        crawler = MassiveCrawler(max_workers=10, max_pages=1000)
        crawler.run_massive_crawl()
    elif choice == "2":
        crawler = MassiveCrawler(max_workers=25, max_pages=50000)
        crawler.run_massive_crawl()
    elif choice == "3":
        run_insane_crawl()
    elif choice == "4":
        pages = int(input("How many pages to crawl? "))
        workers = int(input("How many parallel workers? (recommended: 20-50) "))
        crawler = MassiveCrawler(max_workers=workers, max_pages=pages)
        crawler.run_massive_crawl()
    else:
        print("Invalid choice!")