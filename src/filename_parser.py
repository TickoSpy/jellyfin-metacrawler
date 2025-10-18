"""Intelligent filename parser using GuessIt library."""

import logging
import os
from typing import Dict, Optional
from guessit import guessit

logger = logging.getLogger(__name__)


class FilenameParser:
    """Parser for extracting metadata from media filenames."""

    def __init__(self):
        """Initialize the filename parser."""
        pass

    def parse(self, filename: str, item_type: Optional[str] = None) -> Dict:
        """Parse a filename to extract media information.

        Args:
            filename: The filename to parse (can include path)
            item_type: Optional hint about the item type (Movie, Episode, Series)

        Returns:
            Dictionary with parsed information including:
                - title: Media title
                - year: Production year (if found)
                - season: Season number (for TV shows)
                - episode: Episode number (for TV shows)
                - episode_title: Episode title (if found)
                - type: Detected media type (movie, episode)
                - clean_title: Cleaned title suitable for searches
                - raw_guess: Raw guessit output for debugging
        """
        if not filename:
            return {}

        # Extract just the filename if it's a full path
        basename = os.path.basename(filename)

        try:
            # Use guessit to parse the filename
            guess = guessit(basename)

            parsed = {
                'raw_guess': dict(guess)
            }

            # Extract title
            if 'title' in guess:
                parsed['title'] = str(guess['title'])
                parsed['clean_title'] = str(guess['title'])

            # Extract alternative title if present
            if 'alternative_title' in guess:
                parsed['alternative_title'] = str(guess['alternative_title'])

            # Extract year
            if 'year' in guess:
                parsed['year'] = int(guess['year'])

            # Extract season and episode info
            if 'season' in guess:
                # Handle both single season and list of seasons
                season = guess['season']
                if isinstance(season, list):
                    parsed['season'] = int(season[0])
                else:
                    parsed['season'] = int(season)

            if 'episode' in guess:
                # Handle both single episode and list of episodes
                episode = guess['episode']
                if isinstance(episode, list):
                    parsed['episode'] = int(episode[0])
                else:
                    parsed['episode'] = int(episode)

            if 'episode_title' in guess:
                parsed['episode_title'] = str(guess['episode_title'])

            # Detect media type
            if 'type' in guess:
                parsed['type'] = str(guess['type'])
            elif 'season' in parsed or 'episode' in parsed:
                parsed['type'] = 'episode'
            else:
                parsed['type'] = 'movie'

            # Extract additional metadata
            if 'screen_size' in guess:
                parsed['resolution'] = str(guess['screen_size'])

            if 'source' in guess:
                parsed['source'] = str(guess['source'])

            if 'video_codec' in guess:
                parsed['video_codec'] = str(guess['video_codec'])

            if 'release_group' in guess:
                parsed['release_group'] = str(guess['release_group'])

            logger.debug(f"Parsed '{basename}' -> {parsed}")
            return parsed

        except Exception as e:
            logger.error(f"Error parsing filename '{filename}': {e}", exc_info=True)
            return {}

    def get_search_query(self, filename: str, item_type: Optional[str] = None) -> str:
        """Get a clean search query from a filename.

        Args:
            filename: The filename to parse
            item_type: Optional hint about the item type

        Returns:
            Clean search query string
        """
        parsed = self.parse(filename, item_type)

        if not parsed:
            # Fallback to basic cleaning if parsing fails
            return self._basic_clean(filename)

        # Build search query based on parsed info
        parts = []

        # Add title
        if 'title' in parsed:
            parts.append(parsed['title'])

        # Add year for movies
        if parsed.get('type') == 'movie' and 'year' in parsed:
            parts.append(str(parsed['year']))

        # Add season/episode for TV shows
        if 'season' in parsed and 'episode' in parsed:
            parts.append(f"S{parsed['season']:02d}E{parsed['episode']:02d}")
        elif 'season' in parsed:
            parts.append(f"Season {parsed['season']}")

        # Add episode title if available
        if 'episode_title' in parsed:
            parts.append(parsed['episode_title'])

        return ' '.join(parts) if parts else self._basic_clean(filename)

    def extract_show_name(self, path: str) -> str:
        """Extract show name from a file path.

        For TV shows, the show name is typically the parent directory name.

        Args:
            path: Full file path

        Returns:
            Extracted show name
        """
        # Determine the directory to check
        if os.path.isfile(path) or '.' in os.path.basename(path):
            # It's a file (has extension like .mkv)
            # Get the parent directory
            current_dir = os.path.dirname(path)
        else:
            # It's a directory (no extension)
            current_dir = path

        folder_name = os.path.basename(current_dir)

        # Check if this is a "Season X" folder - if so, go up one more level
        if folder_name.lower().startswith('season'):
            # This is a season folder, go up one more level to get the show name
            parent_dir = os.path.dirname(current_dir)
            folder_name = os.path.basename(parent_dir)

        # Parse the folder name to extract clean show name
        parsed = self.parse(folder_name)

        if 'title' in parsed:
            return parsed['title']

        # Fallback to basic cleaning
        return self._basic_clean(folder_name)

    def _basic_clean(self, filename: str) -> str:
        """Basic filename cleaning as fallback.

        Args:
            filename: Filename to clean

        Returns:
            Cleaned filename
        """
        import re

        # Remove extension
        name = os.path.splitext(filename)[0]

        # Replace separators with spaces
        name = name.replace('.', ' ').replace('_', ' ').replace('-', ' ')

        # Remove extra whitespace
        name = ' '.join(name.split())

        return name.strip()
