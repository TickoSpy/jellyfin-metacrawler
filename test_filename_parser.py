#!/usr/bin/env python3
"""Test script for the filename parser."""

from src.filename_parser import FilenameParser


def test_parser():
    """Test the filename parser with various examples."""
    parser = FilenameParser()

    # Test cases
    test_filenames = [
        # Movies
        "The.Matrix.1999.1080p.BluRay.x264-YIFY.mkv",
        "Inception (2010) [1080p] BluRay.mp4",
        "The.Shawshank.Redemption.1994.720p.mkv",

        # TV Shows
        "Game.of.Thrones.S01E01.Winter.Is.Coming.1080p.WEB-DL.mkv",
        "Breaking.Bad.S05E16.Felina.HDTV.x264.mp4",
        "The.Office.US.S03E12.Back.From.Vacation.720p.BluRay.mkv",
        "Toast of London S01E01.mkv",

        # Anime
        "Attack.on.Titan.S02E06.1080p.BluRay.x265-HEVC.mkv",

        # Edge cases
        "some-random-video-file.mkv",
        "Movie Title 2023.mp4",
    ]

    print("=" * 80)
    print("FILENAME PARSER TEST")
    print("=" * 80)

    for filename in test_filenames:
        print(f"\n\nFilename: {filename}")
        print("-" * 80)

        parsed = parser.parse(filename)

        if parsed:
            print(f"Title:           {parsed.get('title', 'N/A')}")
            print(f"Clean Title:     {parsed.get('clean_title', 'N/A')}")
            print(f"Year:            {parsed.get('year', 'N/A')}")
            print(f"Type:            {parsed.get('type', 'N/A')}")

            if 'season' in parsed:
                print(f"Season:          {parsed['season']}")
            if 'episode' in parsed:
                print(f"Episode:         {parsed['episode']}")
            if 'episode_title' in parsed:
                print(f"Episode Title:   {parsed['episode_title']}")

            if 'resolution' in parsed:
                print(f"Resolution:      {parsed['resolution']}")
            if 'source' in parsed:
                print(f"Source:          {parsed['source']}")
            if 'video_codec' in parsed:
                print(f"Video Codec:     {parsed['video_codec']}")
            if 'release_group' in parsed:
                print(f"Release Group:   {parsed['release_group']}")

            # Test search query generation
            search_query = parser.get_search_query(filename)
            print(f"\nSearch Query:    {search_query}")
        else:
            print("Failed to parse filename")

    # Test path extraction
    print("\n\n" + "=" * 80)
    print("PATH EXTRACTION TEST")
    print("=" * 80)

    test_paths = [
        "/media/TV Shows/Game of Thrones/Season 1/Game.of.Thrones.S01E01.mkv",
        "/media/TV Shows/Breaking Bad (2008)/Breaking.Bad.S05E16.mkv",
        "/media/Movies/The Matrix (1999)/The.Matrix.1999.1080p.mkv",
        "/media/TV Shows/Toast of London",
    ]

    for path in test_paths:
        print(f"\n\nPath: {path}")
        print("-" * 80)
        show_name = parser.extract_show_name(path)
        print(f"Extracted Show Name: {show_name}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_parser()
