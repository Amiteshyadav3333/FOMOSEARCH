# # utils_text.py
# from bs4 import BeautifulSoup
# import re

# def html_to_text(html: str) -> str:
#     soup = BeautifulSoup(html, 'html.parser')

#     # Remove script/style
#     for tag in soup(['script', 'style', 'noscript']):
#         tag.decompose()

#     text = soup.get_text('\n')
#     # Normalize whitespace
#     text = re.sub(r'\s+', ' ', text).strip()
#     return text


import re
import html
from bs4 import BeautifulSoup
import html2text

def clean_html(html_content):
    """Convert HTML to clean, readable text."""
    if not html_content:
        return ""
    
    try:
        # Use html2text for better conversion
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.ignore_tables = False
        h.body_width = 0  # Don't wrap lines
        
        text = h.handle(html_content)
        
        # Clean up the text
        text = clean_text(text)
        
        return text
        
    except Exception as e:
        print(f"Error in html2text conversion: {e}")
        # Fallback to BeautifulSoup
        return clean_html_bs4(html_content)

def clean_html_bs4(html_content):
    """Fallback HTML cleaning with BeautifulSoup."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted tags
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        
        # Get text and clean it
        text = soup.get_text()
        return clean_text(text)
        
    except Exception as e:
        print(f"Error in BeautifulSoup conversion: {e}")
        return clean_text_basic(html_content)

def clean_text(text):
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Keep paragraph breaks
    
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.,!?;:()\-"\']', ' ', text)
    
    # Clean up spacing around punctuation
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)
    
    # Trim and remove excessive newlines
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def clean_text_basic(html_content):
    """Basic text cleaning without external libraries."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def extract_title_from_html(html_content):
    """Extract title from HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title_tag = soup.find('title')
        
        if title_tag and title_tag.string:
            title = clean_text(title_tag.string)
            return title[:200] if title else "Untitled"
        
        # Fallback to h1
        h1_tag = soup.find('h1')
        if h1_tag:
            title = clean_text(h1_tag.get_text())
            return title[:200] if title else "Untitled"
            
        return "Untitled"
        
    except Exception as e:
        print(f"Error extracting title: {e}")
        return "Untitled"

def truncate_text(text, max_length=1000):
    """Truncate text to specified length while preserving word boundaries."""
    if not text or len(text) <= max_length:
        return text
    
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + "..."

def normalize_url(url):
    """Normalize URL for consistent storage."""
    if not url:
        return url
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Remove fragment identifiers
    url = re.sub(r'#.*$', '', url)
    
    # Remove common tracking parameters
    tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
    for param in tracking_params:
        url = re.sub(f'[?&]{param}=[^&]*', '', url)
    
    # Clean up remaining parameters
    url = re.sub(r'[?&]$', '', url)
    
    return url

if __name__ == "__main__":
    # Test the functions
    test_html = '''
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome to Test</h1>
        <p>This is a <strong>test</strong> paragraph with <a href="#">links</a>.</p>
        <script>console.log("ignore this");</script>
    </body>
    </html>
    '''
    
    print("Title:", extract_title_from_html(test_html))
    print("Clean text:", clean_html(test_html))