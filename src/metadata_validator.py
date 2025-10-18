"""Metadata validator using TMDB and file analysis."""

import os
import re
from typing import Dict, Optional, Tuple
from thefuzz import fuzz
import logging
from .filename_parser import FilenameParser

logger = logging.getLogger(__name__)


class MetadataValidator:
    """Validates metadata against TMDB and file information."""

    def __init__(self, tmdb_client):
        """Initialize validator.

        Args:
            tmdb_client: TMDB metadata updater client
        """
        self.tmdb = tmdb_client
        self.filename_parser = FilenameParser()

    def _check_runtime_match(self, file_runtime_ticks: Optional[int], metadata_runtime: Optional[int]) -> Tuple[bool, float]:
        """Check if file runtime matches metadata runtime.

        Args:
            file_runtime_ticks: File runtime in ticks (10,000,000 ticks = 1 second)
            metadata_runtime: Expected runtime in minutes from TMDB/Perplexity

        Returns:
            Tuple of (matches, confidence_adjustment)
        """
        if not file_runtime_ticks or not metadata_runtime:
            # Can't validate without both runtimes
            return True, 0.0

        # Convert ticks to minutes
        file_runtime_minutes = file_runtime_ticks / 10000000 / 60

        # Allow 10% deviation or 10 minutes, whichever is larger
        max_deviation = max(metadata_runtime * 0.1, 10)
        deviation = abs(file_runtime_minutes - metadata_runtime)

        logger.debug(f"Runtime check: file={file_runtime_minutes:.1f}min, metadata={metadata_runtime}min, deviation={deviation:.1f}min")

        if deviation <= max_deviation:
            # Good match
            return True, 0.1  # Small confidence boost
        elif deviation <= max_deviation * 2:
            # Moderate mismatch - warn but allow
            logger.warning(f"Runtime mismatch: file is {file_runtime_minutes:.1f}min but metadata says {metadata_runtime}min")
            return True, -0.2  # Confidence penalty
        else:
            # Large mismatch - likely wrong movie
            logger.error(f"LARGE runtime mismatch: file is {file_runtime_minutes:.1f}min but metadata says {metadata_runtime}min - rejecting match")
            return False, -0.5

    def validate_with_tmdb(self, item: Dict, path: str, item_type: str) -> Tuple[float, Optional[Dict]]:
        """Validate current metadata against TMDB.

        Args:
            item: Jellyfin item
            path: File path (the source of truth)
            item_type: Type of media

        Returns:
            Tuple of (confidence_score, tmdb_metadata)
        """
        current_name = item.get('Name', '')
        current_year = item.get('ProductionYear')

        if not path and not current_name:
            logger.debug("No path or name to validate")
            return 0.0, None

        # Parse the path intelligently based on item type
        search_name = None
        season_num = None
        episode_num = None
        filename_year = None

        logger.debug(f"Validating item_type: {item_type}")

        if item_type == 'Series':
            # For Series, the path IS the series folder
            # Just parse the folder name itself
            folder_name = os.path.basename(path)
            logger.debug(f"Series path: '{path}' -> folder_name: '{folder_name}'")

            # Check if folder name looks like a generic library folder (e.g., "Serien", "TV Shows", "Series")
            generic_folders = ['serien', 'series', 'tv shows', 'tv', 'shows', 'television']
            if folder_name.lower() in generic_folders:
                logger.warning(f"Folder name '{folder_name}' looks like a library folder, not a series. Using current name instead.")
                search_name = current_name
                filename_year = current_year
            else:
                parsed = self.filename_parser.parse(folder_name)
                if parsed and 'title' in parsed:
                    search_name = parsed['title']
                    filename_year = parsed.get('year')
                    logger.debug(f"Parsed series from folder: '{search_name}'" + (f" ({filename_year})" if filename_year else ""))
                else:
                    # Fallback to current name
                    search_name = current_name or folder_name
                    logger.debug(f"Using folder name as series name: '{search_name}'")
            # Try to extract year from path if not already found
            if not filename_year:
                filename_year = self._extract_year_from_filename(path)

        elif item_type == 'Episode':
            # For Episodes, parse the filename to get show, season, episode
            filename = os.path.basename(path)
            parsed = self._parse_episode_filename(filename)
            if parsed and 'show_name' in parsed:
                search_name = parsed['show_name']
                season_num = parsed.get('season')
                episode_num = parsed.get('episode')
                logger.debug(f"Parsed from filename: '{search_name}'" + (f" S{season_num:02d}E{episode_num:02d}" if season_num and episode_num else ""))
            else:
                # Fallback: extract show name from folder structure
                search_name = self.filename_parser.extract_show_name(path)
                logger.debug(f"Extracted show name from path: '{search_name}'")

        elif item_type == 'Movie':
            # For Movies, parse the filename
            filename = os.path.basename(path)
            parsed = self.filename_parser.parse(filename)
            if parsed and 'title' in parsed:
                search_name = parsed['title']
                filename_year = parsed.get('year')
                logger.debug(f"Parsed movie from filename: '{search_name}'" + (f" ({filename_year})" if filename_year else ""))
            else:
                # Fallback to current name
                search_name = current_name
                logger.debug(f"Using current name: '{search_name}'")

        else:
            # For other types, try to parse as a general file
            filename = os.path.basename(path) if path else ""
            parsed = self.filename_parser.parse(filename)
            if parsed and 'title' in parsed:
                search_name = parsed['title']
                filename_year = parsed.get('year')
            else:
                search_name = current_name or filename

        # Fallback if we still don't have a search name
        if not search_name:
            search_name = current_name if current_name else os.path.basename(path)
            logger.debug(f"Fallback search name: '{search_name}'")

        # Convert item_type to TMDB media type
        if item_type == 'Movie':
            media_type = 'movie'
        elif item_type in ['Series', 'Episode']:
            media_type = 'tv'
        else:
            media_type = 'movie'

        # Search TMDB using filename-based search term
        logger.info(f"Validating '{search_name}' (from filename) against TMDB...")
        tmdb_metadata = None

        try:
            # For episodes with season/episode info, fetch specific episode metadata
            if item_type == 'Episode' and season_num is not None and episode_num is not None:
                tmdb_metadata = self.tmdb.search_tmdb_episode(search_name, season_num, episode_num)
            else:
                # For movies, series, or episodes without season/episode info
                tmdb_metadata = self.tmdb.search_tmdb(search_name, filename_year, media_type)

                # If not found, try the opposite type (files can be miscategorized)
                if not tmdb_metadata:
                    if media_type == 'tv':
                        logger.info("Not found as TV, trying as movie...")
                        tmdb_metadata = self.tmdb.search_tmdb(search_name, filename_year, 'movie')
                    elif media_type == 'movie':
                        logger.info("Not found as movie, trying as TV...")
                        tmdb_metadata = self.tmdb.search_tmdb(search_name, filename_year, 'tv')

            if not tmdb_metadata:
                logger.info("Not found in TMDB")
                return 0.3, None

            # Compare TMDB result with FILENAME (not current_name)
            tmdb_name = tmdb_metadata.get('Name', '')
            tmdb_year = tmdb_metadata.get('ProductionYear')

            # Calculate confidence based on matches
            confidence_scores = []

            # Name match - for episodes, extract just the show name from TMDB result
            tmdb_name_for_comparison = tmdb_name
            if item_type == 'Episode' and season_num is not None and episode_num is not None:
                # TMDB episode names are like "Show Name - S01E01 - Episode Title"
                # Extract just the show name for comparison
                tmdb_show_name = self._extract_show_name_from_episode(tmdb_name)
                tmdb_name_for_comparison = tmdb_show_name
                logger.debug(f"Extracted show name from TMDB episode: '{tmdb_show_name}'")

            # Name match - compare TMDB result with the SEARCH NAME (from filename), not current metadata
            name_similarity = fuzz.ratio(search_name.lower(), tmdb_name_for_comparison.lower()) / 100.0

            # For episodes with season/episode info, name match is almost everything
            # Since we found the exact episode, we can be very confident
            if item_type == 'Episode':
                if season_num is not None and episode_num is not None:
                    # Episode identification is primarily about show name + S/E numbers
                    # If we found the episode in cache/TMDB, it's correct
                    confidence_scores.append(name_similarity * 0.9)  # 90% weight on name
                    # Year is less important for episodes
                    year_match = 0.8  # Default good match for episodes
                    if filename_year and tmdb_year:
                        if filename_year == tmdb_year:
                            year_match = 1.0
                        elif abs(filename_year - tmdb_year) <= 1:
                            year_match = 0.9
                    confidence_scores.append(year_match * 0.1)  # Only 10% weight
                else:
                    # Episode without season number - treat like a series
                    confidence_scores.append(name_similarity * 0.8)  # 80% weight on name
                    year_to_compare = filename_year if filename_year else current_year
                    year_match = 0.0
                    if year_to_compare and tmdb_year:
                        if year_to_compare == tmdb_year:
                            year_match = 1.0
                        elif abs(year_to_compare - tmdb_year) <= 2:
                            year_match = 0.8
                        else:
                            year_match = 0.3
                    elif year_to_compare or tmdb_year:
                        year_match = 0.6
                    else:
                        year_match = 0.8  # Both missing is common for TV
                    confidence_scores.append(year_match * 0.2)  # Only 20% weight
            elif item_type == 'Series':
                # For Series, name is more important than year
                # TV series often don't have year in folder name
                confidence_scores.append(name_similarity * 0.8)  # 80% weight on name

                # Year match - prefer filename year over current year
                year_to_compare = filename_year if filename_year else current_year
                year_match = 0.0
                if year_to_compare and tmdb_year:
                    if year_to_compare == tmdb_year:
                        year_match = 1.0
                    elif abs(year_to_compare - tmdb_year) <= 2:  # More lenient for series
                        year_match = 0.8
                    else:
                        year_match = 0.3
                elif year_to_compare or tmdb_year:
                    year_match = 0.6  # More neutral
                else:
                    year_match = 0.8  # Both missing is more common/acceptable for series
                confidence_scores.append(year_match * 0.2)  # Only 20% weight
            else:
                # For movies, year is more important
                confidence_scores.append(name_similarity * 0.6)  # 60% weight

                # Year match - prefer filename year over current year
                year_to_compare = filename_year if filename_year else current_year
                year_match = 0.0
                if year_to_compare and tmdb_year:
                    if year_to_compare == tmdb_year:
                        year_match = 1.0
                    elif abs(year_to_compare - tmdb_year) <= 1:
                        year_match = 0.8
                    else:
                        year_match = 0.2
                elif year_to_compare or tmdb_year:
                    year_match = 0.5
                else:
                    year_match = 0.7  # Both missing, neutral
                confidence_scores.append(year_match * 0.4)  # 40% weight

            total_confidence = sum(confidence_scores)

            # Runtime validation for movies
            if item_type == 'Movie':
                file_runtime = item.get('RunTimeTicks')
                tmdb_runtime = tmdb_metadata.get('Runtime')  # In minutes

                runtime_matches, runtime_adjustment = self._check_runtime_match(file_runtime, tmdb_runtime)

                if not runtime_matches:
                    # Large runtime mismatch - reject this match
                    logger.error(f"Rejecting TMDB match due to large runtime mismatch")
                    return 0.3, None

                # Apply confidence adjustment based on runtime match quality
                total_confidence += runtime_adjustment
                total_confidence = max(0.0, min(1.0, total_confidence))  # Clamp to 0-1

            logger.info(f"TMDB validation confidence: {total_confidence:.2f}")
            logger.info(f"  Filename '{search_name}' vs TMDB '{tmdb_name_for_comparison}': {name_similarity:.2f}")
            if item_type == 'Episode' and season_num is not None and episode_num is not None:
                logger.info(f"  Episode match confirmed (S{season_num:02d}E{episode_num:02d})")
            elif item_type == 'Series':
                logger.info(f"  Series year match (filename:{filename_year} vs tmdb:{tmdb_year}): {year_match:.2f}")
            else:
                logger.info(f"  Year match (filename:{filename_year} vs tmdb:{tmdb_year}): {year_match:.2f}")

            return total_confidence, tmdb_metadata

        except Exception as e:
            logger.error(f"Error validating with TMDB: {e}")
            return 0.5, None

    def analyze_file_characteristics(self, item: Dict) -> Dict:
        """Analyze file characteristics for additional confidence signals.

        Args:
            item: Jellyfin item

        Returns:
            Analysis dictionary
        """
        analysis = {
            'has_reasonable_name': False,
            'has_year_in_path': False,
            'looks_like_proper_release': False
        }

        path = item.get('Path', '')
        name = item.get('Name', '')

        if not path:
            return analysis

        # Check if name looks reasonable (not just a hash or gibberish)
        if name and len(name) > 3 and not self._looks_like_hash(name):
            analysis['has_reasonable_name'] = True

        # Check if path contains a year
        if re.search(r'\b(19\d{2}|20\d{2})\b', path):
            analysis['has_year_in_path'] = True

        # Check if it looks like a proper release (not a raw rip)
        proper_release_indicators = [
            r'BluRay', r'WEB-DL', r'WEBRip', r'HDTV', r'DVDRip',
            r'x264', r'x265', r'HEVC', r'h264', r'h265'
        ]
        for indicator in proper_release_indicators:
            if re.search(indicator, path, re.IGNORECASE):
                analysis['looks_like_proper_release'] = True
                break

        return analysis

    def _extract_year_from_filename(self, filename: str) -> Optional[int]:
        """Extract year from filename.

        Args:
            filename: The filename

        Returns:
            Year or None
        """
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
        if year_match:
            return int(year_match.group(1))
        return None

    def _looks_like_hash(self, text: str) -> bool:
        """Check if text looks like a hash or random string.

        Args:
            text: Text to check

        Returns:
            True if looks like hash
        """
        # If more than 50% of characters are numbers/special chars
        special_count = sum(1 for c in text if not c.isalpha() and not c.isspace())
        return special_count / len(text) > 0.5

    def _parse_episode_filename(self, filename: str) -> Optional[Dict]:
        """Parse episode information from filename using intelligent parser.

        Args:
            filename: Filename like "Toast.of.London.S03E02.1080p.WEB.H264-DiMEPiECE.mkv"

        Returns:
            Dict with show_name, season, episode or None
        """
        # Use the intelligent filename parser
        parsed = self.filename_parser.parse(filename)

        if not parsed:
            return None

        # Extract the required fields
        result = {}

        if 'title' in parsed:
            result['show_name'] = parsed['title']

        if 'season' in parsed:
            result['season'] = parsed['season']

        if 'episode' in parsed:
            result['episode'] = parsed['episode']

        # Only return if we have at least the show name
        return result if 'show_name' in result else None

    def _extract_show_name_from_episode(self, episode_name: str) -> str:
        """Extract show name from episode title.

        Args:
            episode_name: Full episode name (e.g., "Show Name - S01E01 - Episode Title")

        Returns:
            Just the show name
        """
        # Common patterns:
        # "Show Name - S01E01 - Episode Title"
        # "Show Name S01E01 Episode Title"
        # "Show Name - Episode Title"

        # Try splitting by " - " first
        if ' - ' in episode_name:
            parts = episode_name.split(' - ')
            # First part is usually the show name
            show_name = parts[0].strip()

            # Remove any season/episode markers from show name
            show_name = re.sub(r'[Ss]\d{1,2}[Ee]\d{1,2}', '', show_name)
            show_name = re.sub(r'\d{1,2}x\d{1,2}', '', show_name)
            show_name = show_name.strip()

            return show_name

        # Try to find season/episode pattern and take everything before it
        match = re.search(r'(.+?)\s*[Ss]\d{1,2}[Ee]\d{1,2}', episode_name)
        if match:
            return match.group(1).strip()

        # If no pattern found, return original (might be just show name)
        return episode_name.strip()

    def should_use_perplexity(
        self,
        local_confidence: float,
        tmdb_confidence: float,
        threshold: float
    ) -> bool:
        """Determine if Perplexity should be queried.

        Args:
            local_confidence: Confidence from local analysis
            tmdb_confidence: Confidence from TMDB validation
            threshold: Update threshold

        Returns:
            True if Perplexity should be used
        """
        # Use the higher of the two confidences
        best_confidence = max(local_confidence, tmdb_confidence)

        # If TMDB validation is very high, trust it
        if tmdb_confidence >= 0.85:
            logger.info(f"TMDB confidence high ({tmdb_confidence:.2f}), skipping Perplexity")
            return False

        # If both are low, definitely use Perplexity
        if best_confidence < threshold:
            logger.info(f"Best confidence ({best_confidence:.2f}) below threshold, using Perplexity")
            return True

        # Otherwise, skip Perplexity
        logger.info(f"Best confidence ({best_confidence:.2f}) acceptable, skipping Perplexity")
        return False
