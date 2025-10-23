from app import app, db, Pages 

with app.app_context():
    pages = [
        {"url": "https://www.google.com", "title": "Google", "content": "Google Search Engine and Services"},
        {"url": "https://www.youtube.com", "title": "YouTube", "content": "YouTube Video Platform"},
        {"url": "https://www.facebook.com", "title": "Facebook", "content": "Facebook Social Media Platform"},
        {"url": "https://www.instagram.com", "title": "Instagram", "content": "Instagram Social Media Platform"},
        {"url": "https://www.twitter.com", "title": "Twitter", "content": "Twitter Social Media Platform"},
        {"url": "https://www.linkedin.com", "title": "LinkedIn", "content": "LinkedIn Professional Network"},
        {"url": "https://www.reddit.com", "title": "Reddit", "content": "Reddit Community Platform"},
        {"url": "https://www.wikipedia.org", "title": "Wikipedia", "content": "Free Online Encyclopedia"},
        {"url": "https://www.netflix.com", "title": "Netflix", "content": "Streaming Platform for Movies and TV Shows"},
        {"url": "https://www.amazon.com", "title": "Amazon", "content": "Online Shopping Platform"},
        {"url": "https://www.apple.com", "title": "Apple", "content": "Apple Products and Services"},
        {"url": "https://www.microsoft.com", "title": "Microsoft", "content": "Microsoft Software and Services"},
        {"url": "https://www.twitch.tv", "title": "Twitch", "content": "Live Streaming Platform for Gamers"},
        {"url": "https://www.spotify.com", "title": "Spotify", "content": "Music Streaming Platform"},
        {"url": "https://www.medium.com", "title": "Medium", "content": "Blogging Platform for Writers"},
        {"url": "https://www.stackoverflow.com", "title": "Stack Overflow", "content": "Programming Q&A Community"},
        {"url": "https://www.quora.com", "title": "Quora", "content": "Question & Answer Platform"},
        {"url": "https://www.tiktok.com", "title": "TikTok", "content": "Short Video Platform"},
        {"url": "https://www.pinterest.com", "title": "Pinterest", "content": "Image Sharing and Discovery Platform"},
        {"url": "https://www.salesforce.com", "title": "Salesforce", "content": "CRM and Cloud Software Platform"}
    ]

    for page in pages:
        new_page = Pages(url=page['url'], title=page['title'], content=page['content'])
        db.session.add(new_page)

    db.session.commit()
    print("Pages inserted successfully!")