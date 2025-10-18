# Jellyfin Metadata Crawler

An intelligent metadata crawler for Jellyfin that uses Perplexity AI to automatically identify and fix incorrect or missing metadata for your movies and TV shows.

## Features

- Automatically analyzes all media items in your Jellyfin library
- Uses fuzzy matching and confidence scoring to identify problematic metadata
- Leverages Perplexity AI Pro to intelligently identify media from filenames
- Falls back to TMDB for additional metadata and high-quality images
- Updates titles, descriptions, years, genres, and images
- Excludes music libraries by default
- Dry-run mode for safe testing
- Configurable confidence threshold (default: 90%)

## How It Works

1. **Fetch**: Retrieves all media items from your Jellyfin server
2. **Analyze**: Scores each item's metadata confidence by comparing:
   - Filename vs current title (fuzzy matching)
   - Year in filename vs metadata year
   - Presence of provider IDs (IMDb, TMDB)
   - Quality of overview/description
   - Presence of poster images
3. **Identify**: For items below the confidence threshold:
   - Uses Perplexity AI to identify the correct media
   - Searches TMDB for additional metadata if needed
4. **Update**: Applies the corrected metadata and images to Jellyfin

## Requirements

- Python 3.7+
- Jellyfin server with API access
- Perplexity AI Pro API key
- (Optional) TMDB API key for enhanced metadata

## Installation

1. Clone or download this repository:
```bash
git clone <repository-url>
cd jellyfin-metacrawler
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy the example environment file and configure it:
```bash
cp .env.example .env
```

4. Edit `.env` and add your API keys:
   - `JELLYFIN_URL`: Your Jellyfin server URL (e.g., http://localhost:8096)
   - `JELLYFIN_API_KEY`: Your Jellyfin API key
   - `PERPLEXITY_API_KEY`: Your Perplexity AI API key
   - `TMDB_API_KEY`: (Optional) Your TMDB API key

### Getting API Keys

#### Jellyfin API Key
1. Log into your Jellyfin web interface
2. Go to Dashboard → API Keys
3. Click "+" to create a new API key
4. Copy the key to your `.env` file

#### Perplexity API Key
1. Go to https://www.perplexity.ai/
2. Sign in to your Pro account
3. Navigate to API settings
4. Generate an API key

#### TMDB API Key (Optional)
1. Go to https://www.themoviedb.org/
2. Create an account and verify your email
3. Go to Settings → API
4. Request an API key (choose "Developer" option)

## Usage

### Basic Usage

Run the crawler with default settings:
```bash
python main.py
```

### Dry Run Mode

Test without making any changes:
```bash
python main.py --dry-run
```

### Custom Confidence Threshold

Set a different threshold (0.0 to 1.0):
```bash
python main.py --threshold 0.85
```

### Include Music

By default, music is excluded. To include music items:
```bash
python main.py --include-music
```

### Combined Options

```bash
python main.py --dry-run --threshold 0.80
```

## Configuration

Edit the `.env` file to customize behavior:

- `MIN_CONFIDENCE_THRESHOLD`: Minimum confidence score (default: 0.90)
  - Items scoring below this will be updated
  - Lower values = fewer updates, higher values = more updates
- `EXCLUDE_MUSIC`: Skip music libraries (default: true)
- `DRY_RUN`: Run without making changes (default: false)

## Output

The crawler provides detailed logging including:
- Items processed and analyzed
- Confidence scores for each item
- Metadata changes being made
- Final summary statistics

Example output:
```
2025-10-17 20:45:00 - crawler - INFO - Starting Jellyfin metadata crawler
2025-10-17 20:45:00 - crawler - INFO - Confidence threshold: 0.90
2025-10-17 20:45:01 - crawler - INFO - Found 150 items

--- Processing item 1/150 ---
2025-10-17 20:45:02 - crawler - INFO - Item: Some.Movie.2023.1080p (Movie)
2025-10-17 20:45:02 - crawler - INFO - Confidence score: 0.65
2025-10-17 20:45:03 - crawler - INFO - Perplexity identified as: Some Movie (2023)
2025-10-17 20:45:04 - crawler - INFO - Successfully updated metadata

============================================================
CRAWLER SUMMARY
============================================================
Total items: 150
Analyzed: 150
Needed update: 23
Updated: 22
Skipped: 0
Errors: 1
============================================================
```

## Project Structure

```
jellyfin-metacrawler/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── jellyfin_client.py        # Jellyfin API client
│   ├── perplexity_client.py      # Perplexity AI integration
│   ├── metadata_analyzer.py      # Confidence scoring
│   ├── metadata_updater.py       # TMDB integration
│   └── crawler.py                # Main orchestration logic
├── main.py                       # Entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Example configuration
├── .gitignore
└── README.md                     # This file
```

## Troubleshooting

### API Rate Limits

If you encounter rate limiting:
- The crawler includes 1-second delays between items
- Consider running on smaller batches
- Check your Perplexity AI usage limits

### Authentication Errors

If you get authentication errors:
- Verify your API keys are correct in `.env`
- Ensure your Jellyfin API key has proper permissions
- Check that your Perplexity API key is active

### Low Confidence Scores

If too many items are being flagged:
- Lower the threshold: `--threshold 0.80`
- Check your filenames are reasonably formatted
- Review the analysis details in the logs

### No Updates Happening

If nothing is being updated:
- Remove `DRY_RUN=true` from `.env` or don't use `--dry-run`
- Lower the confidence threshold
- Check the logs for specific errors

## Safety Features

- **Dry-run mode**: Test before making changes
- **Confidence scoring**: Only updates items that likely need it
- **Detailed logging**: Full transparency of all actions
- **API key validation**: Checks configuration before starting
- **Music exclusion**: Protects music libraries by default
- **Incremental updates**: Processes items one at a time

## Contributing

Feel free to open issues or submit pull requests for improvements.

## License

This project is provided as-is for personal use.
