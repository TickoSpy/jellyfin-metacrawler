#!/usr/bin/env python3
"""Test script to diagnose Jellyfin API endpoints."""

import requests
import json
from src.config import Config

# Validate config
try:
    Config.validate()
except ValueError as e:
    print(f"Configuration error: {e}")
    exit(1)

base_url = Config.JELLYFIN_URL.rstrip('/')
api_key = Config.JELLYFIN_API_KEY
headers = {
    'X-Emby-Token': api_key,
    'Content-Type': 'application/json'
}

print("=" * 70)
print("JELLYFIN API DIAGNOSTIC TEST")
print("=" * 70)
print(f"Base URL: {base_url}")
print(f"API Key: {api_key[:10]}...")
print()

# Test 1: Get system info
print("[Test 1] System Info")
print("-" * 70)
try:
    response = requests.get(f"{base_url}/System/Info", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        info = response.json()
        print(f"✓ Server Name: {info.get('ServerName')}")
        print(f"✓ Version: {info.get('Version')}")
    else:
        print(f"✗ Error: {response.text}")
except Exception as e:
    print(f"✗ Exception: {e}")
print()

# Test 2: Get current user
print("[Test 2] Current User Info")
print("-" * 70)
user_id = None
try:
    response = requests.get(f"{base_url}/Users/Me", headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        user = response.json()
        user_id = user.get('Id')
        print(f"✓ User Name: {user.get('Name')}")
        print(f"✓ User ID: {user_id}")
        print(f"✓ Is Admin: {user.get('Policy', {}).get('IsAdministrator', False)}")
    else:
        print(f"✗ Error: {response.text}")
except Exception as e:
    print(f"✗ Exception: {e}")
print()

# Test 3: Get items
print("[Test 3] Fetch Items")
print("-" * 70)
sample_item = None
try:
    params = {
        'Recursive': 'true',
        'Fields': 'Path,ProviderIds,Overview,Genres,ProductionYear',
        'IncludeItemTypes': 'Movie,Series,Episode',
        'Limit': 5
    }
    response = requests.get(f"{base_url}/Items", headers=headers, params=params)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        items = data.get('Items', [])
        print(f"✓ Total items available: {data.get('TotalRecordCount')}")
        print(f"✓ Fetched {len(items)} sample items")
        if items:
            sample_item = items[0]
            print(f"\nSample item:")
            print(f"  ID: {sample_item.get('Id')}")
            print(f"  Name: {sample_item.get('Name')}")
            print(f"  Type: {sample_item.get('Type')}")
            print(f"  Path: {sample_item.get('Path', 'N/A')}")
    else:
        print(f"✗ Error: {response.text}")
except Exception as e:
    print(f"✗ Exception: {e}")
print()

if not sample_item:
    print("Cannot continue tests - no sample item available")
    exit(1)

item_id = sample_item['Id']

# Test 4: Get item by ID (various methods)
print("[Test 4] Get Item By ID (Testing Multiple Endpoints)")
print("-" * 70)

endpoints_to_test = [
    f"/Items/{item_id}",
    f"/Users/{user_id}/Items/{item_id}" if user_id else None,
    f"/Library/Items/{item_id}",
]

working_get_endpoint = None

for endpoint in endpoints_to_test:
    if endpoint is None:
        continue

    try:
        url = f"{base_url}{endpoint}"
        print(f"\nTrying: {endpoint}")
        response = requests.get(url, headers=headers)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            print(f"  ✓ SUCCESS")
            working_get_endpoint = endpoint
            item_data = response.json()
            print(f"  Name: {item_data.get('Name')}")
            print(f"  Type: {item_data.get('Type')}")
            break
        else:
            print(f"  ✗ Failed: {response.text[:100]}")
    except Exception as e:
        print(f"  ✗ Exception: {e}")

print()

if not working_get_endpoint:
    print("✗ Could not find working endpoint to fetch item by ID")
    exit(1)

# Test 5: Try updating metadata (various methods)
print("[Test 5] Update Metadata (Testing Multiple Endpoints)")
print("-" * 70)

# Prepare test metadata update
test_metadata = {
    'Name': sample_item.get('Name'),  # Keep same name
    'Overview': sample_item.get('Overview', '') + ' [Test marker]'
}

update_endpoints = [
    (f"/Items/{item_id}", "POST", "full_item"),
    (f"/Library/Items/{item_id}", "POST", "full_item"),
    (f"/Items/{item_id}/MetadataEditor", "POST", "metadata_only"),
]

working_update_endpoint = None

for endpoint, method, payload_type in update_endpoints:
    try:
        url = f"{base_url}{endpoint}"
        print(f"\nTrying: {method} {endpoint}")
        print(f"  Payload type: {payload_type}")

        # Prepare payload
        if payload_type == "full_item":
            # Get full item first
            get_url = f"{base_url}{working_get_endpoint}"
            get_response = requests.get(get_url, headers=headers)
            if get_response.status_code == 200:
                payload = get_response.json()
                payload.update(test_metadata)
            else:
                print(f"  ✗ Could not fetch item for full update")
                continue
        else:
            payload = test_metadata

        # Try update
        if method == "POST":
            response = requests.post(url, headers=headers, json=payload)

        print(f"  Status: {response.status_code}")

        if response.status_code in [200, 204]:
            print(f"  ✓ SUCCESS")
            working_update_endpoint = endpoint

            # Verify the update
            verify_url = f"{base_url}{working_get_endpoint}"
            verify_response = requests.get(verify_url, headers=headers)
            if verify_response.status_code == 200:
                updated_item = verify_response.json()
                if '[Test marker]' in updated_item.get('Overview', ''):
                    print(f"  ✓ Update verified!")
                else:
                    print(f"  ⚠ Update may not have applied")

            break
        else:
            print(f"  ✗ Failed: {response.text[:200]}")

    except Exception as e:
        print(f"  ✗ Exception: {e}")

print()

# Test 6: Check if metadata is locked
print("[Test 6] Check Metadata Lock Status")
print("-" * 70)
try:
    url = f"{base_url}{working_get_endpoint}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        item = response.json()
        locked_fields = item.get('LockedFields', [])
        if locked_fields:
            print(f"⚠ Item has locked fields: {locked_fields}")
        else:
            print(f"✓ No locked fields")

        lock_data = item.get('LockData', False)
        print(f"Lock Data: {lock_data}")
except Exception as e:
    print(f"✗ Exception: {e}")
print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"User ID: {user_id or 'NOT FOUND'}")
print(f"Working GET endpoint: {working_get_endpoint or 'NONE'}")
print(f"Working UPDATE endpoint: {working_update_endpoint or 'NONE'}")
print()

if working_update_endpoint:
    print("✓ Metadata updates should work!")
    print(f"\nRecommended configuration:")
    print(f"  - GET: {working_get_endpoint}")
    print(f"  - UPDATE: {working_update_endpoint}")
else:
    print("✗ Could not find working update endpoint")
    print("\nPossible issues:")
    print("  - API key lacks write permissions")
    print("  - Items have locked metadata")
    print("  - Jellyfin version incompatibility")

print("=" * 70)
