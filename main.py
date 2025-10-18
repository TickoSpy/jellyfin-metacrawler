#!/usr/bin/env python3
"""Main entry point for the Jellyfin metadata crawler."""

import sys
import argparse
from urllib.parse import urlparse, parse_qs
from src.config import Config
from src.crawler import MetadataCrawler


def extract_item_id(url_or_id: str) -> str:
    """Extract item ID from Jellyfin URL or return ID as-is.

    Args:
        url_or_id: Either a Jellyfin URL or a direct item ID

    Returns:
        Extracted or validated item ID
    """
    # If it's already just an ID (no URL scheme), return it
    if not url_or_id.startswith('http'):
        return url_or_id

    # Parse URL to extract item ID
    # Format: http://jellyfin.internal:8096/web/#/details?id=<ITEM_ID>&...
    parsed = urlparse(url_or_id)

    # Check for fragment (after #)
    if parsed.fragment:
        # Fragment might be like "/details?id=..."
        if '?' in parsed.fragment:
            fragment_query = parsed.fragment.split('?', 1)[1]
            params = parse_qs(fragment_query)
            if 'id' in params:
                return params['id'][0]

    # Check for regular query parameters
    params = parse_qs(parsed.query)
    if 'id' in params:
        return params['id'][0]

    raise ValueError(f"Could not extract item ID from: {url_or_id}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Jellyfin Metadata Crawler - Automatically improve metadata using Perplexity AI'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no actual updates)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        help='Confidence threshold for updates (0.0-1.0, default: 0.90)'
    )
    parser.add_argument(
        '--include-music',
        action='store_true',
        help='Include music items (by default music is excluded)'
    )
    parser.add_argument(
        '--update-images',
        action='store_true',
        help='Enable image updates (disabled by default due to IMDb URL restrictions)'
    )
    parser.add_argument(
        '--fix-item',
        type=str,
        metavar='URL_OR_ID',
        help='Fix a specific item by Jellyfin URL or item ID'
    )
    parser.add_argument(
        '--fix-series',
        type=str,
        metavar='URL_OR_ID',
        help='Fix all episodes in a series by Jellyfin URL or series ID'
    )

    args = parser.parse_args()

    # Override config with command line arguments
    if args.dry_run:
        Config.DRY_RUN = True

    if args.threshold:
        Config.MIN_CONFIDENCE_THRESHOLD = args.threshold

    if args.include_music:
        Config.EXCLUDE_MUSIC = False

    if args.update_images:
        Config.UPDATE_IMAGES = True

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease create a .env file based on .env.example and fill in your API keys.")
        sys.exit(1)

    # Create and run crawler
    crawler = MetadataCrawler(Config)

    try:
        # Check if we're fixing a single item or series
        if args.fix_item:
            item_id = extract_item_id(args.fix_item)
            print(f"Fixing single item: {item_id}")
            crawler.fix_single_item(item_id)
        elif args.fix_series:
            series_id = extract_item_id(args.fix_series)
            print(f"Fixing all episodes in series: {series_id}")
            crawler.fix_series_episodes(series_id)
        else:
            crawler.run()
    except KeyboardInterrupt:
        print("\nCrawler interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nCrawler failed with error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
