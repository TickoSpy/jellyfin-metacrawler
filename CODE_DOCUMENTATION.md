# Jellyfin Metadata Crawler - Code Documentation

## Overview

The Jellyfin Metadata Crawler is an intelligent automation tool that improves metadata quality in Jellyfin media libraries. It combines multiple data sources (TMDB, Perplexity AI) with smart validation logic to fix incorrect or missing metadata.

## Architecture

### High-Level Design

```
┌─────────────────┐
│  main.py (CLI)  │
└────────┬────────┘
         │
         v
┌──────────────────────────┐
│   MetadataCrawler        │  ← Main orchestrator
│  (src/crawler.py)        │
└────┬──────────────┬──────┘
     │              │
     v              v
┌────────────┐  ┌────────────────┐
│ Jellyfin   │  │ Metadata       │
│ Client     │  │ Analyzer       │
└─────┬──────┘  └────────┬───────┘
      │                  │
      v                  v
┌─────────────┐  ┌────────────────┐
│ TMDB        │  │ Perplexity AI  │
│ Validator   │  │ Client         │
└──────┬──────┘  └────────┬───────┘
       │                  │
       v                  v
┌──────────────────────────┐
│   Metadata Updater       │
│   (TMDB API Client)      │
└──────────────────────────┘
```

### Core Components

#### 1. **MetadataCrawler** (`src/crawler.py`)
**Purpose**: Main orchestration engine

**Key Responsibilities**:
- Coordinates all metadata improvement workflows
- Implements waterfall validation approach (local → TMDB → Perplexity)
- Manages state tracking for resume capability
- Handles batch and single-item processing

**Key Methods**:
- `run()`: Process entire library
- `fix_single_item(item_id)`: Fix specific movie/episode
- `fix_series_episodes(series_id)`: Fix all episodes in a series
- `_process_item(item, force_update)`: Core processing logic

**Workflow**:
```
1. Check state (skip if already processed)
2. Analyze local metadata quality
3. Validate with TMDB (free, fast)
4. Use Perplexity AI if needed (paid, advanced)
5. Enrich Perplexity results with TMDB data
6. Apply metadata to Jellyfin
7. Update state tracking
```

#### 2. **MetadataUpdater** (`src/metadata_updater.py`)
**Purpose**: TMDB API client with intelligent caching

**Key Features**:
- **Smart Result Scoring**: Fuzzy title matching + year validation
- **Episode Caching**: Fetch all episodes once, cache for efficiency
- **Runtime Validation**: Prevent wrong movie matches
- **Logo Support**: Extract and provide logo images
- **Type Fallback**: Try both Movie and TV if first fails

**Key Methods**:
- `search_tmdb(title, year, media_type)`: Search and score results
- `fetch_tmdb_metadata(tmdb_id, media_type)`: Direct ID lookup
- `search_tmdb_episode(show_name, season, episode)`: Episode lookup with caching
- `_find_best_tmdb_match(results, query_title, query_year)`: Intelligent result selection

**Caching Strategy**:
```python
# Episode cache structure:
{
    "show name lower": {
        "show_id": 12345,
        "show_title": "Show Name",
        "episodes": {
            (1, 1): {metadata for S01E01},
            (1, 2): {metadata for S01E02},
            ...
        }
    }
}
```

**Scoring Algorithm** (for finding best TMDB match):
```python
score = 0

# Title similarity (0-100 from fuzzy matching)
score += fuzz.ratio(query_title, result_title)

# Exact title match bonus
if exact_match:
    score += 50

# Year matching
if query_year == result_year:
    score += 100  # Exact year
elif abs(query_year - result_year) <= 1:
    score += 50   # Close year
else:
    score -= 50   # Wrong year penalty

# Popularity factor (capped at 10 points)
score += min(popularity, 10)

# Return highest scoring result
```

#### 3. **MetadataValidator** (`src/metadata_validator.py`)
**Purpose**: Validate metadata against TMDB and file information

**Key Features**:
- **Intelligent Filename Parsing**: Uses GuessIt library
- **Runtime Validation**: ±10% or 10 minutes tolerance
- **Type Fallback**: Handles miscategorized items
- **Confidence Scoring**: Multi-factor validation

**Runtime Validation Rules**:
```python
file_runtime_minutes = file_runtime_ticks / 10000000 / 60
max_deviation = max(metadata_runtime * 0.1, 10)  # 10% or 10 min
deviation = abs(file_runtime - metadata_runtime)

if deviation <= max_deviation:
    return True, +0.1  # Good match, boost confidence
elif deviation <= max_deviation * 2:
    return True, -0.2  # Moderate mismatch, penalty
else:
    return False, -0.5  # Large mismatch, reject match
```

**Confidence Calculation**:
```python
# For movies:
confidence = (
    name_similarity * 0.6 +  # 60% weight on title
    year_match * 0.4         # 40% weight on year
) + runtime_adjustment

# For TV series:
confidence = (
    name_similarity * 0.8 +  # 80% weight on title
    year_match * 0.2         # 20% weight on year (less important)
)

# For episodes with S/E numbers:
confidence = (
    name_similarity * 0.9 +  # 90% weight on show name
    year_match * 0.1         # 10% weight on year
)
```

#### 4. **JellyfinClient** (`src/jellyfin_client.py`)
**Purpose**: Jellyfin API interaction layer

**Key Features**:
- Item fetching and filtering
- Metadata updates with field locking
- Image updates (poster, backdrop, logo)
- Series and episode management

**Field Locking**:
```python
# Lock metadata fields to prevent Jellyfin from overwriting
locked_fields = ['Name', 'Overview', 'Genres', 'OfficialRating',
                'Studios', 'Cast']
updated_item['LockedFields'] = locked_fields
```

#### 5. **PerplexityClient** (`src/perplexity_client.py`)
**Purpose**: AI-powered media identification

**Key Use Cases**:
- Obscure or foreign titles
- Ambiguous filenames
- Special characters (e.g., "Brüno" vs "Bruno")
- Complex filename patterns

**Model Selection**:
- `sonar`: Cost-effective for most cases
- `sonar-pro`: Higher accuracy for difficult cases

#### 6. **MetadataAnalyzer** (`src/metadata_analyzer.py`)
**Purpose**: Local metadata quality analysis

**Scoring Factors**:
```python
weights = {
    'filename_match': 0.35,     # Most important
    'year_match': 0.20,
    'provider_ids': 0.20,
    'overview_quality': 0.15,
    'has_image': 0.10
}

confidence = sum(score * weight for score, weight in zip(scores, weights))
```

#### 7. **FilenameParser** (`src/filename_parser.py`)
**Purpose**: Intelligent filename parsing using GuessIt

**Capabilities**:
- Extract title, year, season, episode from filenames
- Handle various naming conventions (S01E01, 1x01, etc.)
- Clean release group tags and quality markers
- Extract show names from directory structures

**Example**:
```python
# Input: "Toast.of.London.S03E02.1080p.WEB.H264-DiMEPiECE.mkv"
{
    'title': 'Toast of London',
    'season': 3,
    'episode': 2,
    'resolution': '1080p',
    'source': 'WEB',
    'video_codec': 'H264',
    'release_group': 'DiMEPiECE'
}
```

#### 8. **StateTracker** (`src/state_tracker.py`)
**Purpose**: Track processed items for resume capability

**Features**:
- Persistent state storage (`.crawler_state.json`)
- Skip already processed items
- Auto-save after each item
- Separate tracking for processed vs skipped items

## Data Flow

### Typical Processing Flow

```
1. CLI Arguments
   ↓
2. Initialize MetadataCrawler
   ↓
3. Fetch all items from Jellyfin
   ↓
4. For each item:
   ├─→ Check StateTracker (skip if processed)
   ├─→ MetadataAnalyzer: Calculate confidence
   ├─→ If confidence < threshold:
   │   ├─→ MetadataValidator: Validate with TMDB
   │   │   ├─→ FilenameParser: Parse filename
   │   │   ├─→ MetadataUpdater: Search TMDB
   │   │   └─→ Runtime validation (for movies)
   │   │
   │   ├─→ If TMDB insufficient:
   │   │   ├─→ PerplexityClient: AI identification
   │   │   └─→ MetadataUpdater: Enrich with TMDB data
   │   │
   │   └─→ JellyfinClient: Apply metadata
   │       ├─→ Update item metadata
   │       ├─→ Lock fields
   │       └─→ Update images
   │
   └─→ StateTracker: Mark as processed
```

## Configuration

### Environment Variables

```bash
# Required
JELLYFIN_URL=http://localhost:8096
JELLYFIN_API_KEY=your-jellyfin-api-key
PERPLEXITY_API_KEY=your-perplexity-key

# Optional
TMDB_API_KEY=your-tmdb-key
PERPLEXITY_USE_PRO=false
MIN_CONFIDENCE_THRESHOLD=0.90
EXCLUDE_MUSIC=true
DRY_RUN=false
UPDATE_IMAGES=false
```

## Key Features Implemented

### 1. **Intelligent Result Scoring**
Prevents common misidentification issues like:
- "Brüno" (2009 comedy) vs "Bruno" (2019 documentary)
- Wrong year matches
- Similar titles

### 2. **Runtime Validation**
Ensures movies match file duration:
```python
# Example: Reject if runtime differs by >20%
if file_runtime = 150 min and metadata_runtime = 102 min:
    rejection = True  # 47% difference
```

### 3. **Type Fallback**
Handles miscategorized items:
```python
# Try as Movie first
metadata = search_tmdb(title, year, 'movie')
if not metadata:
    # Fallback to TV
    metadata = search_tmdb(title, year, 'tv')
```

### 4. **Episode Caching**
Minimizes API calls for TV series:
```python
# Without caching: 6 episodes = 6 API calls
# With caching: 6 episodes = 1 API call (fetch all upfront)
```

### 5. **Field Locking**
Prevents Jellyfin from overwriting fixes:
```python
updated_item['LockedFields'] = [
    'Name', 'Overview', 'Genres', 'OfficialRating',
    'Studios', 'Cast'
]
```

### 6. **Logo Image Support**
Fetches show/movie logos from TMDB's images API

### 7. **State Tracking**
Resume capability after interruptions

## Testing

### Test Coverage

All features have been tested:

✅ `--fix-item` with Movie (Galaxy Quest)
✅ `--fix-item` with TV Episode (Police Squad S01E04)
✅ `--fix-series` with TV Series (Police Squad! - 6 episodes)
✅ Runtime validation (good match: +0.1 boost, large mismatch: rejection)
✅ Full crawler run (550 items processed)

### Test Results Summary

```
Total items: 550
Already processed: 515
Newly analyzed: 4
Validated with TMDB: 1
Used Perplexity: 1
Skipped: 31 (virtual items)
Errors: 1
```

## Performance Optimization

### API Call Optimization

1. **State Tracking**: Skip already processed items
2. **TMDB First**: Free API before paid Perplexity
3. **Episode Caching**: Batch fetch all episodes
4. **High Confidence Skip**: Don't validate if confidence >= 0.90

### Cost Savings

```
Example library (550 items):
- Without optimization: 550 Perplexity calls
- With optimization: 1 Perplexity call
- Savings: ~99.8%
```

## Error Handling

### Graceful Degradation

```python
try:
    # Try Perplexity
    metadata = perplexity.identify_media(...)
except:
    # Fall back to TMDB
    if tmdb_metadata:
        metadata = tmdb_metadata
```

### Logging Levels

- `DEBUG`: Detailed parsing and scoring information
- `INFO`: Processing progress and decisions
- `WARNING`: Mismatches and fallbacks
- `ERROR`: Failed operations (with stack traces)

## Future Improvements

### Potential Enhancements

1. **Parallel Processing**: Process items concurrently
2. **ML-based Confidence**: Train model on corrections
3. **User Feedback Loop**: Learn from manual fixes
4. **Additional Providers**: Support for TVDb, OMDb
5. **Web UI**: Visual interface for reviewing changes
6. **Backup/Restore**: Metadata snapshots before changes
7. **Change History**: Track all metadata modifications

## Contributing

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and returns
- Write comprehensive docstrings (Google/NumPy style)
- Add inline comments for complex logic
- Keep functions focused and single-purpose

### Documentation Standards

- Module-level docstrings with examples
- Class-level docstrings explaining purpose and attributes
- Method-level docstrings with Args, Returns, Raises
- Inline comments for non-obvious logic
- Real-world examples in docstrings

## License

See LICENSE file for details.

## Credits

- **TMDB**: The Movie Database (https://www.themoviedb.org/)
- **Perplexity AI**: Advanced AI search (https://www.perplexity.ai/)
- **GuessIt**: Intelligent filename parsing (https://github.com/guessit-io/guessit)
- **TheFuzz**: Fuzzy string matching (https://github.com/seatgeek/thefuzz)

---

Generated: 2025-10-18
Version: 1.0.0
