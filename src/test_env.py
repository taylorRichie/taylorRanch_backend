#!/usr/bin/env python3
import sys
import os

print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")
print("\nTesting imports:")

try:
    from playwright.async_api import async_playwright
    print("✓ playwright")
except ImportError as e:
    print(f"✗ playwright: {e}")

try:
    import psycopg2
    print("✓ psycopg2")
except ImportError as e:
    print(f"✗ psycopg2: {e}")

try:
    import boto3
    print("✓ boto3")
except ImportError as e:
    print(f"✗ boto3: {e}")

try:
    from dotenv import load_dotenv
    print("✓ python-dotenv")
except ImportError as e:
    print(f"✗ python-dotenv: {e}")

print("\nEnvironment variables:")
print(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'Not set')}")
print(f"PATH: {os.getenv('PATH', 'Not set')}") 