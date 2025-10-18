#!/usr/bin/env python3
"""Diagnostic script to test Jellyfin and Perplexity API connections."""

import sys
from src.config import Config
from src.jellyfin_client import JellyfinClient
from src.perplexity_client import PerplexityClient
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_jellyfin_connection():
    """Test Jellyfin API connection."""
    print("\n" + "=" * 60)
    print("TESTING JELLYFIN CONNECTION")
    print("=" * 60)

    try:
        client = JellyfinClient(Config.JELLYFIN_URL, Config.JELLYFIN_API_KEY)
        print(f"Jellyfin URL: {Config.JELLYFIN_URL}")
        print(f"API Key: {Config.JELLYFIN_API_KEY[:10]}..." if Config.JELLYFIN_API_KEY else "API Key: NOT SET")

        print("\nFetching items...")
        items = client.get_all_items(exclude_music=True)
        print(f"✓ Successfully fetched {len(items)} items")

        if items:
            print("\nSample item:")
            item = items[0]
            print(f"  ID: {item.get('Id')}")
            print(f"  Name: {item.get('Name')}")
            print(f"  Type: {item.get('Type')}")
            print(f"  Path: {item.get('Path', 'N/A')}")

            # Try to get item by ID
            print(f"\nTesting get_item_by_id with ID: {item.get('Id')}")
            retrieved_item = client.get_item_by_id(item.get('Id'))
            if retrieved_item:
                print("✓ Successfully retrieved item by ID")
            else:
                print("✗ Failed to retrieve item by ID")

        return True

    except Exception as e:
        print(f"✗ Jellyfin connection failed: {e}")
        logger.error("Jellyfin connection error", exc_info=True)
        return False


def test_perplexity_connection():
    """Test Perplexity API connection."""
    print("\n" + "=" * 60)
    print("TESTING PERPLEXITY CONNECTION")
    print("=" * 60)

    try:
        client = PerplexityClient(Config.PERPLEXITY_API_KEY, Config.PERPLEXITY_USE_PRO)
        print(f"Perplexity API Key: {Config.PERPLEXITY_API_KEY[:10]}..." if Config.PERPLEXITY_API_KEY else "API Key: NOT SET")
        print(f"Model: {client.model}")

        print("\nTesting media identification with sample filename...")
        test_filename = "The.Matrix.1999.1080p.BluRay.x264.mkv"
        print(f"Sample filename: {test_filename}")

        metadata = client.identify_media(test_filename, {}, "Movie")

        if metadata:
            print("✓ Successfully identified media")
            print(f"\nIdentified metadata:")
            print(f"  Title: {metadata.get('title', 'N/A')}")
            print(f"  Year: {metadata.get('year', 'N/A')}")
            print(f"  Confidence: {metadata.get('confidence', 'N/A')}")
            print(f"  IMDb ID: {metadata.get('imdb_id', 'N/A')}")
            print(f"  TMDB ID: {metadata.get('tmdb_id', 'N/A')}")
            return True
        else:
            print("✗ Failed to identify media")
            return False

    except Exception as e:
        print(f"✗ Perplexity connection failed: {e}")
        logger.error("Perplexity connection error", exc_info=True)
        return False


def main():
    """Run all diagnostic tests."""
    print("\n" + "=" * 60)
    print("JELLYFIN METADATA CRAWLER - DIAGNOSTICS")
    print("=" * 60)

    # Validate configuration
    try:
        Config.validate()
        print("✓ Configuration validated")
    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nPlease ensure your .env file is properly configured.")
        sys.exit(1)

    # Test Jellyfin
    jellyfin_ok = test_jellyfin_connection()

    # Test Perplexity
    perplexity_ok = test_perplexity_connection()

    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"Jellyfin API: {'✓ WORKING' if jellyfin_ok else '✗ FAILED'}")
    print(f"Perplexity API: {'✓ WORKING' if perplexity_ok else '✗ FAILED'}")
    print("=" * 60)

    if jellyfin_ok and perplexity_ok:
        print("\n✓ All systems operational!")
        print("You can now run: python main.py --dry-run")
        sys.exit(0)
    else:
        print("\n✗ Some systems are not working properly.")
        print("Please check the error messages above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
