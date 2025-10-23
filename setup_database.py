#!/usr/bin/env python3
"""
Setup database for FOMO Search Engine
"""

import sqlite3
from db import get_conn, init_db

def setup_search_database():
    """Setup the complete search database with FTS"""
    print("🗄️ Setting up FOMO Search Database...")
    
    try:
        # Initialize database using the proper db.py function
        init_db()
        
        with get_conn() as conn:
            
            # Add some sample data if database is empty
            count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            if count == 0:
                print("📝 Adding sample data...")
                sample_pages = [
                    ("https://www.python.org/", "Python Programming Language", 
                     "Python is a programming language that lets you work quickly and integrate systems more effectively. Python's simple, easy to learn syntax emphasizes readability and therefore reduces the cost of program maintenance."),
                    ("https://flask.palletsprojects.com/", "Flask Web Framework", 
                     "Flask is a lightweight WSGI web application framework in Python. It is designed to make getting started quick and easy, with the ability to scale up to complex applications."),
                    ("https://reactjs.org/", "React JavaScript Library", 
                     "A JavaScript library for building user interfaces. React makes it painless to create interactive UIs. Design simple views for each state in your application."),
                    ("https://stackoverflow.com/", "Stack Overflow", 
                     "Stack Overflow is the largest online community for programmers to learn, share their knowledge, and build their careers. Join the world's largest developer community."),
                    ("https://github.com/", "GitHub", 
                     "GitHub is where over 100 million developers shape the future of software, together. Contribute to the open source community, manage your Git repositories, and review code like a pro.")
                ]
                
                for url, title, content in sample_pages:
                    conn.execute('''
                        INSERT OR IGNORE INTO pages (url, title, content) 
                        VALUES (?, ?, ?)
                    ''', (url, title, content))
                
                conn.commit()
                print(f"✅ Added {len(sample_pages)} sample pages")
            
            # Check final status
            total_pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            try:
                fts_entries = conn.execute("SELECT COUNT(*) FROM pages_fts").fetchone()[0]
            except:
                fts_entries = 0
            
            print(f"✅ Database setup complete!")
            print(f"📊 Total pages: {total_pages}")
            print(f"🔍 FTS entries: {fts_entries}")
            
            if total_pages == 0:
                print("\n⚠️ Database is empty. Run the crawler to add content:")
                print("   python3 run_crawler.py")
            else:
                print("\n🚀 Ready to start search engine:")
                print("   python3 app.py")
            
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_search_database()