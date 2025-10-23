import sqlite3
import os
from contextlib import contextmanager

DATABASE_PATH = "search_engine.db"

@contextmanager
def get_conn():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # This allows dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database with tables and FTS5 index."""
    print("🔧 Initializing database...")
    
    with get_conn() as conn:
        # Create main pages table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                content TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status_code INTEGER DEFAULT 200
            )
        ''')
        
        # Create FTS5 virtual table for full-text search
        conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
                title,
                content,
                content='pages',
                content_rowid='id'
            )
        ''')
        
        # Create triggers to keep FTS5 in sync with main table
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS pages_fts_insert AFTER INSERT ON pages BEGIN
                INSERT INTO pages_fts(rowid, title, content) 
                VALUES (new.id, new.title, new.content);
            END
        ''')
        
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS pages_fts_delete AFTER DELETE ON pages BEGIN
                INSERT INTO pages_fts(pages_fts, rowid, title, content) 
                VALUES('delete', old.id, old.title, old.content);
            END
        ''')
        
        conn.execute('''
            CREATE TRIGGER IF NOT EXISTS pages_fts_update AFTER UPDATE ON pages BEGIN
                INSERT INTO pages_fts(pages_fts, rowid, title, content) 
                VALUES('delete', old.id, old.title, old.content);
                INSERT INTO pages_fts(rowid, title, content) 
                VALUES (new.id, new.title, new.content);
            END
        ''')
        
        # Create indexes for better performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pages_crawled_at ON pages(crawled_at)')
        
        conn.commit()
        print("✅ Database initialized successfully!")

def get_stats():
    """Get database statistics."""
    with get_conn() as conn:
        total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        fts_entries = conn.execute("SELECT COUNT(*) FROM pages_fts").fetchone()[0]
        
        return {
            'total_pages': total_pages,
            'fts_entries': fts_entries,
            'db_size': os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0
        }

def clear_database():
    """Clear all data from database (for testing)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM pages")
        conn.commit()
        print("🗑️ Database cleared!")

if __name__ == "__main__":
    # Test the database setup
    init_db()
    stats = get_stats()
    print(f"📊 Database stats: {stats}")