"""Main crawler orchestration logic.

This module provides the MetadataCrawler class, which orchestrates the entire
metadata improvement workflow for Jellyfin media libraries. It coordinates between
multiple services (Jellyfin, TMDB, Perplexity AI) to identify and fix incorrect
or missing metadata.

The crawler follows a multi-stage validation approach:
    1. Local analysis - Evaluate current metadata quality
    2. TMDB validation - Fast, free validation against TMDB database
    3. Perplexity AI - Advanced AI identification for difficult cases
    4. Metadata application - Update Jellyfin with improved metadata

Example:
    Basic usage of the crawler:

    >>> from src.config import Config
    >>> from src.crawler import MetadataCrawler
    >>>
    >>> config = Config()
    >>> crawler = MetadataCrawler(config)
    >>> crawler.run()  # Process all items in library
    >>>
    >>> # Or fix a specific item:
    >>> crawler.fix_single_item("item-id-here")

Attributes:
    logger: Module-level logger instance for this crawler.
"""

import logging
from typing import Dict, Optional

from .config import Config
from .jellyfin_client import JellyfinClient
from .perplexity_client import PerplexityClient
from .metadata_analyzer import MetadataAnalyzer
from .metadata_updater import MetadataUpdater
from .metadata_validator import MetadataValidator
from .state_tracker import StateTracker

# Configure module-level logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MetadataCrawler:
    """Orchestrates the metadata improvement process for Jellyfin media libraries.

    The MetadataCrawler is the main entry point for automated metadata improvement.
    It coordinates between multiple services to validate and enhance media metadata:

    - Jellyfin API: Source of current metadata and target for updates
    - TMDB API: Primary validation source (free, fast, accurate)
    - Perplexity AI: Advanced identification for edge cases
    - State tracking: Resume capability and avoiding duplicate work

    The crawler uses a waterfall approach to minimize API costs:
    1. Check if item was already processed (state tracking)
    2. Analyze current metadata quality (local confidence scoring)
    3. Validate with TMDB if confidence is low (free, fast)
    4. Use Perplexity AI only if TMDB validation insufficient (paid API)

    Attributes:
        config (Config): Configuration object with API keys and settings.
        jellyfin (JellyfinClient): Client for Jellyfin API operations.
        perplexity (PerplexityClient): Client for Perplexity AI API.
        analyzer (MetadataAnalyzer): Analyzes metadata quality/confidence.
        updater (MetadataUpdater): Fetches metadata from external sources.
        validator (MetadataValidator): Validates metadata against TMDB.
        state (StateTracker): Tracks processed items for resume capability.
        stats (dict): Runtime statistics for the current crawl session.

    Example:
        Typical workflow for processing a library:

        >>> crawler = MetadataCrawler(config)
        >>> crawler.run()  # Process entire library

        Or fix specific problematic items:

        >>> crawler.fix_single_item("abc123")  # Fix one movie/episode
        >>> crawler.fix_series_episodes("series-id")  # Fix all episodes in series
    """

    def __init__(self, config: Config):
        """Initialize the metadata crawler with all required services.

        Sets up clients for Jellyfin, TMDB, and Perplexity AI, along with
        the metadata analyzer, validator, and state tracker.

        Args:
            config: Configuration object containing API keys, URLs, and settings.
                   Must include JELLYFIN_URL, JELLYFIN_API_KEY, and optionally
                   TMDB_API_KEY and PERPLEXITY_API_KEY.

        Raises:
            ValueError: If required configuration values are missing.
        """
        self.config = config

        # Initialize API clients
        self.jellyfin = JellyfinClient(config.JELLYFIN_URL, config.JELLYFIN_API_KEY)
        self.perplexity = PerplexityClient(config.PERPLEXITY_API_KEY, config.PERPLEXITY_USE_PRO)

        # Initialize metadata processing components
        self.analyzer = MetadataAnalyzer()  # Analyzes current metadata quality
        self.updater = MetadataUpdater(config.TMDB_API_KEY)  # Fetches from TMDB
        self.validator = MetadataValidator(self.updater)  # Validates against TMDB
        self.state = StateTracker()  # Tracks processed items

        # Initialize statistics tracking for this session
        self.stats = {
            'total_items': 0,           # Total items found in library
            'analyzed': 0,               # Items analyzed for quality
            'needs_update': 0,           # Items that need metadata fixes
            'updated': 0,                # Items successfully updated
            'errors': 0,                 # Items that encountered errors
            'skipped': 0,                # Items skipped (no path, wrong type, etc.)
            'already_processed': 0,      # Items already processed in previous runs
            'validated_with_tmdb': 0,    # Items validated with TMDB
            'used_perplexity': 0,        # Items that required Perplexity AI
            'tmdb_episode_cache_hits': 0,  # Episode cache efficiency metric
            'tmdb_shows_cached': 0       # Number of shows cached
        }

    def run(self):
        """Run the metadata crawler on the entire Jellyfin library.

        This method processes all items in the Jellyfin library, analyzing
        and updating metadata where needed. It follows these steps for each item:

        1. Fetch all items from Jellyfin
        2. For each item:
           - Check if already processed (state tracking)
           - Analyze current metadata quality
           - Validate with TMDB if quality is low
           - Use Perplexity AI if TMDB validation is insufficient
           - Update Jellyfin with improved metadata
        3. Print summary statistics

        The crawler respects configuration settings:
        - DRY_RUN: If True, no actual updates are made
        - MIN_CONFIDENCE_THRESHOLD: Items below this are candidates for update
        - EXCLUDE_MUSIC: If True, skip music/audio items
        - UPDATE_IMAGES: If True, also update poster/backdrop images

        Raises:
            Exception: If Jellyfin connection fails or other critical errors occur.
                      Individual item errors are logged but don't stop processing.

        Example:
            >>> crawler = MetadataCrawler(config)
            >>> crawler.run()
            Starting Jellyfin metadata crawler
            Found 550 items
            Processing item 1/550...
            ...
            Successfully updated metadata
        """
        logger.info("Starting Jellyfin metadata crawler")
        logger.info(f"Confidence threshold: {self.config.MIN_CONFIDENCE_THRESHOLD}")
        logger.info(f"Exclude music: {self.config.EXCLUDE_MUSIC}")
        logger.info(f"Dry run mode: {self.config.DRY_RUN}")
        logger.info(f"Update images: {self.config.UPDATE_IMAGES}")

        try:
            # Fetch all media items from the Jellyfin library
            logger.info("Fetching items from Jellyfin...")
            items = self.jellyfin.get_all_items(exclude_music=self.config.EXCLUDE_MUSIC)
            self.stats['total_items'] = len(items)
            logger.info(f"Found {len(items)} items")

            # Process each item sequentially
            # Note: Could be parallelized in future but current implementation
            # is sequential to avoid API rate limits and simplify error handling
            for i, item in enumerate(items, 1):
                logger.info(f"\n--- Processing item {i}/{len(items)} ---")
                self._process_item(item)

            # Display summary statistics for the crawl session
            self._print_summary()

        except Exception as e:
            logger.error(f"Error running crawler: {e}", exc_info=True)
            raise

    def fix_single_item(self, item_id: str):
        """Fix metadata for a single specific item.

        This method processes a single Jellyfin item, forcing an update
        regardless of confidence score. Useful for fixing known problem items.

        The item is removed from the processed state to ensure it gets
        reprocessed even if it was previously handled.

        Args:
            item_id: Jellyfin item ID (UUID format). Can be obtained from the
                    Jellyfin web interface URL or API.

        Example:
            Fix a specific movie that has incorrect metadata:

            >>> crawler.fix_single_item("76ec4e151dda47ab20ff280ea3e48ced")
            Fixing single item: 76ec4e151dda47ab20ff280ea3e48ced
            Found item: Galaxy Quest
            Force update mode - will update regardless of confidence
            Successfully updated metadata

        Note:
            This method uses force_update=True to bypass confidence checks,
            ensuring the item gets updated even if current metadata seems good.
        """
        logger.info(f"Fixing single item: {item_id}")
        logger.info(f"Confidence threshold: {self.config.MIN_CONFIDENCE_THRESHOLD}")
        logger.info(f"Dry run mode: {self.config.DRY_RUN}")
        logger.info(f"Update images: {self.config.UPDATE_IMAGES}")

        try:
            # Fetch the specific item from Jellyfin
            item = self.jellyfin.get_item_by_id(item_id)
            if not item:
                logger.error(f"Item {item_id} not found in Jellyfin")
                return

            logger.info(f"Found item: {item.get('Name', 'Unknown')}")

            # Remove from state so it will be processed
            if self.state.is_processed(item_id):
                logger.info("Removing from processed state to force reprocessing")
                self.state.processed_items.discard(item_id)

            # Process the item (this will force update even if confidence is high)
            self._process_item(item, force_update=True)

            logger.info(f"\nSingle item processing complete")

        except Exception as e:
            logger.error(f"Error fixing item {item_id}: {e}", exc_info=True)
            raise

    def fix_series_episodes(self, series_id: str):
        """Fix metadata for all episodes in a TV series.

        This method processes all episodes in a given TV series, forcing updates
        regardless of current metadata quality. Particularly useful for fixing
        entire seasons where metadata is systematically wrong.

        Each episode is processed independently, so if one fails, others continue.
        A summary is printed at the end showing success/error counts.

        Args:
            series_id: Jellyfin series ID (UUID format). This is the parent series
                      container, not an individual episode or season.

        Example:
            Fix all episodes in a series that has incorrect episode titles:

            >>> crawler.fix_series_episodes("970488e781a9840f6e758a7469da13ef")
            Fixing all episodes in series: 970488e781a9840f6e758a7469da13ef
            Found series: Police Squad!
            Found 6 episodes to process
            Processing episode 1/6: S01E01 - A Substantial Gift
            ...
            SERIES FIX SUMMARY
            Successfully processed: 6
            Errors: 0

        Note:
            This method only processes Episodes, not the Series item itself.
            To fix the series metadata, use fix_single_item() on the series ID.
        """
        logger.info(f"Fixing all episodes in series: {series_id}")
        logger.info(f"Confidence threshold: {self.config.MIN_CONFIDENCE_THRESHOLD}")
        logger.info(f"Dry run mode: {self.config.DRY_RUN}")
        logger.info(f"Update images: {self.config.UPDATE_IMAGES}")

        try:
            # Fetch series info
            series = self.jellyfin.get_series_info(series_id)
            if not series:
                logger.error(f"Series {series_id} not found in Jellyfin")
                return

            series_name = series.get('Name', 'Unknown')
            logger.info(f"Found series: {series_name}")

            # Get all episodes
            episodes = self.jellyfin.get_series_episodes(series_id)
            if not episodes:
                logger.warning("No episodes found for this series")
                return

            logger.info(f"Found {len(episodes)} episodes to process")

            # Process each episode
            success_count = 0
            error_count = 0

            for i, episode in enumerate(episodes, 1):
                episode_id = episode.get('Id')
                episode_name = episode.get('Name', 'Unknown')
                season = episode.get('ParentIndexNumber', '?')
                episode_num = episode.get('IndexNumber', '?')

                logger.info(f"\n--- Processing episode {i}/{len(episodes)}: S{season:02d}E{episode_num:02d} - {episode_name} ---")

                # Remove from state so it will be processed
                if self.state.is_processed(episode_id):
                    logger.debug("Removing from processed state to force reprocessing")
                    self.state.processed_items.discard(episode_id)

                # Process the episode (force update)
                try:
                    self._process_item(episode, force_update=True)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing episode {episode_name}: {e}")
                    error_count += 1

            logger.info(f"\n{'=' * 60}")
            logger.info(f"SERIES FIX SUMMARY")
            logger.info(f"{'=' * 60}")
            logger.info(f"Series: {series_name}")
            logger.info(f"Total episodes: {len(episodes)}")
            logger.info(f"Successfully processed: {success_count}")
            logger.info(f"Errors: {error_count}")
            logger.info(f"{'=' * 60}")

        except Exception as e:
            logger.error(f"Error fixing series {series_id}: {e}", exc_info=True)
            raise

    def _process_item(self, item: Dict, force_update: bool = False):
        """Process a single Jellyfin item through the metadata improvement workflow.

        This is the core processing method that handles a single media item
        (movie, TV episode, or series). It orchestrates the entire workflow:

        1. **Validation checks**: Skip if already processed or unsupported type
        2. **Local analysis**: Evaluate current metadata quality (confidence score)
        3. **TMDB validation**: Fast, free validation against TMDB database
        4. **Perplexity AI**: Advanced identification for difficult cases
        5. **Metadata update**: Apply improved metadata to Jellyfin
        6. **State tracking**: Mark as processed to avoid duplicate work

        The method uses a waterfall approach to minimize API costs:
        - TMDB is tried first (free, fast, accurate for most cases)
        - Perplexity AI is only used if TMDB validation is insufficient
        - This can save significant costs on large libraries

        Args:
            item: Jellyfin item dictionary containing metadata like:
                  - Id: Unique item identifier
                  - Name: Current title
                  - Type: Media type (Movie, Series, Episode)
                  - Path: File system path
                  - ProductionYear, Overview, etc.
            force_update: If True, bypass confidence checks and always update.
                         Used by fix_single_item() and fix_series_episodes().

        Returns:
            None. Updates are applied directly to Jellyfin via API.

        Raises:
            Exception: Errors are logged but don't propagate to allow
                      continuation with other items.

        Example:
            Internal use by run() method:

            >>> for item in items:
            ...     self._process_item(item)  # Normal processing
            >>>
            >>> # Or force update for a specific item:
            >>> self._process_item(problem_item, force_update=True)
        """
        # Extract item metadata
        item_id = item.get('Id')
        name = item.get('Name', 'Unknown')
        item_type = item.get('Type', 'Unknown')
        path = item.get('Path', '')

        logger.info(f"Item: {name} ({item_type})")
        logger.info(f"Path: {path}")

        # === STEP 1: Pre-processing checks ===

        # Skip items already processed in a previous run (resume capability)
        if self.state.is_processed(item_id):
            logger.info("Already processed previously, skipping")
            self.stats['already_processed'] += 1
            return

        # Skip virtual items without file paths (e.g., collections, folders)
        # These are Jellyfin organizational items, not actual media files
        if not path:
            logger.info("Skipping: No file path")
            self.stats['skipped'] += 1
            self.state.mark_skipped(item_id)
            return

        # Skip unsupported item types
        # Season: Virtual container for episodes (handled via episodes instead)
        # Music types: Can be excluded via config to focus on video content
        if item_type in ['Season', 'MusicAlbum', 'MusicArtist', 'Audio']:
            if self.config.EXCLUDE_MUSIC or item_type == 'Season':
                logger.info(f"Skipping: {item_type} type")
                self.stats['skipped'] += 1
                self.state.mark_skipped(item_id)
                return

        try:
            # === STEP 2: Local metadata quality analysis ===

            # Analyze current metadata to determine if update is needed
            # Returns confidence score (0.0-1.0) based on:
            # - Filename vs metadata title match
            # - Year presence and correctness
            # - Provider IDs (IMDb, TMDB)
            # - Overview quality
            # - Image presence
            confidence, analysis = self.analyzer.analyze_item(item)
            self.stats['analyzed'] += 1

            logger.info(f"Confidence score: {confidence:.2f}")
            logger.info(f"Analysis: {analysis}")

            # If confidence is high and not forcing update, skip this item
            if not force_update and not self.analyzer.needs_update(confidence, self.config.MIN_CONFIDENCE_THRESHOLD):
                logger.info("Metadata looks good, no update needed")
                self.state.mark_processed(item_id)
                return

            if force_update:
                logger.info("Force update mode - will update regardless of confidence")
            else:
                logger.info("Confidence below threshold, checking if update needed...")
            self.stats['needs_update'] += 1

            # === STEP 3: TMDB validation ===

            # Pass the file path to the validator for intelligent parsing
            # The validator will:
            # - Parse filename to extract title, year, season/episode
            # - Search TMDB for matches
            # - Score results based on title similarity and year matching
            # - For movies: Validate runtime to prevent wrong matches
            # For Series items, the path itself is the series folder
            # For Episode items, the path includes the episode file
            # For Movie items, the path includes the movie file

            logger.info("Step 1: Validating with TMDB...")
            tmdb_confidence, tmdb_metadata = self.validator.validate_with_tmdb(
                item, path, item_type
            )
            self.stats['validated_with_tmdb'] += 1

            # === STEP 4: Determine if Perplexity AI is needed ===

            # Decision logic:
            # - If TMDB confidence >= 0.85: Trust TMDB, skip Perplexity (cost savings)
            # - If local confidence < threshold: Use Perplexity for better identification
            # - Otherwise: TMDB is good enough
            should_use_perplexity = self.validator.should_use_perplexity(
                confidence, tmdb_confidence, self.config.MIN_CONFIDENCE_THRESHOLD
            )

            new_metadata = None

            if should_use_perplexity:
                # === STEP 5: Perplexity AI identification ===

                logger.info("Step 2: Using Perplexity AI for identification...")
                # Perplexity uses advanced AI to identify media from filenames
                # Particularly useful for:
                # - Obscure or foreign titles
                # - Files with ambiguous or truncated names
                # - Special characters (e.g., Brüno vs Bruno)
                new_metadata = self.perplexity.identify_media(path, item, item_type)
                self.stats['used_perplexity'] += 1

                if not new_metadata:
                    logger.warning("Could not identify media with Perplexity")
                    # Fallback: Use TMDB results if available
                    # Better to have some metadata than none
                    if tmdb_metadata:
                        logger.info("Falling back to TMDB metadata")
                        new_metadata = tmdb_metadata
                    else:
                        self.stats['errors'] += 1
                        return

                logger.info(f"Perplexity identified as: {new_metadata.get('title')}")
                logger.info(f"Perplexity confidence: {new_metadata.get('confidence', 0):.2f}")

                # === STEP 6: Enrich Perplexity results with TMDB data ===

                # Perplexity is great at identification but TMDB has richer metadata
                # Combine both: Perplexity for title, TMDB for images/genres/ratings
                logger.info("Step 3: Enriching with TMDB data...")
                tmdb_enrichment = self._try_tmdb_search(new_metadata, item_type)
                if tmdb_enrichment:
                    logger.info("Successfully enriched with TMDB metadata")

                    # Merge TMDB supplemental data into Perplexity results
                    # IMPORTANT: Preserve Perplexity's title (more accurate identification)
                    # Only add missing fields like images, genres, ratings
                    for key in ['ProviderIds', 'Overview', 'Genres', 'ProductionYear', 'PosterUrl', 'BackdropUrl', 'LogoUrl', 'CommunityRating']:
                        if key in tmdb_enrichment and key not in new_metadata:
                            new_metadata[key] = tmdb_enrichment[key]

                    # Log discrepancies between Perplexity and TMDB titles
                    # Helps identify potential identification issues
                    tmdb_name = tmdb_enrichment.get('Name', '')
                    perplexity_name = new_metadata.get('title', '')
                    if tmdb_name and perplexity_name and tmdb_name.lower() != perplexity_name.lower():
                        logger.warning(f"TMDB title '{tmdb_name}' differs from Perplexity title '{perplexity_name}' - using Perplexity title")
                else:
                    logger.warning("Could not enrich with TMDB data")

            else:
                # TMDB validation was sufficient - use it directly
                if tmdb_metadata:
                    logger.info("Using TMDB metadata (sufficient confidence)")
                    new_metadata = tmdb_metadata
                else:
                    # Local confidence was acceptable, no external lookup needed
                    logger.info("Local confidence acceptable, no update needed")
                    self.state.mark_processed(item_id)
                    return

            # Sanity check: Ensure we have metadata to apply
            if not new_metadata:
                logger.error("No metadata available for update")
                self.stats['errors'] += 1
                return

            # === STEP 7: Apply metadata updates to Jellyfin ===

            if not self.config.DRY_RUN:
                # Actually update Jellyfin via API
                success = self._apply_metadata_update(item_id, item, new_metadata)
                if success:
                    self.stats['updated'] += 1
                    self.state.mark_processed(item_id)
                    logger.info("Successfully updated metadata")
                else:
                    self.stats['errors'] += 1
                    logger.error("Failed to update metadata")
            else:
                # Dry-run mode: Log what would be done without making changes
                logger.info("[DRY RUN] Would update metadata")
                self.stats['updated'] += 1
                self.state.mark_processed(item_id)

        except Exception as e:
            # Log errors but don't propagate - allows processing other items
            logger.error(f"Error processing item {name}: {e}", exc_info=True)
            self.stats['errors'] += 1

    def _try_tmdb_search(self, perplexity_metadata: Dict, item_type: str) -> Optional[Dict]:
        """Enrich Perplexity AI results with TMDB metadata.

        This method attempts to fetch additional metadata from TMDB to supplement
        Perplexity's identification results. TMDB provides rich metadata like:
        - High-quality poster and backdrop images
        - Detailed genre information
        - Cast and crew information
        - Community ratings and vote counts
        - Provider IDs (IMDb, TMDB)

        The method uses multiple fallback strategies:
        1. If Perplexity provided a TMDB ID, fetch directly by ID (most reliable)
        2. Otherwise, search TMDB by title and year
        3. If not found as specified type, try opposite type (Movie ↔ TV)

        Args:
            perplexity_metadata: Metadata dictionary from Perplexity AI containing
                                at least 'title', optionally 'year' and 'tmdb_id'.
            item_type: Media type hint ('Movie', 'Series', 'Episode').

        Returns:
            TMDB metadata dictionary with enriched fields, or None if not found.

        Example:
            >>> perplexity_data = {'title': 'Inception', 'year': 2010}
            >>> tmdb_data = self._try_tmdb_search(perplexity_data, 'Movie')
            >>> tmdb_data.get('PosterUrl')
            'https://image.tmdb.org/t/p/original/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg'
        """
        title = perplexity_metadata.get('title')
        year = perplexity_metadata.get('year')

        if not title:
            return None

        try:
            # First try with TMDB ID if available
            tmdb_id = perplexity_metadata.get('tmdb_id')
            if tmdb_id:
                logger.info(f"Fetching from TMDB with ID: {tmdb_id}")
                metadata = self.updater.fetch_tmdb_metadata(tmdb_id, item_type)
                if metadata:
                    return metadata

            # Otherwise search by title
            logger.info(f"Searching TMDB for: {title} ({year if year else 'no year'})")

            # Try searching as the specified type first
            metadata = self.updater.search_tmdb(title, year, item_type)
            if metadata:
                return metadata

            # If not found and type is Series, also try as Movie (files can be miscategorized)
            if item_type == 'Series':
                logger.info("Not found as TV series, trying as movie...")
                metadata = self.updater.search_tmdb(title, year, 'Movie')
                if metadata:
                    return metadata

            # If not found and type is Movie, also try as TV series
            elif item_type == 'Movie':
                logger.info("Not found as movie, trying as TV series...")
                metadata = self.updater.search_tmdb(title, year, 'Series')
                if metadata:
                    return metadata

            return None

        except Exception as e:
            logger.error(f"Error searching TMDB: {e}")
            return None

    def _apply_metadata_update(self, item_id: str, current_item: Dict, new_metadata: Dict) -> bool:
        """Apply metadata update to Jellyfin.

        Args:
            item_id: Jellyfin item ID
            current_item: Current item data
            new_metadata: New metadata to apply

        Returns:
            True if successful
        """
        try:
            # Prepare metadata for Jellyfin
            jellyfin_metadata = self._prepare_jellyfin_metadata(new_metadata)
            logger.debug(f"Prepared Jellyfin metadata: {jellyfin_metadata}")

            # Update metadata fields
            updated_item = self.updater.apply_metadata_to_item(current_item, jellyfin_metadata)
            logger.debug(f"Merged item keys: {list(updated_item.keys())}")

            # Lock the fields we're updating to prevent Jellyfin from overwriting them
            # LockedFields must use Jellyfin's MetadataField enum values
            locked_fields = updated_item.get('LockedFields', [])
            if not isinstance(locked_fields, list):
                locked_fields = []

            # Map our fields to Jellyfin's MetadataField enum values
            # Valid values: Name, Overview, Genres, Tags, ProductionLocations, Studios, Cast, Runtime, OfficialRating
            fields_to_lock_map = {
                'Name': 'Name',
                'Overview': 'Overview',
                'Genres': 'Genres',
                'ProductionYear': 'Name',  # ProductionYear is part of Name metadata
                'OfficialRating': 'OfficialRating',
                'Studios': 'Studios',
                'Cast': 'Cast'
            }

            for field_key, lock_value in fields_to_lock_map.items():
                if field_key in jellyfin_metadata and lock_value not in locked_fields:
                    locked_fields.append(lock_value)

            # Remove duplicates
            locked_fields = list(set(locked_fields))
            updated_item['LockedFields'] = locked_fields
            logger.info(f"Locking metadata fields: {locked_fields}")

            success = self.jellyfin.update_item_metadata(item_id, updated_item)

            if not success:
                logger.error(f"Metadata update failed for item {item_id}")
                logger.error(f"Item name: {current_item.get('Name')}")
                logger.error(f"Item type: {current_item.get('Type')}")
                return False

            # Update images if enabled (continue even if some fail)
            if self.config.UPDATE_IMAGES:
                images = self.updater.get_image_urls(new_metadata)
                if images:
                    image_success_count = 0
                    for image_type, image_url in images.items():
                        if not image_url:
                            logger.warning(f"Skipping {image_type} image - no URL provided")
                            continue

                        logger.info(f"Updating {image_type} image...")
                        if self.jellyfin.update_item_images(item_id, image_url, image_type):
                            image_success_count += 1
                        else:
                            logger.warning(f"Failed to update {image_type} image (continuing anyway)")

                    logger.info(f"Updated {image_success_count}/{len(images)} images")
                else:
                    logger.debug("No image URLs available")
            else:
                logger.debug("Image updates disabled")

            # NOTE: Do NOT trigger metadata refresh for items we manually fixed
            # Metadata refresh causes Jellyfin to re-identify media and can overwrite our changes
            # Images will still show up without a full refresh
            logger.info("Skipping metadata refresh to preserve manual changes")

            return True

        except Exception as e:
            logger.error(f"Error applying metadata update for item {item_id}: {e}", exc_info=True)
            logger.error(f"New metadata that failed: {new_metadata}")
            return False

    def _prepare_jellyfin_metadata(self, metadata: Dict) -> Dict:
        """Prepare metadata in Jellyfin format.

        Args:
            metadata: Metadata dictionary

        Returns:
            Jellyfin-formatted metadata
        """
        jellyfin_metadata = {}

        # Map fields - TMDB uses 'Name', Perplexity uses 'title'
        if metadata.get('Name'):
            jellyfin_metadata['Name'] = metadata['Name']
        elif metadata.get('title'):
            jellyfin_metadata['Name'] = metadata['title']

        # TMDB might have ProductionYear already
        if metadata.get('ProductionYear'):
            jellyfin_metadata['ProductionYear'] = metadata['ProductionYear']
        elif metadata.get('year'):
            jellyfin_metadata['ProductionYear'] = metadata['year']

        # TMDB might have Overview already
        if metadata.get('Overview'):
            jellyfin_metadata['Overview'] = metadata['Overview']
        elif metadata.get('overview'):
            jellyfin_metadata['Overview'] = metadata['overview']

        # TMDB might have Genres already
        if metadata.get('Genres'):
            jellyfin_metadata['Genres'] = metadata['Genres']
        elif metadata.get('genres'):
            jellyfin_metadata['Genres'] = metadata['genres']

        # Provider IDs - handle both formats
        provider_ids = {}
        if metadata.get('ProviderIds'):
            # TMDB already has ProviderIds
            provider_ids.update(metadata['ProviderIds'])
        if metadata.get('imdb_id'):
            provider_ids['Imdb'] = metadata['imdb_id']
        if metadata.get('tmdb_id'):
            provider_ids['Tmdb'] = str(metadata['tmdb_id'])

        if provider_ids:
            jellyfin_metadata['ProviderIds'] = provider_ids

        # Community rating
        if metadata.get('CommunityRating'):
            jellyfin_metadata['CommunityRating'] = metadata['CommunityRating']

        return jellyfin_metadata

    def _print_summary(self):
        """Print summary statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("CRAWLER SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total items: {self.stats['total_items']}")
        logger.info(f"Already processed: {self.stats['already_processed']}")
        logger.info(f"Analyzed: {self.stats['analyzed']}")
        logger.info(f"Needed update: {self.stats['needs_update']}")
        logger.info(f"Validated with TMDB: {self.stats['validated_with_tmdb']}")
        logger.info(f"Used Perplexity: {self.stats['used_perplexity']}")
        logger.info(f"Updated: {self.stats['updated']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 60)

        # TMDB caching stats
        cache_size = len(self.updater.tv_episode_cache)
        if cache_size > 0:
            total_cached_episodes = sum(
                len(show['episodes'])
                for show in self.updater.tv_episode_cache.values()
            )
            logger.info(f"\nTMDB Episode Cache:")
            logger.info(f"  Shows cached: {cache_size}")
            logger.info(f"  Episodes cached: {total_cached_episodes}")
            logger.info(f"  Cache efficiency: Fetched all episodes for {cache_size} shows upfront")

        # Cost savings estimate
        if self.stats['validated_with_tmdb'] > 0:
            perplexity_saved = self.stats['validated_with_tmdb'] - self.stats['used_perplexity']
            if perplexity_saved > 0:
                logger.info(f"\nCost savings: Avoided {perplexity_saved} Perplexity API calls")
        logger.info("=" * 60)
