"""TMDB metadata updater for fetching rich metadata from TheMovieDB.

This module provides the MetadataUpdater class, which handles all interactions
with The Movie Database (TMDB) API. TMDB is the primary source for metadata
enrichment, providing:

- Movie and TV show information
- High-quality poster, backdrop, and logo images
- Detailed cast, crew, and genre information
- Community ratings and vote counts
- Provider IDs (TMDB, IMDb)
- Runtime information for validation

The module implements an intelligent caching system for TV episodes to minimize
API calls and improve performance when processing entire series.

Key Features:
    - Smart result scoring for accurate matches
    - Episode caching for efficient TV series processing
    - Logo image support for enhanced UI
    - Runtime validation to prevent mismatches
    - Automatic type fallback (Movie ↔ TV)

Example:
    Basic TMDB lookup:

    >>> from src.metadata_updater import MetadataUpdater
    >>>
    >>> updater = MetadataUpdater(tmdb_api_key="your-api-key")
    >>> metadata = updater.search_tmdb("Inception", 2010, "movie")
    >>> print(metadata['Name'])
    'Inception'

Attributes:
    logger: Module-level logger for this updater.
"""

import requests
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MetadataUpdater:
    """Fetches and manages metadata from The Movie Database (TMDB).

    The MetadataUpdater is responsible for all TMDB API interactions, including:
    - Searching for movies and TV shows by title/year
    - Fetching detailed metadata by TMDB ID
    - Downloading and managing images (poster, backdrop, logo)
    - Caching TV episode data for efficient batch processing
    - Intelligent result scoring to select the best match

    The class implements sophisticated matching logic to handle:
    - Title variations and special characters (e.g., "Brüno" vs "Bruno")
    - Year matching with fuzzy tolerance
    - Popularity-based ranking
    - Runtime validation for movies

    Attributes:
        tmdb_api_key (str): API key for TMDB authentication.
        tmdb_base_url (str): Base URL for TMDB API v3.
        tmdb_image_base (str): Base URL for TMDB image CDN (original quality).
        tv_episode_cache (dict): Cache mapping show names to episode metadata.
                                 Structure: {show_name: {show_id, show_title, episodes}}
                                 where episodes is {(season, episode): metadata}

    Example:
        Initialize and search for a movie:

        >>> updater = MetadataUpdater("your-tmdb-api-key")
        >>> result = updater.search_tmdb("Galaxy Quest", 1999, "movie")
        >>> print(f"{result['Name']} ({result['ProductionYear']})")
        Galaxy Quest (1999)

        Fetch episode information with caching:

        >>> episode = updater.search_tmdb_episode("Police Squad!", 1, 4)
        >>> print(episode['Name'])
        Police Squad! - S01E04 - Revenge and Remorse
    """

    def __init__(self, tmdb_api_key: Optional[str] = None):
        """Initialize the TMDB metadata updater.

        Sets up the TMDB API client with authentication and initializes
        the episode caching system for efficient TV series processing.

        Args:
            tmdb_api_key: TMDB API v3 key. Get one free at:
                         https://www.themoviedb.org/settings/api
                         If None, TMDB functionality will be disabled.

        Note:
            The TMDB API is free for non-commercial use but requires attribution.
            See: https://www.themoviedb.org/documentation/api/terms-of-use
        """
        self.tmdb_api_key = tmdb_api_key
        self.tmdb_base_url = "https://api.themoviedb.org/3"
        self.tmdb_image_base = "https://image.tmdb.org/t/p/original"

        # Episode cache structure:
        # {
        #     "show name lower": {
        #         "show_id": 12345,
        #         "show_title": "Show Name",
        #         "episodes": {
        #             (1, 1): {metadata for S01E01},
        #             (1, 2): {metadata for S01E02},
        #             ...
        #         }
        #     }
        # }
        # This allows fetching all episodes once instead of per-episode API calls
        self.tv_episode_cache = {}

    def fetch_tmdb_metadata(self, tmdb_id: str, media_type: str) -> Optional[Dict]:
        """Fetch metadata from TMDB.

        Args:
            tmdb_id: TMDB ID
            media_type: Type of media (movie or tv)

        Returns:
            Metadata dictionary or None
        """
        if not self.tmdb_api_key:
            logger.warning("TMDB API key not configured")
            return None

        # Convert media type
        tmdb_type = 'movie' if media_type.lower() in ['movie'] else 'tv'
        url = f"{self.tmdb_base_url}/{tmdb_type}/{tmdb_id}"

        params = {
            'api_key': self.tmdb_api_key,
            'append_to_response': 'images,credits'
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            metadata = self._parse_tmdb_response(data, tmdb_type)
            logger.info(f"Fetched TMDB metadata for ID {tmdb_id}")
            return metadata

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching TMDB metadata: {e}")
            return None

    def search_tmdb(self, title: str, year: Optional[int], media_type: str) -> Optional[Dict]:
        """Search TMDB for a title.

        Args:
            title: Title to search for
            year: Optional year to narrow search
            media_type: Type of media (movie or tv)

        Returns:
            Metadata dictionary or None
        """
        if not self.tmdb_api_key:
            logger.warning("TMDB API key not configured")
            return None

        tmdb_type = 'movie' if media_type.lower() in ['movie'] else 'tv'
        url = f"{self.tmdb_base_url}/search/{tmdb_type}"

        params = {
            'api_key': self.tmdb_api_key,
            'query': title
        }

        if year:
            if tmdb_type == 'movie':
                params['year'] = year
            else:
                params['first_air_date_year'] = year

        try:
            logger.debug(f"TMDB search: {url} with query='{title}', year={year}, type={tmdb_type}")
            response = requests.get(url, params=params)

            logger.debug(f"TMDB response status: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            logger.debug(f"TMDB returned {len(results)} results for '{title}'")
            if results:
                logger.debug(f"First result: {results[0].get('name') or results[0].get('title')} (ID: {results[0].get('id')})")

            if not results:
                logger.info(f"No TMDB results found for {title}")
                return None

            # Don't just pick the first result - find the best match
            best_result = self._find_best_tmdb_match(results, title, year, tmdb_type)
            tmdb_id = best_result['id']

            if len(results) > 1:
                result_title = best_result.get('name') or best_result.get('title')
                logger.info(f"Selected best match: '{result_title}' (ID: {tmdb_id}) from {len(results)} results")

            return self.fetch_tmdb_metadata(str(tmdb_id), media_type)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching TMDB for '{title}': {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching TMDB for '{title}': {e}", exc_info=True)
            return None

    def _find_best_tmdb_match(self, results: list, query_title: str, query_year: Optional[int], media_type: str) -> Dict:
        """Find the best matching result from TMDB search results.

        Args:
            results: List of TMDB search results
            query_title: The title we searched for
            query_year: Optional year we searched for
            media_type: Type of media (movie or tv)

        Returns:
            The best matching result
        """
        from thefuzz import fuzz

        if not results:
            return None

        # If only one result, return it
        if len(results) == 1:
            return results[0]

        # Score each result
        scored_results = []
        for result in results:
            score = 0
            result_title = result.get('title') if media_type == 'movie' else result.get('name', '')
            result_year = None

            # Extract year from result
            if media_type == 'movie':
                release_date = result.get('release_date', '')
            else:
                release_date = result.get('first_air_date', '')

            if release_date:
                try:
                    result_year = int(release_date.split('-')[0])
                except (ValueError, IndexError):
                    pass

            # Title similarity (0-100)
            title_similarity = fuzz.ratio(query_title.lower(), result_title.lower())
            score += title_similarity

            # Exact title match bonus
            if query_title.lower() == result_title.lower():
                score += 50

            # Year match bonus (if year provided)
            if query_year and result_year:
                if query_year == result_year:
                    score += 100  # Exact year match
                elif abs(query_year - result_year) <= 1:
                    score += 50   # Close year match
                else:
                    score -= 50   # Wrong year penalty

            # Popularity factor (small influence)
            popularity = result.get('popularity', 0)
            score += min(popularity, 10)  # Cap at 10 points

            scored_results.append((score, result, result_title, result_year))

        # Sort by score descending
        scored_results.sort(reverse=True, key=lambda x: x[0])

        # Log top results for debugging
        logger.debug(f"TMDB match scores for '{query_title}' ({query_year or 'no year'}):")
        for score, result, title, year in scored_results[:3]:
            logger.debug(f"  Score {score:.1f}: '{title}' ({year}) - ID {result.get('id')}")

        # Return the best match
        return scored_results[0][1]

    def search_tmdb_episode(self, show_name: str, season: int, episode: int, year: Optional[int] = None) -> Optional[Dict]:
        """Search TMDB for a specific episode using cached show data.

        Args:
            show_name: Name of the TV show
            season: Season number
            episode: Episode number
            year: Optional year to narrow search

        Returns:
            Episode metadata dictionary or None
        """
        if not self.tmdb_api_key:
            logger.warning("TMDB API key not configured")
            return None

        # Normalize show name for cache key
        cache_key = show_name.lower().strip()

        # Check if we have this show cached
        if cache_key not in self.tv_episode_cache:
            logger.info(f"Fetching all episodes for show: {show_name}")
            if not self._fetch_and_cache_show_episodes(show_name, year):
                return None

        # Look up the episode in cache
        show_cache = self.tv_episode_cache[cache_key]
        episode_key = (season, episode)

        if episode_key in show_cache['episodes']:
            logger.debug(f"Found episode S{season:02d}E{episode:02d} in cache")
            return show_cache['episodes'][episode_key]
        else:
            logger.info(f"Episode S{season:02d}E{episode:02d} not found in TMDB for {show_name}")
            return None

    def _fetch_and_cache_show_episodes(self, show_name: str, year: Optional[int] = None) -> bool:
        """Fetch all episodes for a show and cache them.

        Args:
            show_name: Name of the TV show
            year: Optional year to narrow search

        Returns:
            True if successful, False otherwise
        """
        cache_key = show_name.lower().strip()

        # Search for the show
        url = f"{self.tmdb_base_url}/search/tv"
        params = {
            'api_key': self.tmdb_api_key,
            'query': show_name
        }

        if year:
            params['first_air_date_year'] = year

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get('results', [])
            if not results:
                logger.info(f"No TMDB results found for show: {show_name}")
                return False

            # Get the show details
            show_id = results[0]['id']
            show_title = results[0].get('name', show_name)
            logger.info(f"Found show: {show_title} (ID: {show_id})")

            # Fetch show details to get number of seasons
            show_url = f"{self.tmdb_base_url}/tv/{show_id}"
            show_response = requests.get(show_url, params={'api_key': self.tmdb_api_key})
            show_response.raise_for_status()
            show_data = show_response.json()

            num_seasons = show_data.get('number_of_seasons', 0)
            logger.info(f"Show has {num_seasons} seasons, fetching all episodes...")

            # Initialize cache for this show
            self.tv_episode_cache[cache_key] = {
                'show_id': show_id,
                'show_title': show_title,
                'episodes': {}
            }

            # Fetch all seasons
            for season_num in range(1, num_seasons + 1):
                self._fetch_and_cache_season(cache_key, show_id, show_title, season_num)

            total_episodes = len(self.tv_episode_cache[cache_key]['episodes'])
            logger.info(f"Cached {total_episodes} episodes for {show_title}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching show episodes: {e}")
            return False

    def _fetch_and_cache_season(self, cache_key: str, show_id: int, show_title: str, season_num: int):
        """Fetch all episodes for a season and add to cache.

        Args:
            cache_key: Cache key for the show
            show_id: TMDB show ID
            show_title: Show title
            season_num: Season number
        """
        season_url = f"{self.tmdb_base_url}/tv/{show_id}/season/{season_num}"
        params = {'api_key': self.tmdb_api_key}

        try:
            response = requests.get(season_url, params=params)
            response.raise_for_status()
            season_data = response.json()

            episodes = season_data.get('episodes', [])
            logger.debug(f"Season {season_num}: {len(episodes)} episodes")

            # Cache each episode
            for episode_data in episodes:
                episode_num = episode_data.get('episode_number')
                if episode_num:
                    metadata = self._parse_tmdb_episode_response(episode_data, show_title, show_id)
                    episode_key = (season_num, episode_num)
                    self.tv_episode_cache[cache_key]['episodes'][episode_key] = metadata

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.debug(f"Season {season_num} not found (might be specials)")
            else:
                logger.warning(f"Error fetching season {season_num}: {e}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching season {season_num}: {e}")

    def _parse_tmdb_episode_response(self, data: Dict, show_name: str, show_id: int) -> Dict:
        """Parse TMDB episode API response into our metadata format.

        Args:
            data: TMDB episode API response
            show_name: Name of the show
            show_id: TMDB show ID

        Returns:
            Parsed metadata dictionary
        """
        metadata = {}

        # Episode title
        episode_name = data.get('name', '')
        season_num = data.get('season_number', 0)
        episode_num = data.get('episode_number', 0)

        # Format: "Show Name - S01E01 - Episode Title"
        metadata['Name'] = f"{show_name} - S{season_num:02d}E{episode_num:02d} - {episode_name}"

        # Air date
        metadata['ProductionYear'] = self._extract_year(data.get('air_date', ''))

        # Overview
        metadata['Overview'] = data.get('overview', '')

        # Provider IDs
        metadata['ProviderIds'] = {
            'Tmdb': str(show_id)  # Use show ID since episodes don't have separate TMDB IDs
        }

        # Episode-specific fields
        metadata['IndexNumber'] = episode_num
        metadata['ParentIndexNumber'] = season_num

        # Still image (episode screenshot)
        still_path = data.get('still_path')
        if still_path:
            metadata['PosterUrl'] = f"{self.tmdb_image_base}{still_path}"

        # Rating
        if data.get('vote_average'):
            metadata['CommunityRating'] = data['vote_average']

        return metadata

    def _parse_tmdb_response(self, data: Dict, media_type: str) -> Dict:
        """Parse TMDB API response into our metadata format.

        Args:
            data: TMDB API response
            media_type: Type of media (movie or tv)

        Returns:
            Parsed metadata dictionary
        """
        metadata = {}

        # Title
        if media_type == 'movie':
            metadata['Name'] = data.get('title', '')
            metadata['ProductionYear'] = self._extract_year(data.get('release_date', ''))
        else:
            metadata['Name'] = data.get('name', '')
            metadata['ProductionYear'] = self._extract_year(data.get('first_air_date', ''))

        # Overview
        metadata['Overview'] = data.get('overview', '')

        # Genres
        genres = [g['name'] for g in data.get('genres', [])]
        metadata['Genres'] = genres

        # Provider IDs
        metadata['ProviderIds'] = {}
        metadata['ProviderIds']['Tmdb'] = str(data.get('id', ''))

        # IMDb ID if available
        if data.get('imdb_id'):
            metadata['ProviderIds']['Imdb'] = data['imdb_id']

        # Images
        poster_path = data.get('poster_path')
        if poster_path:
            metadata['PosterUrl'] = f"{self.tmdb_image_base}{poster_path}"

        backdrop_path = data.get('backdrop_path')
        if backdrop_path:
            metadata['BackdropUrl'] = f"{self.tmdb_image_base}{backdrop_path}"

        # Logo image (from appended images response)
        images_data = data.get('images', {})
        logos = images_data.get('logos', [])
        if logos:
            # Get the first English logo, or first logo if no English available
            english_logos = [logo for logo in logos if logo.get('iso_639_1') == 'en']
            logo_to_use = english_logos[0] if english_logos else logos[0]
            logo_path = logo_to_use.get('file_path')
            if logo_path:
                metadata['LogoUrl'] = f"{self.tmdb_image_base}{logo_path}"

        # Ratings
        if data.get('vote_average'):
            metadata['CommunityRating'] = data['vote_average']

        # Runtime (in minutes)
        if data.get('runtime'):
            metadata['Runtime'] = data['runtime']

        return metadata

    def _extract_year(self, date_string: str) -> Optional[int]:
        """Extract year from date string.

        Args:
            date_string: Date string (YYYY-MM-DD format)

        Returns:
            Year as integer or None
        """
        if not date_string:
            return None

        try:
            return int(date_string.split('-')[0])
        except (ValueError, IndexError):
            return None

    def apply_metadata_to_item(self, current_item: Dict, new_metadata: Dict) -> Dict:
        """Merge new metadata into current item.

        Args:
            current_item: Current Jellyfin item
            new_metadata: New metadata to apply

        Returns:
            Updated item dictionary
        """
        updated_item = current_item.copy()

        # Update basic fields
        if new_metadata.get('Name'):
            updated_item['Name'] = new_metadata['Name']

        if new_metadata.get('ProductionYear'):
            updated_item['ProductionYear'] = new_metadata['ProductionYear']

        if new_metadata.get('Overview'):
            updated_item['Overview'] = new_metadata['Overview']

        if new_metadata.get('Genres'):
            updated_item['Genres'] = new_metadata['Genres']

        # Update provider IDs
        if new_metadata.get('ProviderIds'):
            if 'ProviderIds' not in updated_item:
                updated_item['ProviderIds'] = {}
            updated_item['ProviderIds'].update(new_metadata['ProviderIds'])

        # Community rating
        if new_metadata.get('CommunityRating'):
            updated_item['CommunityRating'] = new_metadata['CommunityRating']

        return updated_item

    def get_image_urls(self, metadata: Dict) -> Dict[str, str]:
        """Extract image URLs from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Dictionary with image types and URLs
        """
        images = {}

        if metadata.get('PosterUrl'):
            images['Primary'] = metadata['PosterUrl']

        if metadata.get('BackdropUrl'):
            images['Backdrop'] = metadata['BackdropUrl']

        if metadata.get('LogoUrl'):
            images['Logo'] = metadata['LogoUrl']

        if metadata.get('poster_url'):  # From Perplexity
            images['Primary'] = metadata['poster_url']

        if metadata.get('backdrop_url'):  # From Perplexity
            images['Backdrop'] = metadata['backdrop_url']

        if metadata.get('logo_url'):  # From Perplexity
            images['Logo'] = metadata['logo_url']

        return images
