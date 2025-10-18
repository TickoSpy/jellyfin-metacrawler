#!/usr/bin/env python3
"""Test TMDB search for Toast of London specifically."""

import os
import sys
import logging
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from metadata_updater import MetadataUpdater

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Load environment
load_dotenv()

def test_toast_search():
    """Test searching for Toast of London."""
    tmdb_api_key = os.getenv('TMDB_API_KEY')

    if not tmdb_api_key:
        print("ERROR: TMDB_API_KEY not set in .env")
        return

    updater = MetadataUpdater(tmdb_api_key)

    print("\n" + "=" * 60)
    print("Testing TMDB Search for 'Toast of London' (Series)")
    print("=" * 60 + "\n")

    # Test as Series (tv)
    print("Searching as Series (media_type='tv')...")
    result = updater.search_tmdb("Toast of London", None, "tv")

    if result:
        print(f"\n✓ FOUND!")
        print(f"Name: {result.get('Name')}")
        print(f"Year: {result.get('ProductionYear')}")
        print(f"Overview: {result.get('Overview', '')[:100]}...")
        print(f"TMDB ID: {result.get('ProviderIds', {}).get('Tmdb')}")
    else:
        print("\n✗ NOT FOUND")

if __name__ == '__main__':
    test_toast_search()
