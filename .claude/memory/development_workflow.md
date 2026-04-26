---
name: development_workflow
description: Development workflow and error prevention
type: feedback
---

**Rule**: When making file edits, use a 3-step test method to prevent error loops:

1. **Read the file first** - Use `cat /path/to/file | grep -n "search_string"` to see the exact content
2. **Check exact content with `od -c`** - Use `cat /path/to/file | sed -n 'line_start,line_end' | od -c` to see special characters
3. **If the string doesn't match exactly, use a different approach**:
   - Use `sed` for simple replacements
   - Use `awk` for complex replacements
   - Or write the entire file with the correct content

**Why:** This prevents error loops and ensures the file is correct the first time.

**How to apply:** When making file edits, always use this 3-step method to verify the exact content before making changes.
