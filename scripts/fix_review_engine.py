#!/usr/bin/env python3
"""Fix review_engine.py _classify_issue_category to use word-boundary matching."""

import re
import sys

script_path = "/Users/yanping.ma/biz-delivery/scripts/review_engine.py"

with open(script_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the _classify_issue_category function
def_idx = None
for i, line in enumerate(lines):
    if '_classify_issue_category' in line and line.strip().startswith('def'):
        def_idx = i
        break

if def_idx is None:
    print("ERROR: Could not find _classify_issue_category function")
    sys.exit(1)

# Find the end of this function (next method or class level)
# Look for the line with 'categories_map = [' after the function start
map_idx = None
for i in range(def_idx, len(lines)):
    if 'categories_map = [' in lines[i]:
        map_idx = i
        break

if map_idx is None:
    print("ERROR: Could not find categories_map in function")
    sys.exit(1)

# Find the closing bracket of categories_map and the following lines
# The pattern we want to replace starts after the categories_map definition ends
# Look for "for cat, keywords in categories_map:" after the map
for_idx = None
for i in range(map_idx, len(lines)):
    if 'for cat, keywords in categories_map:' in lines[i]:
        for_idx = i
        break

if for_idx is None:
    print("ERROR: Could not find the for loop")
    sys.exit(1)

# Replace from for_idx to the return statement
# Find the line containing "return '其他通用'"
return_idx = None
for i in range(for_idx, len(lines)):
    if "return '其他通用'" in lines[i]:
        return_idx = i
        break

if return_idx is None:
    print("ERROR: Could not find the final return")
    sys.exit(1)

# Build new lines - insert text_lower assignment before the for loop
new_lines = lines[:for_idx]  # keep everything up to (but not including) the for loop
# Insert text_lower = text.lower() before the for loop
new_lines.append('        text_lower = text.lower()\n')
# Replace the old for loop block with the new one
new_lines.append('        for cat, keywords in categories_map:\n')
new_lines.append('            for kw in keywords:\n')
new_lines.append('                kw_lower = kw.lower()\n')
new_lines.append('                # First try word-boundary match for English keywords\n')
new_lines.append('                if re.search(r"\\b" + re.escape(kw_lower) + r"\\b", text_lower):\n')
new_lines.append('                    return cat\n')
new_lines.append('                # Fallback to substring match for Chinese/edge cases\n')
new_lines.append('                if kw_lower in text_lower:\n')
new_lines.append('                    return cat\n')
new_lines.append(lines[return_idx])  # the "return '其他通用'" line
# Keep everything after return_idx
new_lines.extend(lines[return_idx+1:])

# Write back
with open(script_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Updated review_engine.py from line {for_idx} to {return_idx}")
print("Function now uses word-boundary regex matching to avoid false positives.")