#!/usr/bin/env python3
"""Test to find valid user and proper endpoints."""

import requests
from src.config import Config

Config.validate()

base_url = Config.JELLYFIN_URL.rstrip('/')
api_key = Config.JELLYFIN_API_KEY
headers = {
    'X-Emby-Token': api_key,
    'Content-Type': 'application/json'
}

print("=" * 70)
print("FINDING USERS AND WORKING ENDPOINTS")
print("=" * 70)

# Get all users
print("\n[Step 1] List all users")
print("-" * 70)
try:
    response = requests.get(f"{base_url}/Users", headers=headers)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        users = response.json()
        print(f"✓ Found {len(users)} users:")
        for user in users:
            print(f"  - {user.get('Name')} (ID: {user.get('Id')})")
            print(f"    Admin: {user.get('Policy', {}).get('IsAdministrator', False)}")

        # Try with first user
        if users:
            test_user_id = users[0]['Id']
            print(f"\n[Step 2] Testing with user: {users[0]['Name']}")
            print("-" * 70)

            # Get sample item
            response = requests.get(f"{base_url}/Items", headers=headers, params={
                'Recursive': 'true',
                'Limit': 1,
                'IncludeItemTypes': 'Movie,Series'
            })

            if response.status_code == 200:
                items = response.json().get('Items', [])
                if items:
                    item_id = items[0]['Id']
                    item_name = items[0]['Name']
                    print(f"Sample item: {item_name} ({item_id})")

                    # Test GET with user
                    print(f"\n[Step 3] Testing GET endpoints with user context")
                    print("-" * 70)

                    test_get_urls = [
                        f"{base_url}/Users/{test_user_id}/Items/{item_id}",
                        f"{base_url}/Items/{item_id}?userId={test_user_id}",
                    ]

                    working_get = None
                    for url in test_get_urls:
                        print(f"\nTrying: {url}")
                        try:
                            r = requests.get(url, headers=headers)
                            print(f"  Status: {r.status_code}")
                            if r.status_code == 200:
                                print(f"  ✓ SUCCESS")
                                working_get = url
                                item_data = r.json()
                                break
                            else:
                                print(f"  ✗ Error: {r.text[:100]}")
                        except Exception as e:
                            print(f"  ✗ Exception: {e}")

                    if working_get:
                        print(f"\n✓ Working GET pattern found!")

                        # Now test UPDATE
                        print(f"\n[Step 4] Testing UPDATE endpoints")
                        print("-" * 70)

                        # Fetch item data first
                        r = requests.get(working_get, headers=headers)
                        current_item = r.json()

                        # Try different update methods
                        test_update_configs = [
                            {
                                'url': f"{base_url}/Items/{item_id}",
                                'method': 'POST',
                                'payload_type': 'full'
                            },
                            {
                                'url': f"{base_url}/Items/{item_id}?userId={test_user_id}",
                                'method': 'POST',
                                'payload_type': 'full'
                            },
                        ]

                        for config in test_update_configs:
                            print(f"\nTrying: {config['method']} {config['url']}")
                            try:
                                payload = current_item.copy()
                                # Make a small change
                                test_marker = " [TEST]"
                                original_overview = payload.get('Overview', '')

                                # Only proceed if we won't duplicate the marker
                                if test_marker not in original_overview:
                                    payload['Overview'] = original_overview + test_marker

                                    r = requests.post(config['url'], headers=headers, json=payload)
                                    print(f"  Status: {r.status_code}")

                                    if r.status_code in [200, 204]:
                                        print(f"  ✓ SUCCESS!")

                                        # Verify
                                        verify = requests.get(working_get, headers=headers)
                                        if verify.status_code == 200:
                                            verified = verify.json()
                                            if test_marker in verified.get('Overview', ''):
                                                print(f"  ✓ Update verified!")

                                                # Clean up - remove test marker
                                                payload['Overview'] = original_overview
                                                requests.post(config['url'], headers=headers, json=payload)
                                                print(f"  ✓ Cleaned up test marker")

                                                print(f"\n{'='*70}")
                                                print(f"SOLUTION FOUND!")
                                                print(f"{'='*70}")
                                                print(f"User ID: {test_user_id}")
                                                print(f"GET endpoint: {working_get}")
                                                print(f"UPDATE endpoint: {config['url']}")
                                                print(f"Method: {config['method']}")
                                                exit(0)
                                    else:
                                        print(f"  ✗ Error: {r.text[:200]}")

                            except Exception as e:
                                print(f"  ✗ Exception: {e}")

                        print("\n✗ No working UPDATE endpoint found")
                    else:
                        print("\n✗ Could not find working GET endpoint")
    else:
        print(f"✗ Error: {response.text}")

except Exception as e:
    print(f"✗ Exception: {e}")

print("\n" + "=" * 70)
print("Could not find working solution")
print("=" * 70)
