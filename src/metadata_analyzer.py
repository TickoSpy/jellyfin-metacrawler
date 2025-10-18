"""Metadata analyzer for evaluating confidence in current metadata."""

import re
import os
from typing import Dict, Tuple
from thefuzz import fuzz
import logging
from .filename_parser import FilenameParser

logger = logging.getLogger(__name__)


class MetadataAnalyzer:
    """Analyzes metadata quality and confidence."""

    def __init__(self):
        """Initialize the metadata analyzer."""
        self.filename_parser = FilenameParser()

    def analyze_item(self, item: Dict) -> Tuple[float, Dict]:
        """Analyze an item and return confidence score and analysis details.

        Args:
            item: Jellyfin item dictionary

        Returns:
            Tuple of (confidence_score, analysis_details)
        """
        scores = []
        details = {}

        # Get filename and metadata
        path = item.get('Path', '')
        filename = os.path.basename(path) if path else ''
        name = item.get('Name', '')
        year = item.get('ProductionYear')
        overview = item.get('Overview', '')
        provider_ids = item.get('ProviderIds', {})

        # Score 1: Filename vs Name match
        filename_score = self._score_filename_match(filename, name)
        scores.append(filename_score)
        details['filename_match'] = filename_score

        # Score 2: Year presence and match
        year_score = self._score_year_match(filename, year)
        scores.append(year_score)
        details['year_match'] = year_score

        # Score 3: Provider IDs presence (IMDb, TMDB)
        provider_score = self._score_provider_ids(provider_ids)
        scores.append(provider_score)
        details['provider_ids'] = provider_score

        # Score 4: Overview quality
        overview_score = self._score_overview(overview)
        scores.append(overview_score)
        details['overview_quality'] = overview_score

        # Score 5: Image presence
        has_primary_image = item.get('ImageTags', {}).get('Primary') is not None
        image_score = 1.0 if has_primary_image else 0.3
        scores.append(image_score)
        details['has_image'] = image_score

        # Calculate weighted average
        weights = [0.35, 0.20, 0.20, 0.15, 0.10]  # Filename match is most important
        confidence = sum(s * w for s, w in zip(scores, weights))

        details['overall_confidence'] = confidence
        details['filename'] = filename
        details['current_name'] = name

        logger.debug(f"Analyzed {name}: confidence={confidence:.2f}")

        return confidence, details

    def _score_filename_match(self, filename: str, name: str) -> float:
        """Score how well the name matches the filename.

        Args:
            filename: The filename
            name: The metadata name

        Returns:
            Score between 0.0 and 1.0
        """
        if not filename or not name:
            return 0.0

        # Clean filename (remove extension and common patterns)
        clean_filename = self._clean_filename(filename)
        clean_name = name.lower().strip()

        # Use fuzzy matching
        ratio = fuzz.ratio(clean_filename, clean_name) / 100.0
        token_sort_ratio = fuzz.token_sort_ratio(clean_filename, clean_name) / 100.0

        # Take the best score
        score = max(ratio, token_sort_ratio)

        return score

    def _score_year_match(self, filename: str, year: int) -> float:
        """Score whether the year matches between filename and metadata.

        Args:
            filename: The filename
            year: The production year from metadata

        Returns:
            Score between 0.0 and 1.0
        """
        if not filename:
            return 0.5  # Neutral if no filename

        # Extract years from filename
        year_pattern = r'\b(19\d{2}|20\d{2})\b'
        years_in_filename = re.findall(year_pattern, filename)

        if not years_in_filename:
            # No year in filename
            if year:
                return 0.7  # Has year in metadata, but not in filename (somewhat okay)
            else:
                return 0.5  # No year in either (neutral)

        if not year:
            return 0.3  # Year in filename but not in metadata (bad)

        # Check if metadata year matches any year in filename
        if str(year) in years_in_filename:
            return 1.0  # Perfect match
        else:
            return 0.2  # Mismatch (bad)

    def _score_provider_ids(self, provider_ids: Dict) -> float:
        """Score the presence and quality of provider IDs.

        Args:
            provider_ids: Dictionary of provider IDs

        Returns:
            Score between 0.0 and 1.0
        """
        if not provider_ids:
            return 0.0

        score = 0.0

        # IMDb ID is most important
        if provider_ids.get('Imdb'):
            score += 0.6

        # TMDB is also valuable
        if provider_ids.get('Tmdb'):
            score += 0.4

        return min(score, 1.0)

    def _score_overview(self, overview: str) -> float:
        """Score the quality of the overview/description.

        Args:
            overview: The overview text

        Returns:
            Score between 0.0 and 1.0
        """
        if not overview:
            return 0.0

        # Score based on length (good overviews are usually substantial)
        length = len(overview)

        if length < 50:
            return 0.3
        elif length < 100:
            return 0.6
        elif length < 200:
            return 0.8
        else:
            return 1.0

    def _clean_filename(self, filename: str) -> str:
        """Clean filename for comparison using intelligent parsing.

        Args:
            filename: The filename to clean

        Returns:
            Cleaned filename
        """
        # Use the filename parser to extract clean title
        parsed = self.filename_parser.parse(filename)

        if parsed and 'clean_title' in parsed:
            # Successfully parsed, return clean title
            clean_title = parsed['clean_title']

            # For TV episodes, include episode title if available
            if 'episode_title' in parsed:
                clean_title = f"{clean_title} {parsed['episode_title']}"

            return clean_title.lower().strip()

        # Fallback to basic cleaning if parsing fails
        return self._basic_clean_filename(filename)

    def _basic_clean_filename(self, filename: str) -> str:
        """Basic filename cleaning as fallback.

        Args:
            filename: The filename to clean

        Returns:
            Cleaned filename
        """
        # Remove extension
        name = os.path.splitext(filename)[0]

        # Remove season/episode patterns first (S01E01, 1x01, etc.)
        season_ep_patterns = [
            r'[Ss]\d{1,2}[Ee]\d{1,2}',  # S01E01
            r'\d{1,2}x\d{1,2}',  # 1x01
            r'[Ss]eason\s*\d+',  # Season 1
            r'[Ee]pisode\s*\d+',  # Episode 1
        ]
        for pattern in season_ep_patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        # Remove common patterns
        patterns = [
            r'\[.*?\]',  # Remove brackets and contents
            r'\(.*?\)',  # Remove parentheses and contents
            r'\d{3,4}p',  # Remove resolution (1080p, 720p, etc.)
            r'BluRay|BRRip|DVDRip|WEBRip|HDTV|WEB-DL',  # Remove quality tags
            r'x264|x265|H\.264|H\.265|HEVC',  # Remove codec tags
            r'AAC|AC3|DTS|MP3',  # Remove audio codec tags
            r'YIFY|RARBG|YTS|ETRG|KOGi',  # Remove release group tags
        ]

        for pattern in patterns:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)

        # Replace dots, underscores with spaces
        name = name.replace('.', ' ').replace('_', ' ').replace('-', ' ')

        # Remove extra whitespace
        name = ' '.join(name.split())

        return name.lower().strip()

    def extract_show_name_from_path(self, path: str) -> str:
        """Extract show name from file path using intelligent parsing.

        Args:
            path: Full file path (could be a file or directory)

        Returns:
            Extracted show name
        """
        # Use the filename parser's dedicated method
        return self.filename_parser.extract_show_name(path)

    def needs_update(self, confidence: float, threshold: float) -> bool:
        """Determine if an item needs metadata update.

        Args:
            confidence: Confidence score
            threshold: Threshold for updates

        Returns:
            True if update is needed
        """
        return confidence < threshold
