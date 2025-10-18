# Security Guidelines

## Sensitive Data Protection

This repository has been configured to protect sensitive information:

### Protected Files (Never Committed)

The following files are excluded via `.gitignore`:

- `.env` - Contains real API keys and credentials
- `.env.local` - Local environment overrides
- `.crawler_state.json` - May contain server-specific paths
- `.claude/settings.local.json` - Local Claude Code settings
- `venv/` - Virtual environment
- `__pycache__/` - Python cache files
- `*.pem`, `*.key` - Private keys
- `credentials.json`, `secrets.json` - Credential files

### Safe to Commit

- `.env.example` - Template with placeholder values
- All source code in `src/`
- Documentation files (`*.md`)
- Test files
- `requirements.txt`

## API Keys

This project requires the following API keys:

1. **Jellyfin API Key**
   - Used to: Access Jellyfin server for reading/updating metadata
   - Obtain from: Jellyfin Dashboard → API Keys
   - Stored in: `.env` file (NOT committed)

2. **Perplexity API Key**
   - Used to: AI-powered media identification
   - Obtain from: https://www.perplexity.ai/
   - Stored in: `.env` file (NOT committed)

3. **TMDB API Key** (Optional)
   - Used to: Fetch metadata and images from TMDB
   - Obtain from: https://www.themoviedb.org/settings/api
   - Stored in: `.env` file (NOT committed)

## Setup Instructions

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and replace placeholder values with your actual API keys

3. **NEVER** commit the `.env` file to version control

4. Verify `.env` is ignored:
   ```bash
   git status --ignored | grep .env
   ```

## Before Sharing Code

If you fork or share this repository:

1. Ensure `.env` is in `.gitignore`
2. Never include real API keys in any committed files
3. Use `.env.example` with placeholder values only
4. Remove any server-specific hostnames or usernames from documentation
5. Check commit history for accidentally committed secrets:
   ```bash
   git log --all --full-history --source -- .env
   ```

## Accidental Commit Recovery

If you accidentally commit sensitive data:

1. **Do NOT push** to remote repository
2. Remove the file from git history:
   ```bash
   git rm --cached .env
   git commit --amend -m "Remove sensitive file"
   ```
3. If already pushed, consider the API keys compromised and regenerate them
4. Use `git filter-branch` or `BFG Repo-Cleaner` for complete removal from history

## Reporting Security Issues

If you discover a security vulnerability, please:
- Do NOT open a public issue
- Contact the maintainer directly
- Provide details about the vulnerability
- Allow time for a fix before public disclosure

## Best Practices

1. **Rotate API Keys Regularly**: Change API keys periodically
2. **Use Read-Only Keys When Possible**: Limit API key permissions
3. **Monitor API Usage**: Watch for unusual activity
4. **Local Development Only**: Never use production keys in development
5. **Environment Separation**: Use different keys for different environments

## Compliance

This project handles:
- API credentials (must be protected)
- Server URLs (may contain internal hostnames)
- File paths (may contain usernames)

Ensure compliance with your organization's security policies when deploying.

---

Last Updated: 2025-10-18
