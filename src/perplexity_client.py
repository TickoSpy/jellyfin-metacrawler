"""Perplexity AI client for querying media metadata information."""

import requests
from typing import Dict, Optional
import logging
import json
import re

logger = logging.getLogger(__name__)


class PerplexityClient:
    """Client for interacting with Perplexity AI API."""

    def __init__(self, api_key: str, use_pro: bool = False):
        """Initialize Perplexity client.

        Args:
            api_key: Perplexity API key
            use_pro: Use sonar-pro model (default: sonar for cost efficiency)
        """
        self.api_key = api_key
        self.base_url = "https://api.perplexity.ai"
        self.model = "sonar-pro" if use_pro else "sonar"
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def identify_media(self, filename: str, current_metadata: Dict, media_type: str) -> Optional[Dict]:
        """Use Perplexity to identify media and get correct metadata.

        Args:
            filename: The filename of the media
            current_metadata: Current metadata from Jellyfin
            media_type: Type of media (Movie, Series, Episode, etc.)

        Returns:
            Dictionary with identified metadata or None
        """
        prompt = self._build_identification_prompt(filename, current_metadata, media_type)

        try:
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 500,
                "return_citations": False,
                "return_images": False,
                "return_related_questions": False
            }

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )

            # Log response for debugging
            if response.status_code != 200:
                logger.error(f"Perplexity API error {response.status_code}")
                logger.error(f"Response: {response.text}")
                try:
                    error_data = response.json()
                    logger.error(f"Error details: {error_data}")
                except:
                    pass

            response.raise_for_status()

            result = response.json()

            # Log token usage if available
            if 'usage' in result:
                usage = result['usage']
                logger.info(f"Token usage - Prompt: {usage.get('prompt_tokens', 0)}, "
                          f"Completion: {usage.get('completion_tokens', 0)}, "
                          f"Total: {usage.get('total_tokens', 0)}")

            content = result['choices'][0]['message']['content']
            logger.debug(f"Raw Perplexity response: {content}")

            # Parse the JSON response
            metadata = self._parse_perplexity_response(content)
            logger.info(f"Successfully identified media from filename: {filename}")
            return metadata

        except requests.exceptions.HTTPError as e:
            logger.error(f"Perplexity HTTP error: {e}")
            logger.error(f"Status code: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Perplexity request error: {e}")
            logger.error(f"Request URL: {self.base_url}/chat/completions")
            logger.error(f"Model: {self.model}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing Perplexity response: {e}")
            logger.error(f"Response content: {content if 'content' in locals() else 'N/A'}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Perplexity identify_media: {e}", exc_info=True)
            return None

    def _build_identification_prompt(self, filename: str, current_metadata: Dict, media_type: str) -> str:
        """Build prompt for media identification.

        Args:
            filename: The filename
            current_metadata: Current metadata
            media_type: Type of media

        Returns:
            Formatted prompt string
        """
        # Customize prompt based on media type
        if media_type == 'Series':
            prompt = f"""TV show name: {filename}
Find exact show. JSON:
{{"title":"","year":0,"overview":"","imdb_id":"","tmdb_id":"","genres":[],"confidence":0.0}}"""
        elif media_type == 'Episode':
            prompt = f"""Episode file: {filename}
Identify show + episode. JSON:
{{"title":"","year":0,"overview":"","imdb_id":"","tmdb_id":"","genres":[],"confidence":0.0}}"""
        else:
            prompt = f"""Movie: {filename}
JSON:
{{"title":"","year":0,"overview":"","imdb_id":"","tmdb_id":"","genres":[],"confidence":0.0}}"""

        return prompt

    def _parse_perplexity_response(self, content: str) -> Dict:
        """Parse Perplexity API response.

        Args:
            content: Response content from Perplexity

        Returns:
            Parsed metadata dictionary
        """
        # Try to extract JSON from the response
        # Sometimes the response includes markdown code blocks
        content = content.strip()

        logger.debug(f"Parsing response (first 200 chars): {content[:200]}")

        # Remove markdown code blocks if present
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]

        content = content.strip()

        # Try to extract and clean JSON
        json_str = self._extract_and_clean_json(content)

        try:
            metadata = json.loads(json_str)
            return self._normalize_metadata(metadata)
        except json.JSONDecodeError as e:
            logger.error(f"Could not parse JSON after cleaning: {e}")
            logger.error(f"Cleaned JSON: {json_str}")
            raise

    def _extract_and_clean_json(self, content: str) -> str:
        """Extract and clean JSON from response.

        Args:
            content: Response content

        Returns:
            Cleaned JSON string
        """
        # Find JSON object boundaries
        start = content.find('{')
        end = content.rfind('}') + 1

        if start == -1:
            logger.error("No JSON object found in response")
            return "{}"

        if end <= start:
            # JSON might be truncated - try to fix it
            logger.warning("JSON appears truncated, attempting to close it")
            json_str = content[start:]
            # Try to intelligently close the JSON
            json_str = self._fix_truncated_json(json_str)
        else:
            json_str = content[start:end]

        # Remove JavaScript-style comments (// comment)
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove inline comments
            if '//' in line:
                # Keep everything before the comment
                before_comment = line.split('//')[0]
                # If line has content before comment, keep it
                if before_comment.strip() and not before_comment.strip().endswith(','):
                    # Add comma if needed
                    if before_comment.rstrip().endswith('"') or before_comment.rstrip().endswith(']'):
                        before_comment = before_comment.rstrip()
                        if not before_comment.endswith(','):
                            before_comment += ','
                cleaned_lines.append(before_comment)
            else:
                cleaned_lines.append(line)

        json_str = '\n'.join(cleaned_lines)

        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

        # Remove multi-line comments /* ... */
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

        return json_str

    def _fix_truncated_json(self, json_str: str) -> str:
        """Attempt to fix truncated JSON by closing unclosed structures.

        Args:
            json_str: Potentially truncated JSON string

        Returns:
            Fixed JSON string
        """
        # Count open/close braces and brackets
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        open_brackets = json_str.count('[')
        close_brackets = json_str.count(']')

        # Remove any trailing commas or incomplete values
        json_str = json_str.rstrip()
        if json_str.endswith(','):
            json_str = json_str[:-1]

        # Close unclosed brackets
        while close_brackets < open_brackets:
            json_str += ']'
            close_brackets += 1

        # Close unclosed braces
        while close_braces < open_braces:
            json_str += '}'
            close_braces += 1

        return json_str

    def _normalize_metadata(self, metadata: Dict) -> Dict:
        """Normalize metadata to handle various formats.

        Args:
            metadata: Raw metadata dictionary

        Returns:
            Normalized metadata
        """
        normalized = {}

        # Handle title variations
        title = metadata.get('title') or metadata.get('Title') or metadata.get('name') or metadata.get('Name')
        if title:
            normalized['title'] = str(title).strip()

        # Handle year - might be string or int
        year = metadata.get('year') or metadata.get('Year') or metadata.get('production_year')
        if year:
            try:
                # Convert to int, handle strings like "2023"
                year_int = int(str(year).strip())
                if 1800 <= year_int <= 2100:  # Sanity check
                    normalized['year'] = year_int
            except (ValueError, TypeError):
                logger.warning(f"Could not parse year: {year}")

        # Handle overview/description
        overview = (
            metadata.get('overview') or
            metadata.get('Overview') or
            metadata.get('description') or
            metadata.get('Description') or
            metadata.get('plot')
        )
        if overview:
            normalized['overview'] = str(overview).strip()

        # Handle IMDb ID
        imdb_id = metadata.get('imdb_id') or metadata.get('imdb') or metadata.get('ImdbId')
        if imdb_id:
            imdb_str = str(imdb_id).strip()
            # Ensure it starts with 'tt'
            if not imdb_str.startswith('tt') and imdb_str.isdigit():
                imdb_str = 'tt' + imdb_str
            normalized['imdb_id'] = imdb_str

        # Handle TMDB ID
        tmdb_id = metadata.get('tmdb_id') or metadata.get('tmdb') or metadata.get('TmdbId')
        if tmdb_id:
            try:
                normalized['tmdb_id'] = str(int(tmdb_id))
            except (ValueError, TypeError):
                logger.warning(f"Could not parse TMDB ID: {tmdb_id}")

        # Handle genres - might be list or string
        genres = metadata.get('genres') or metadata.get('Genres')
        if genres:
            if isinstance(genres, list):
                normalized['genres'] = [str(g).strip() for g in genres if g]
            elif isinstance(genres, str):
                # Handle comma-separated genres
                normalized['genres'] = [g.strip() for g in genres.split(',') if g.strip()]

        # Handle confidence
        confidence = metadata.get('confidence') or metadata.get('Confidence')
        if confidence is not None:
            try:
                conf_float = float(confidence)
                # Clamp between 0 and 1
                normalized['confidence'] = max(0.0, min(1.0, conf_float))
            except (ValueError, TypeError):
                logger.warning(f"Could not parse confidence: {confidence}")
                normalized['confidence'] = 0.5

        # Handle poster/backdrop URLs
        poster_url = metadata.get('poster_url') or metadata.get('posterUrl') or metadata.get('poster')
        if poster_url:
            normalized['poster_url'] = str(poster_url).strip()

        backdrop_url = metadata.get('backdrop_url') or metadata.get('backdropUrl') or metadata.get('backdrop')
        if backdrop_url:
            normalized['backdrop_url'] = str(backdrop_url).strip()

        # Handle season/episode numbers for episodes
        season = metadata.get('season') or metadata.get('Season')
        if season:
            try:
                normalized['season'] = int(season)
            except (ValueError, TypeError):
                pass

        episode = metadata.get('episode') or metadata.get('Episode')
        if episode:
            try:
                normalized['episode'] = int(episode)
            except (ValueError, TypeError):
                pass

        logger.debug(f"Normalized metadata: {normalized}")

        return normalized
