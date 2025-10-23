#!/usr/bin/env python3
"""
FOMO Search Engine - Massive Web Crawler
Run this to populate your search database with thousands of websites
"""

from crawler import MassiveCrawler
import sys
import time

def main():
    print("🕷️ FOMO SEARCH ENGINE - MASSIVE WEB CRAWLER")
    print("=" * 60)
    print("This will crawl hundreds of popular websites and add them to your search database!")
    print()
    
    # Ask user for crawling scale
    print("Choose your crawling scale:")
    print("1. 🏃 Quick Start (1,000 pages) - 5-10 minutes")
    print("2. 🚀 Medium Scale (10,000 pages) - 30-60 minutes") 
    print("3. 🔥 Large Scale (50,000 pages) - 2-4 hours")
    print("4. 🌟 INSANE Scale (100,000+ pages) - 4-8 hours")
    print()
    
    choice = input("Enter your choice (1-4): ").strip()
    
    if choice == "1":
        crawler = MassiveCrawler(max_workers=10, max_pages=1000, delay_range=(0.5, 1.5))
        print("\n🏃 Starting Quick Crawl...")
    elif choice == "2":
        crawler = MassiveCrawler(max_workers=20, max_pages=10000, delay_range=(0.3, 1.0))
        print("\n🚀 Starting Medium Scale Crawl...")
    elif choice == "3":
        crawler = MassiveCrawler(max_workers=30, max_pages=50000, delay_range=(0.2, 0.8))
        print("\n🔥 Starting Large Scale Crawl...")
    elif choice == "4":
        crawler = MassiveCrawler(max_workers=50, max_pages=100000, delay_range=(0.1, 0.5))
        print("\n🌟 Starting INSANE Scale Crawl...")
    else:
        print("❌ Invalid choice!")
        return
    
    print(f"🎯 Target: {crawler.max_pages:,} pages")
    print(f"⚡ Workers: {crawler.max_workers}")
    print(f"🌐 Seed URLs: {len(crawler.get_seed_urls())}")
    print()
    
    # Confirm before starting
    confirm = input("Ready to start crawling? This will take time and bandwidth. (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Crawling cancelled.")
        return
    
    print("\n🚀 STARTING MASSIVE CRAWL...")
    print("=" * 60)
    
    try:
        # Run the crawler
        start_time = time.time()
        pages_crawled = crawler.run_massive_crawl()
        total_time = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("🎉 CRAWLING COMPLETED SUCCESSFULLY!")
        print(f"✅ Total pages crawled: {pages_crawled:,}")
        print(f"⏱️ Total time: {total_time/60:.1f} minutes")
        print(f"⚡ Average speed: {pages_crawled/total_time:.1f} pages/second")
        print()
        print("🔍 Your FOMO Search Engine is now ready with massive content!")
        print("🌐 You can now search for:")
        print("   • Programming tutorials and documentation")
        print("   • News articles and blog posts") 
        print("   • Educational content and courses")
        print("   • Technical references and wikis")
        print("   • And much more!")
        print()
        print("🚀 Start your search engine with: python3 app.py")
        
    except KeyboardInterrupt:
        print("\n⏹️ Crawling interrupted by user")
        print(f"✅ Partial crawl completed: {crawler.stats['crawled']:,} pages")
    except Exception as e:
        print(f"\n❌ Crawling error: {e}")
        print(f"✅ Partial crawl completed: {crawler.stats['crawled']:,} pages")

if __name__ == "__main__":
    main()