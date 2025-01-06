#!/bin/bash
cd /var/www/reveal_gallery
source venv/bin/activate
cd src
python3 analyze_untagged.py 