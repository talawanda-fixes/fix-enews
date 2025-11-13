#!/usr/bin/env python3
"""
Generate index.html and viewer.html for RSS feeds based on schools.json
"""

import json
import shutil
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def generate_pages():
    """Generate index.html and viewer.html from templates"""
    # Load schools
    schools_file = Path('schools.json')
    with open(schools_file, 'r', encoding='utf-8') as f:
        schools = json.load(f)

    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(loader=FileSystemLoader(template_dir))

    # Create output directory
    output_dir = Path('output')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate index.html
    index_template = env.get_template('index.html')
    index_html = index_template.render(schools=schools)
    index_file = output_dir / 'index.html'
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_html)
    print(f"Generated {index_file}")

    # Generate viewer.html
    viewer_template = env.get_template('viewer.html')
    viewer_html = viewer_template.render(schools=schools)
    viewer_file = output_dir / 'viewer.html'
    with open(viewer_file, 'w', encoding='utf-8') as f:
        f.write(viewer_html)
    print(f"Generated {viewer_file}")

    # Copy schools.json to output directory for viewer to fetch
    schools_output = output_dir / 'schools.json'
    shutil.copy(schools_file, schools_output)
    print(f"Copied {schools_output}")

if __name__ == '__main__':
    generate_pages()
