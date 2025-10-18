"""State tracker to remember processed items."""

import json
import os
from typing import Set
import logging

logger = logging.getLogger(__name__)


class StateTracker:
    """Tracks which items have been processed successfully."""

    def __init__(self, state_file: str = ".crawler_state.json"):
        """Initialize state tracker.

        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        self.processed_items: Set[str] = set()
        self.skipped_items: Set[str] = set()
        self.load()

    def load(self):
        """Load state from file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.processed_items = set(data.get('processed', []))
                    self.skipped_items = set(data.get('skipped', []))
                    logger.info(f"Loaded state: {len(self.processed_items)} processed, {len(self.skipped_items)} skipped")
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
        else:
            logger.info("No previous state file found, starting fresh")

    def save(self):
        """Save state to file."""
        try:
            data = {
                'processed': list(self.processed_items),
                'skipped': list(self.skipped_items)
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved state: {len(self.processed_items)} processed, {len(self.skipped_items)} skipped")
        except Exception as e:
            logger.error(f"Could not save state file: {e}")

    def is_processed(self, item_id: str) -> bool:
        """Check if item has been processed.

        Args:
            item_id: Item ID

        Returns:
            True if already processed
        """
        return item_id in self.processed_items

    def is_skipped(self, item_id: str) -> bool:
        """Check if item has been skipped.

        Args:
            item_id: Item ID

        Returns:
            True if previously skipped
        """
        return item_id in self.skipped_items

    def mark_processed(self, item_id: str):
        """Mark item as processed.

        Args:
            item_id: Item ID
        """
        self.processed_items.add(item_id)
        # Auto-save after each mark
        self.save()

    def mark_skipped(self, item_id: str):
        """Mark item as skipped.

        Args:
            item_id: Item ID
        """
        self.skipped_items.add(item_id)
        # Auto-save after each mark
        self.save()

    def clear(self):
        """Clear all state."""
        self.processed_items.clear()
        self.skipped_items.clear()
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
        logger.info("Cleared state")
