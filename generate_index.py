#!/usr/bin/env python3
"""
Generate index.html for RSS feeds based on schools.json
"""

import json
from pathlib import Path

def generate_index():
    """Generate index.html from schools.json"""
    # Load schools
    with open('schools.json', 'r', encoding='utf-8') as f:
        schools = json.load(f)
    
    # Generate HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Talawanda School District - RSS Feeds</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }
        .school {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .school h2 {
            color: #0066cc;
            margin-top: 0;
        }
        .school p {
            color: #666;
            margin: 10px 0;
        }
        .links {
            margin-top: 15px;
        }
        .links a {
            display: inline-block;
            margin-right: 15px;
            padding: 8px 16px;
            background-color: #0066cc;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }
        .links a:hover {
            background-color: #0052a3;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 14px;
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>Talawanda School District - RSS Feeds</h1>
    <p>Subscribe to RSS feeds for news and announcements from Talawanda schools.</p>
"""
    
    # Add each school
    for school in schools:
        slug = school['slug']
        name = school['name']
        description = school.get('description', '')
        
        html += f"""
    <div class="school">
        <h2>{name}</h2>
        <p>{description}</p>
        <div class="links">
            <a href="{slug}-feed.rss">RSS Feed</a>
            <a href="{slug}-items.json">JSON Data</a>
        </div>
    </div>
"""
    
    html += """
    <div class="footer">
        <p>RSS feeds are updated every 6 hours.</p>
        <p>Powered by <a href="https://claude.com/claude-code" style="color: #0066cc;">Claude Code</a></p>
    </div>
</body>
</html>
"""
    
    # Write to output directory
    output_dir = Path('output')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'index.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Generated {output_file}")

if __name__ == '__main__':
    generate_index()
