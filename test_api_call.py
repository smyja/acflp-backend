#!/usr/bin/env python3
"""
Test script to debug the flexible bulk import API call with authentication
"""

import requests
import json

# Test data from the JSONL file
test_data = [
    {"translation": {"ffen": "Hello, how are you?", "bini": ""}, "id": "greeting_001", "category": "greetings"},
    {"translation": {"ffen": "What is your name?", "igbo": ""}, "id": "question_001", "category": "questions"}
]

# Create a temporary JSONL file content
jsonl_content = "\n".join([json.dumps(item) for item in test_data])

print("Testing API call to flexible bulk import with authentication...")
print(f"JSONL content:\n{jsonl_content}")
print()

# First, authenticate to get a token
auth_url = "http://localhost:8000/api/v1/login/access-token"
auth_data = {
    "username": "maro@acflp.org",
    "password": "changethis"
}

print("Step 1: Authenticating...")
try:
    auth_response = requests.post(auth_url, data=auth_data)
    print(f"Auth response status: {auth_response.status_code}")
    
    if auth_response.status_code == 200:
        token_data = auth_response.json()
        access_token = token_data["access_token"]
        print(f"Authentication successful! Token: {access_token[:20]}...")
        
        # Now test the bulk import with authentication
        print("\nStep 2: Testing bulk import...")
        
        url = "http://localhost:8000/api/v1/tasks/flexible-bulk-import-jsonl"
        
        # Create form data for file upload
        files = {
            'file': ('test.jsonl', jsonl_content, 'application/json')
        }
        
        # Parameters should be sent as query parameters
        params = {
            'content_field': 'translation.ffen',
            'title_field': 'id',
            'default_source_language': 'english',
            'default_target_language': 'bini',
            'default_task_type': 'text_translation',
            'default_reward_amount': 10
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        print(f"API URL: {url}")
        print(f"Query params: {params}")
        print(f"Headers: {headers}")
        print()
        
        # Make the API call with params as query parameters
        response = requests.post(url, files=files, params=params, headers=headers)
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response content: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nParsed response: {json.dumps(result, indent=2)}")
        else:
            print(f"\nError response: {response.text}")
    else:
        print(f"Authentication failed: {auth_response.text}")
        
except requests.exceptions.ConnectionError:
    print("Error: Could not connect to the backend. Make sure Docker containers are running.")
except Exception as e:
    print(f"Error: {e}")