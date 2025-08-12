#!/usr/bin/env python3
"""
Debug script to test the exact backend logic with our data
"""

import json

def get_nested_value(data: dict, key: str):
    """Get value from nested dictionary using dot notation (e.g., 'translation.en')"""
    print(f"get_nested_value called with data={data}, key='{key}'")
    
    if '.' not in key:
        result = data.get(key)
        print(f"No dot in key, returning: {result}")
        return result
    
    keys = key.split('.')
    print(f"Split key into: {keys}")
    current = data
    
    for i, k in enumerate(keys):
        print(f"Step {i+1}: Looking for key '{k}' in {current}")
        if isinstance(current, dict) and k in current:
            current = current[k]
            print(f"Found '{k}', current value: {current}")
        else:
            print(f"Key '{k}' not found or current is not dict. Current type: {type(current)}")
            return None
    
    print(f"Final result: {current}")
    return current

def has_nested_key(data: dict, key: str) -> bool:
    """Check if nested key exists using dot notation"""
    result = get_nested_value(data, key) is not None
    print(f"has_nested_key('{key}') = {result}")
    return result

# Test with the exact data from our JSONL
test_cases = [
    {"translation": {"ffen": "Hello, how are you?", "bini": ""}, "id": "greeting_001", "category": "greetings"},
    {"translation": {"ffen": "What is your name?", "igbo": ""}, "id": "question_001", "category": "questions"}
]

print("Testing backend nested field access logic:")
print("=" * 50)

for i, test_data in enumerate(test_cases, 1):
    print(f"\nTest case {i}:")
    print(f"Data: {test_data}")
    print()
    
    # Test the problematic field
    field_key = "translation.ffen"
    print(f"Testing field: '{field_key}'")
    print("-" * 30)
    
    exists = has_nested_key(test_data, field_key)
    value = get_nested_value(test_data, field_key)
    
    print(f"\nSummary for test case {i}:")
    print(f"  Field exists: {exists}")
    print(f"  Field value: {value}")
    print("=" * 50)