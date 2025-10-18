#!/usr/bin/env python3
"""Clear the crawler state to reprocess all items."""

import os
import sys

state_file = ".crawler_state.json"

if os.path.exists(state_file):
    confirm = input(f"Are you sure you want to clear {state_file}? (yes/no): ")
    if confirm.lower() == 'yes':
        os.remove(state_file)
        print(f"✓ Cleared {state_file}")
        print("All items will be reprocessed on next run.")
    else:
        print("Cancelled.")
else:
    print(f"No state file found at {state_file}")
