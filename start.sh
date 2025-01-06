#!/bin/bash
cd ../var/www/reveal_gallery/
source venv/bin/activate
exec python3 src/api.py
