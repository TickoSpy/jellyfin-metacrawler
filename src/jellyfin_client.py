"""Jellyfin API client for fetching and updating media metadata."""

import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Client for interacting with Jellyfin API."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize Jellyfin client.

        Args:
            base_url: Base URL of the Jellyfin server
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'X-Emby-Token': api_key,
            'Content-Type': 'application/json'
        }
        self.user_id = None
        self._get_user_id()

    def _get_user_id(self):
        """Get the user ID by fetching the users list and using first admin."""
        try:
            # Try Users/Me first
            url = f"{self.base_url}/Users/Me"
            response = requests.get(url, headers=self.headers)

            if response.status_code == 200:
                user_data = response.json()
                self.user_id = user_data.get('Id')
                logger.info(f"Authenticated as user: {user_data.get('Name')} (ID: {self.user_id})")
                return

            # If that fails, get users list and use first admin
            logger.info("Users/Me not available, fetching users list...")
            url = f"{self.base_url}/Users"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            users = response.json()
            # Find first admin user
            for user in users:
                if user.get('Policy', {}).get('IsAdministrator', False):
                    self.user_id = user.get('Id')
                    logger.info(f"Using admin user: {user.get('Name')} (ID: {self.user_id})")
                    return

            # If no admin, use first user
            if users:
                self.user_id = users[0].get('Id')
                logger.info(f"Using first user: {users[0].get('Name')} (ID: {self.user_id})")

        except Exception as e:
            logger.warning(f"Could not get user ID: {e}")
            # Continue without user ID - some endpoints might still work

    def get_all_items(self, exclude_music: bool = True) -> List[Dict]:
        """Get all media items from Jellyfin.

        Args:
            exclude_music: Whether to exclude music items

        Returns:
            List of media items
        """
        url = f"{self.base_url}/Items"
        params = {
            'Recursive': 'true',
            'Fields': 'Path,ProviderIds,Overview,Genres,Studios,Tags,ProductionYear,PremiereDate,CommunityRating,CriticRating',
        }

        if exclude_music:
            params['IncludeItemTypes'] = 'Movie,Series,Season,Episode'
        else:
            params['IncludeItemTypes'] = 'Movie,Series,Season,Episode,Audio,MusicAlbum,MusicArtist'

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get('Items', [])
            logger.info(f"Retrieved {len(items)} items from Jellyfin")
            return items
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching items from Jellyfin: {e}")
            raise

    def get_series_info(self, series_id: str) -> Optional[Dict]:
        """Get series information.

        Args:
            series_id: The series ID

        Returns:
            Series data or None
        """
        return self.get_item_by_id(series_id)

    def get_series_episodes(self, series_id: str) -> List[Dict]:
        """Get all episodes for a series.

        Args:
            series_id: The series ID

        Returns:
            List of episode items
        """
        url = f"{self.base_url}/Shows/{series_id}/Episodes"
        params = {
            'Fields': 'Path,ProviderIds,Overview,Genres,ProductionYear,PremiereDate,CommunityRating',
            'UserId': self.user_id
        }

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            episodes = data.get('Items', [])
            logger.info(f"Retrieved {len(episodes)} episodes for series {series_id}")
            return episodes
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching episodes for series {series_id}: {e}")
            return []

    def get_item_by_id(self, item_id: str) -> Optional[Dict]:
        """Get a specific item by ID.

        Args:
            item_id: The Jellyfin item ID

        Returns:
            Item data or None
        """
        # Try with user-specific endpoint first
        if self.user_id:
            url = f"{self.base_url}/Users/{self.user_id}/Items/{item_id}"
        else:
            url = f"{self.base_url}/Items/{item_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code != 200:
                logger.error(f"Jellyfin API error for item {item_id}: {response.status_code}")
                logger.error(f"URL: {url}")
                logger.error(f"Response: {response.text}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Jellyfin HTTP error fetching item {item_id}: {e}")
            logger.error(f"Status code: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Jellyfin request error fetching item {item_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching item {item_id}: {e}", exc_info=True)
            return None

    def update_item_metadata(self, item_id: str, metadata: Dict) -> bool:
        """Update metadata for a specific item.

        Args:
            item_id: The Jellyfin item ID
            metadata: Dictionary containing metadata fields to update

        Returns:
            True if successful, False otherwise
        """
        # Use the simple /Items/{item_id} endpoint for updates
        url = f"{self.base_url}/Items/{item_id}"

        try:
            # Get current item data
            current_item = self.get_item_by_id(item_id)
            if not current_item:
                logger.error(f"Could not fetch item {item_id} for update")
                return False

            # Log current and new names for debugging
            logger.info(f"Current Name: {current_item.get('Name')}")
            logger.info(f"New Name: {metadata.get('Name')}")
            logger.info(f"Locked Fields: {current_item.get('LockedFields', [])}")

            # Merge current data with new metadata
            payload = current_item.copy()
            payload.update(metadata)

            # Log what we're updating
            logger.debug(f"Updating item {item_id} with metadata keys: {list(metadata.keys())}")
            logger.info(f"Payload Name after merge: {payload.get('Name')}")

            # POST to update
            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code not in [200, 204]:
                logger.error(f"Jellyfin update error for item {item_id}: {response.status_code}")
                logger.error(f"URL: {url}")
                logger.error(f"Metadata fields: {list(metadata.keys())}")
                logger.error(f"Response: {response.text}")

            response.raise_for_status()
            logger.info(f"Updated metadata for item {item_id}")
            return True

        except requests.exceptions.HTTPError as e:
            logger.error(f"Jellyfin HTTP error updating item {item_id}: {e}")
            logger.error(f"Status code: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Jellyfin request error updating item {item_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating item {item_id}: {e}", exc_info=True)
            return False

    def update_item_images(self, item_id: str, image_url: str, image_type: str = 'Primary') -> bool:
        """Update item image from URL.

        Args:
            item_id: The Jellyfin item ID
            image_url: URL of the new image
            image_type: Type of image (Primary, Backdrop, Logo, etc.)

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/Items/{item_id}/RemoteImages/Download"
        params = {
            'Type': image_type,
            'ImageUrl': image_url
        }

        try:
            response = requests.post(url, headers=self.headers, params=params)

            if response.status_code not in [200, 204]:
                logger.error(f"Jellyfin image update error for item {item_id}: {response.status_code}")
                logger.error(f"URL: {url}")
                logger.error(f"Image URL: {image_url}")
                logger.error(f"Response: {response.text}")

            response.raise_for_status()
            logger.info(f"Updated {image_type} image for item {item_id}")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Jellyfin HTTP error updating image for item {item_id}: {e}")
            logger.error(f"Status code: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Jellyfin request error updating image for item {item_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating image for item {item_id}: {e}", exc_info=True)
            return False

    def refresh_metadata(self, item_id: str) -> bool:
        """Trigger metadata refresh for an item.

        Args:
            item_id: The Jellyfin item ID

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/Items/{item_id}/Refresh"
        params = {
            'Recursive': 'true',
            'MetadataRefreshMode': 'FullRefresh',
            'ImageRefreshMode': 'FullRefresh',
            'ReplaceAllMetadata': 'false',
            'ReplaceAllImages': 'false'
        }

        try:
            response = requests.post(url, headers=self.headers, params=params)
            response.raise_for_status()
            logger.info(f"Triggered metadata refresh for item {item_id}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error refreshing metadata for item {item_id}: {e}")
            return False
