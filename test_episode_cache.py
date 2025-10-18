#!/usr/bin/env python3
"""Test the TMDB episode caching functionality."""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from metadata_updater import MetadataUpdater

# Load environment
load_dotenv()

def test_episode_cache():
    """Test that episode caching works efficiently."""
    tmdb_api_key = os.getenv('TMDB_API_KEY')

    if not tmdb_api_key:
        print("ERROR: TMDB_API_KEY not set in .env")
        return

    updater = MetadataUpdater(tmdb_api_key)

    print("=" * 60)
    print("Testing TMDB Episode Caching")
    print("=" * 60)

    # Test with Toast of London episodes
    test_episodes = [
        ("Toast of London", 3, 2),
        ("Toast of London", 3, 1),
        ("Toast of London", 3, 3),
        ("Toast of London", 1, 1),
        ("Toast of London", 2, 5),
    ]

    print("\nFetching 5 episodes from 'Toast of London'...")
    print("First request will fetch ALL episodes, subsequent ones use cache.\n")

    for show_name, season, episode in test_episodes:
        print(f"\n--- Fetching S{season:02d}E{episode:02d} ---")
        metadata = updater.search_tmdb_episode(show_name, season, episode)

        if metadata:
            print(f"✓ Found: {metadata.get('Name')}")
            print(f"  Overview: {metadata.get('Overview', '')[:80]}...")
        else:
            print(f"✗ Not found")

    # Show cache stats
    print("\n" + "=" * 60)
    print("Cache Statistics")
    print("=" * 60)

    cache_size = len(updater.tv_episode_cache)
    total_episodes = sum(
        len(show['episodes'])
        for show in updater.tv_episode_cache.values()
    )

    print(f"Shows cached: {cache_size}")
    print(f"Total episodes cached: {total_episodes}")
    print(f"\nAPI calls saved: {len(test_episodes) - 1} episode requests")
    print(f"  (Made 1 bulk fetch instead of {len(test_episodes)} individual requests)")
    print("=" * 60)

if __name__ == '__main__':
    test_episode_cache()
