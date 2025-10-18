# API Reference - Jellyfin Metadata Crawler

## Table of Contents

1. [MetadataCrawler](#metadatacrawler)
2. [MetadataUpdater](#metadataupdater)
3. [MetadataValidator](#metadatavalidator)
4. [JellyfinClient](#jellyfinclient)
5. [PerplexityClient](#perplexityclient)
6. [MetadataAnalyzer](#metadataanalyzer)
7. [FilenameParser](#filenameparser)
8. [StateTracker](#statetracker)
9. [Config](#config)

---

## MetadataCrawler

**Module**: `src.crawler`

Main orchestrator for the metadata improvement process.

### Constructor

```python
MetadataCrawler(config: Config)
```

**Parameters**:
- `config` (Config): Configuration object with API keys and settings

**Example**:
```python
from src.config import Config
from src.crawler import MetadataCrawler

config = Config()
crawler = MetadataCrawler(config)
```

### Methods

#### `run()`

Process the entire Jellyfin library.

**Parameters**: None

**Returns**: None

**Raises**:
- `Exception`: If Jellyfin connection fails

**Example**:
```python
crawler.run()
# Processes all items in library
```

---

#### `fix_single_item(item_id: str)`

Fix metadata for a single specific item.

**Parameters**:
- `item_id` (str): Jellyfin item ID (UUID format)

**Returns**: None

**Example**:
```python
crawler.fix_single_item("76ec4e151dda47ab20ff280ea3e48ced")
# Fixes one movie/episode
```

---

#### `fix_series_episodes(series_id: str)`

Fix metadata for all episodes in a TV series.

**Parameters**:
- `series_id` (str): Jellyfin series ID (UUID format)

**Returns**: None

**Example**:
```python
crawler.fix_series_episodes("970488e781a9840f6e758a7469da13ef")
# Fixes all episodes in series
```

---

## MetadataUpdater

**Module**: `src.metadata_updater`

TMDB API client with intelligent caching and scoring.

### Constructor

```python
MetadataUpdater(tmdb_api_key: Optional[str] = None)
```

**Parameters**:
- `tmdb_api_key` (Optional[str]): TMDB API v3 key

**Example**:
```python
from src.metadata_updater import MetadataUpdater

updater = MetadataUpdater(tmdb_api_key="your-key")
```

### Methods

#### `search_tmdb(title: str, year: Optional[int], media_type: str) -> Optional[Dict]`

Search TMDB for a title with intelligent result scoring.

**Parameters**:
- `title` (str): Title to search for
- `year` (Optional[int]): Year to narrow search
- `media_type` (str): Type of media ('movie' or 'tv')

**Returns**:
- `Optional[Dict]`: Metadata dictionary or None

**Example**:
```python
metadata = updater.search_tmdb("Inception", 2010, "movie")
print(metadata['Name'])  # "Inception"
print(metadata['ProductionYear'])  # 2010
```

---

#### `fetch_tmdb_metadata(tmdb_id: str, media_type: str) -> Optional[Dict]`

Fetch metadata directly by TMDB ID.

**Parameters**:
- `tmdb_id` (str): TMDB ID
- `media_type` (str): Type of media ('movie' or 'tv')

**Returns**:
- `Optional[Dict]`: Metadata dictionary or None

**Example**:
```python
metadata = updater.fetch_tmdb_metadata("27205", "movie")
```

---

#### `search_tmdb_episode(show_name: str, season: int, episode: int, year: Optional[int] = None) -> Optional[Dict]`

Search for a specific episode using cached show data.

**Parameters**:
- `show_name` (str): Name of the TV show
- `season` (int): Season number
- `episode` (int): Episode number
- `year` (Optional[int]): Optional year to narrow search

**Returns**:
- `Optional[Dict]`: Episode metadata dictionary or None

**Example**:
```python
episode = updater.search_tmdb_episode("Police Squad!", 1, 4)
print(episode['Name'])
# "Police Squad! - S01E04 - Revenge and Remorse"
```

---

#### `get_image_urls(metadata: Dict) -> Dict[str, str]`

Extract image URLs from metadata.

**Parameters**:
- `metadata` (Dict): Metadata dictionary

**Returns**:
- `Dict[str, str]`: Dictionary mapping image types to URLs

**Example**:
```python
images = updater.get_image_urls(metadata)
print(images['Primary'])  # Poster URL
print(images['Backdrop'])  # Backdrop URL
print(images['Logo'])  # Logo URL
```

---

## MetadataValidator

**Module**: `src.metadata_validator`

Validates metadata against TMDB and file information.

### Constructor

```python
MetadataValidator(tmdb_client: MetadataUpdater)
```

**Parameters**:
- `tmdb_client` (MetadataUpdater): TMDB client instance

**Example**:
```python
from src.metadata_validator import MetadataValidator

validator = MetadataValidator(tmdb_updater)
```

### Methods

#### `validate_with_tmdb(item: Dict, path: str, item_type: str) -> Tuple[float, Optional[Dict]]`

Validate current metadata against TMDB.

**Parameters**:
- `item` (Dict): Jellyfin item dictionary
- `path` (str): File path (source of truth)
- `item_type` (str): Type of media ('Movie', 'Series', 'Episode')

**Returns**:
- `Tuple[float, Optional[Dict]]`: (confidence_score, tmdb_metadata)

**Example**:
```python
confidence, metadata = validator.validate_with_tmdb(
    item=jellyfin_item,
    path="/path/to/Galaxy.Quest.1999.mkv",
    item_type="Movie"
)
print(f"Confidence: {confidence:.2f}")  # 0.95
```

---

#### `should_use_perplexity(local_confidence: float, tmdb_confidence: float, threshold: float) -> bool`

Determine if Perplexity AI should be queried.

**Parameters**:
- `local_confidence` (float): Confidence from local analysis
- `tmdb_confidence` (float): Confidence from TMDB validation
- `threshold` (float): Update threshold

**Returns**:
- `bool`: True if Perplexity should be used

**Example**:
```python
should_use = validator.should_use_perplexity(
    local_confidence=0.7,
    tmdb_confidence=0.6,
    threshold=0.9
)
```

---

## JellyfinClient

**Module**: `src.jellyfin_client`

Jellyfin API interaction layer.

### Constructor

```python
JellyfinClient(base_url: str, api_key: str)
```

**Parameters**:
- `base_url` (str): Jellyfin server URL
- `api_key` (str): Jellyfin API key

**Example**:
```python
from src.jellyfin_client import JellyfinClient

client = JellyfinClient(
    base_url="http://localhost:8096",
    api_key="your-api-key"
)
```

### Methods

#### `get_all_items(exclude_music: bool = True) -> List[Dict]`

Fetch all media items from Jellyfin.

**Parameters**:
- `exclude_music` (bool): Whether to exclude music items

**Returns**:
- `List[Dict]`: List of Jellyfin item dictionaries

**Example**:
```python
items = client.get_all_items(exclude_music=True)
print(f"Found {len(items)} items")
```

---

#### `get_item_by_id(item_id: str) -> Optional[Dict]`

Fetch a specific item by ID.

**Parameters**:
- `item_id` (str): Jellyfin item ID

**Returns**:
- `Optional[Dict]`: Item dictionary or None

**Example**:
```python
item = client.get_item_by_id("76ec4e151dda47ab20ff280ea3e48ced")
print(item['Name'])
```

---

#### `update_item_metadata(item_id: str, updated_item: Dict) -> bool`

Update item metadata in Jellyfin.

**Parameters**:
- `item_id` (str): Jellyfin item ID
- `updated_item` (Dict): Updated item dictionary

**Returns**:
- `bool`: True if successful

**Example**:
```python
updated_item['Name'] = "Inception"
updated_item['ProductionYear'] = 2010
updated_item['LockedFields'] = ['Name', 'Overview']

success = client.update_item_metadata(item_id, updated_item)
```

---

#### `update_item_images(item_id: str, image_url: str, image_type: str) -> bool`

Update item images.

**Parameters**:
- `item_id` (str): Jellyfin item ID
- `image_url` (str): Image URL
- `image_type` (str): Image type ('Primary', 'Backdrop', 'Logo')

**Returns**:
- `bool`: True if successful

**Example**:
```python
client.update_item_images(
    item_id="abc123",
    image_url="https://image.tmdb.org/t/p/original/poster.jpg",
    image_type="Primary"
)
```

---

## PerplexityClient

**Module**: `src.perplexity_client`

Perplexity AI client for advanced media identification.

### Constructor

```python
PerplexityClient(api_key: str, use_pro: bool = False)
```

**Parameters**:
- `api_key` (str): Perplexity API key
- `use_pro` (bool): Use sonar-pro model (default: sonar)

**Example**:
```python
from src.perplexity_client import PerplexityClient

client = PerplexityClient(
    api_key="your-key",
    use_pro=False
)
```

### Methods

#### `identify_media(filename: str, current_metadata: Dict, media_type: str) -> Optional[Dict]`

Use Perplexity AI to identify media.

**Parameters**:
- `filename` (str): The filename of the media
- `current_metadata` (Dict): Current metadata from Jellyfin
- `media_type` (str): Type of media ('Movie', 'Series', 'Episode')

**Returns**:
- `Optional[Dict]`: Identified metadata or None

**Example**:
```python
metadata = client.identify_media(
    filename="Brüno.m4v",
    current_metadata=current_item,
    media_type="Movie"
)
print(metadata['title'])  # "Brüno"
print(metadata['year'])  # 2009
```

---

## MetadataAnalyzer

**Module**: `src.metadata_analyzer`

Analyzes metadata quality and confidence.

### Constructor

```python
MetadataAnalyzer()
```

**Example**:
```python
from src.metadata_analyzer import MetadataAnalyzer

analyzer = MetadataAnalyzer()
```

### Methods

#### `analyze_item(item: Dict) -> Tuple[float, Dict]`

Analyze an item and return confidence score.

**Parameters**:
- `item` (Dict): Jellyfin item dictionary

**Returns**:
- `Tuple[float, Dict]`: (confidence_score, analysis_details)

**Example**:
```python
confidence, analysis = analyzer.analyze_item(item)
print(f"Confidence: {confidence:.2f}")
print(f"Filename match: {analysis['filename_match']:.2f}")
print(f"Year match: {analysis['year_match']:.2f}")
```

---

#### `needs_update(confidence: float, threshold: float) -> bool`

Determine if an item needs metadata update.

**Parameters**:
- `confidence` (float): Confidence score
- `threshold` (float): Threshold for updates

**Returns**:
- `bool`: True if update is needed

**Example**:
```python
needs_update = analyzer.needs_update(confidence=0.75, threshold=0.90)
# True (0.75 < 0.90)
```

---

## FilenameParser

**Module**: `src.filename_parser`

Intelligent filename parsing using GuessIt library.

### Constructor

```python
FilenameParser()
```

**Example**:
```python
from src.filename_parser import FilenameParser

parser = FilenameParser()
```

### Methods

#### `parse(filename: str, item_type: Optional[str] = None) -> Dict`

Parse a filename to extract media information.

**Parameters**:
- `filename` (str): The filename to parse
- `item_type` (Optional[str]): Optional hint ('Movie', 'Episode', 'Series')

**Returns**:
- `Dict`: Parsed information

**Example**:
```python
result = parser.parse("Toast.of.London.S03E02.1080p.WEB.H264.mkv")
print(result['title'])  # "Toast of London"
print(result['season'])  # 3
print(result['episode'])  # 2
print(result['resolution'])  # "1080p"
```

---

#### `extract_show_name(path: str) -> str`

Extract show name from a file path.

**Parameters**:
- `path` (str): Full file path

**Returns**:
- `str`: Extracted show name

**Example**:
```python
show_name = parser.extract_show_name(
    "/media/Police Squad/Season 1/Police Squad S01E04.mp4"
)
print(show_name)  # "Police Squad"
```

---

## StateTracker

**Module**: `src.state_tracker`

Tracks processed items for resume capability.

### Constructor

```python
StateTracker(state_file: str = ".crawler_state.json")
```

**Parameters**:
- `state_file` (str): Path to state file

**Example**:
```python
from src.state_tracker import StateTracker

tracker = StateTracker()
```

### Methods

#### `is_processed(item_id: str) -> bool`

Check if item has been processed.

**Parameters**:
- `item_id` (str): Item ID

**Returns**:
- `bool`: True if already processed

**Example**:
```python
if tracker.is_processed("abc123"):
    print("Already processed, skipping")
```

---

#### `mark_processed(item_id: str)`

Mark item as processed.

**Parameters**:
- `item_id` (str): Item ID

**Example**:
```python
tracker.mark_processed("abc123")
# Auto-saves to state file
```

---

#### `mark_skipped(item_id: str)`

Mark item as skipped.

**Parameters**:
- `item_id` (str): Item ID

**Example**:
```python
tracker.mark_skipped("virtual-item-id")
```

---

## Config

**Module**: `src.config`

Configuration class for the metadata crawler.

### Class Attributes

```python
# Required
JELLYFIN_URL: str
JELLYFIN_API_KEY: str
PERPLEXITY_API_KEY: str

# Optional
TMDB_API_KEY: Optional[str]
PERPLEXITY_USE_PRO: bool = False
MIN_CONFIDENCE_THRESHOLD: float = 0.90
EXCLUDE_MUSIC: bool = True
DRY_RUN: bool = False
UPDATE_IMAGES: bool = False
```

### Methods

#### `validate() -> bool`

Validate that required configuration is present.

**Returns**:
- `bool`: True if valid

**Raises**:
- `ValueError`: If required values are missing

**Example**:
```python
from src.config import Config

Config.validate()  # Raises if missing required values
```

---

## Common Use Cases

### Example 1: Process Entire Library

```python
from src.config import Config
from src.crawler import MetadataCrawler

# Configure
config = Config()
Config.validate()

# Run crawler
crawler = MetadataCrawler(config)
crawler.run()
```

---

### Example 2: Fix Specific Movie

```python
from src.config import Config
from src.crawler import MetadataCrawler

config = Config()
crawler = MetadataCrawler(config)

# Fix one movie
crawler.fix_single_item("76ec4e151dda47ab20ff280ea3e48ced")
```

---

### Example 3: Fix All Episodes in Series

```python
from src.config import Config
from src.crawler import MetadataCrawler

config = Config()
crawler = MetadataCrawler(config)

# Fix all episodes
crawler.fix_series_episodes("970488e781a9840f6e758a7469da13ef")
```

---

### Example 4: Custom TMDB Search

```python
from src.metadata_updater import MetadataUpdater

updater = MetadataUpdater(tmdb_api_key="your-key")

# Search for a movie
result = updater.search_tmdb("Inception", 2010, "movie")

# Get images
images = updater.get_image_urls(result)
print(images['Primary'])  # Poster URL
```

---

### Example 5: Validate Metadata

```python
from src.metadata_updater import MetadataUpdater
from src.metadata_validator import MetadataValidator

updater = MetadataUpdater(tmdb_api_key="your-key")
validator = MetadataValidator(updater)

# Validate an item
confidence, metadata = validator.validate_with_tmdb(
    item=jellyfin_item,
    path="/path/to/movie.mkv",
    item_type="Movie"
)

if confidence >= 0.90:
    print("High confidence - metadata is good")
else:
    print("Low confidence - needs update")
```

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 404 | Item/Resource Not Found |
| 401 | Unauthorized (invalid API key) |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |

---

Generated: 2025-10-18
Version: 1.0.0
