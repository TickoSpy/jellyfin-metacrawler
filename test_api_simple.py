#!/usr/bin/env python3
"""Standalone test script for Jellyfin API."""

import requests
import os

# Load from .env file manually
env_vars = {}
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value

base_url = env_vars.get('JELLYFIN_URL', 'http://jellyfin.internal:8096').rstrip('/')
api_key = env_vars.get('JELLYFIN_API_KEY', '')

if not api_key:
    print("ERROR: JELLYFIN_API_KEY not found in .env file")
    exit(1)

headers = {
    'X-Emby-Token': api_key,
    'Content-Type': 'application/json'
}

print("=" * 70)
print("JELLYFIN API ENDPOINT FINDER")
print("=" * 70)
print(f"Base URL: {base_url}")
print(f"API Key: {api_key[:10]}...")
print()

# Step 1: Get users list
print("[Step 1] Fetching users list")
print("-" * 70)
try:
    response = requests.get(f"{base_url}/Users", headers=headers)
    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.text}")
        exit(1)

    users = response.json()
    print(f"✓ Found {len(users)} users:")

    user_id = None
    for user in users:
        name = user.get('Name')
        uid = user.get('Id')
        is_admin = user.get('Policy', {}).get('IsAdministrator', False)
        print(f"  - {name} (ID: {uid}, Admin: {is_admin})")

        # Use first admin user
        if is_admin and not user_id:
            user_id = uid
            print(f"    → Will use this user")

    if not user_id:
        # Use first user if no admin found
        user_id = users[0]['Id']
        print(f"\nNo admin found, using first user: {users[0]['Name']}")

    print(f"\nSelected User ID: {user_id}")

except Exception as e:
    print(f"✗ Exception: {e}")
    exit(1)

print()

# Step 2: Get a sample item
print("[Step 2] Fetching sample item")
print("-" * 70)
try:
    params = {
        'Recursive': 'true',
        'Limit': 1,
        'IncludeItemTypes': 'Series,Movie'
    }
    response = requests.get(f"{base_url}/Items", headers=headers, params=params)

    if response.status_code != 200:
        print(f"Error: {response.text}")
        exit(1)

    items = response.json().get('Items', [])
    if not items:
        print("No items found!")
        exit(1)

    sample_item = items[0]
    item_id = sample_item['Id']
    item_name = sample_item['Name']
    item_type = sample_item['Type']

    print(f"✓ Sample item: {item_name}")
    print(f"  ID: {item_id}")
    print(f"  Type: {item_type}")

except Exception as e:
    print(f"✗ Exception: {e}")
    exit(1)

print()

# Step 3: Test GET endpoints
print("[Step 3] Testing GET endpoints")
print("-" * 70)

get_endpoints = [
    f"/Users/{user_id}/Items/{item_id}",
    f"/Items/{item_id}?userId={user_id}",
]

working_get = None

for endpoint in get_endpoints:
    url = f"{base_url}{endpoint}"
    print(f"\nTrying GET: {endpoint}")

    try:
        response = requests.get(url, headers=headers)
        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            print(f"  ✓ SUCCESS")
            working_get = endpoint
            item_data = response.json()
            print(f"  Name: {item_data.get('Name')}")
            break
        else:
            print(f"  ✗ Error: {response.text[:100]}")

    except Exception as e:
        print(f"  ✗ Exception: {e}")

if not working_get:
    print("\n✗ No working GET endpoint found")
    exit(1)

print()

# Step 4: Test UPDATE endpoints
print("[Step 4] Testing UPDATE endpoints")
print("-" * 70)

# Fetch full item data
get_url = f"{base_url}{working_get}"
response = requests.get(get_url, headers=headers)
current_item = response.json()

update_configs = [
    f"/Items/{item_id}",
    f"/Items/{item_id}?userId={user_id}",
]

for endpoint in update_configs:
    url = f"{base_url}{endpoint}"
    print(f"\nTrying POST: {endpoint}")

    try:
        # Make payload with test change
        payload = current_item.copy()
        test_marker = " [API_TEST]"
        original_overview = payload.get('Overview', '')

        # Only test if marker not already there
        if test_marker in original_overview:
            print(f"  ⚠ Test marker already exists, skipping")
            continue

        payload['Overview'] = original_overview + test_marker

        response = requests.post(url, headers=headers, json=payload)
        print(f"  Status: {response.status_code}")

        if response.status_code in [200, 204]:
            print(f"  ✓ UPDATE SUCCESS!")

            # Verify the update
            verify_response = requests.get(get_url, headers=headers)
            if verify_response.status_code == 200:
                verified_item = verify_response.json()
                if test_marker in verified_item.get('Overview', ''):
                    print(f"  ✓ Update verified!")

                    # Clean up - remove test marker
                    payload['Overview'] = original_overview
                    cleanup_response = requests.post(url, headers=headers, json=payload)
                    print(f"  ✓ Cleaned up test marker")

                    print("\n" + "=" * 70)
                    print("✓✓✓ SOLUTION FOUND! ✓✓✓")
                    print("=" * 70)
                    print(f"User ID to use: {user_id}")
                    print(f"GET endpoint: {working_get}")
                    print(f"UPDATE endpoint: {endpoint}")
                    print(f"Method: POST")
                    print("=" * 70)
                    exit(0)
                else:
                    print(f"  ⚠ Update didn't apply correctly")
        else:
            print(f"  ✗ Error: {response.text[:200]}")

    except Exception as e:
        print(f"  ✗ Exception: {e}")

print("\n" + "=" * 70)
print("✗ Could not find working UPDATE endpoint")
print("=" * 70)
print("\nPossible issues:")
print("  - Metadata is locked on items")
print("  - API key lacks write permissions")
print("  - Jellyfin server configuration restricts updates")
