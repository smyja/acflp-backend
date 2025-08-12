#!/usr/bin/env python3
"""
Debug script to test nested field access in the bulk import functionality.
"""

import json

def get_nested_value(data: dict, key: str):
    """Get value from nested dictionary using dot notation (e.g., 'translation.en')"""
    if '.' not in key:
        return data.get(key)
    
    keys = key.split('.')
    current = data
    
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    
    return current

def has_nested_key(data: dict, key: str) -> bool:
    """Check if nested key exists using dot notation"""
    return get_nested_value(data, key) is not None

# Test data from your JSONL file
test_data = {
    "translation": {"ffen": "Where is the market?", "bini": ""}, 
    "id": "location_001", 
    "category": "directions"
}

print("Testing nested field access:")
print(f"Original data: {test_data}")
print()

# Test the nested access
field_key = "translation.ffen"
print(f"Testing key: '{field_key}'")
print(f"has_nested_key result: {has_nested_key(test_data, field_key)}")
print(f"get_nested_value result: {get_nested_value(test_data, field_key)}")
print()

# Test other fields
other_tests = ["id", "category", "translation.bini", "translation.nonexistent", "nonexistent.field"]
for test_key in other_tests:
    print(f"Key '{test_key}': exists={has_nested_key(test_data, test_key)}, value={get_nested_value(test_data, test_key)}")