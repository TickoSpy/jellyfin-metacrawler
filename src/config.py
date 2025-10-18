"""Configuration module for Jellyfin metadata crawler."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class for the metadata crawler."""

    # Jellyfin settings
    JELLYFIN_URL = os.getenv('JELLYFIN_URL', 'http://localhost:8096')
    JELLYFIN_API_KEY = os.getenv('JELLYFIN_API_KEY')

    # Perplexity AI settings
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
    PERPLEXITY_USE_PRO = os.getenv('PERPLEXITY_USE_PRO', 'false').lower() == 'true'

    # TMDB settings (optional)
    TMDB_API_KEY = os.getenv('TMDB_API_KEY')

    # Crawler settings
    MIN_CONFIDENCE_THRESHOLD = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', '0.90'))
    EXCLUDE_MUSIC = os.getenv('EXCLUDE_MUSIC', 'true').lower() == 'true'
    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'
    UPDATE_IMAGES = os.getenv('UPDATE_IMAGES', 'false').lower() == 'true'

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        errors = []

        if not cls.JELLYFIN_API_KEY:
            errors.append("JELLYFIN_API_KEY is required")

        if not cls.PERPLEXITY_API_KEY:
            errors.append("PERPLEXITY_API_KEY is required")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True
