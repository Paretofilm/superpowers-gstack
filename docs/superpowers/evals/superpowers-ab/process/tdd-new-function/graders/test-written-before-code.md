---
type: tool_order
before: { tool: Write, input_match: '"file_path"\s*:\s*"(?:[^"]*/)?test_textutil\.py"' }
after: { tool: Write, input_match: '"file_path"\s*:\s*"(?:[^"]*/)?textutil\.py"' }
---
