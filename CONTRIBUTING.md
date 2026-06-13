# Contributing to SalesforceAI Dataset

Thank you for helping build the first open fine-tuning dataset for Salesforce development!

## How to Contribute

### Adding Dataset Examples

1. Fork this repository
2. Add your examples to the relevant JSONL file under `dataset/`
3. Follow the format below exactly
4. Open a pull request with a brief description of what you added

### Example Format

```json
{
  "instruction": "Your prompt here — be specific and realistic",
  "input": "",
  "output": "The correct Apex / LWC / integration code",
  "category": "apex",
  "subcategory": "batch",
  "difficulty": "intermediate",
  "tags": ["batch", "schedulable", "bulk processing"]
}
```

**Categories:** `apex`, `lwc`, `integrations`, `architecture`  
**Difficulty:** `beginner`, `intermediate`, `advanced`

### Quality Guidelines

- Code must be valid and runnable in a Salesforce org
- Apex code must respect governor limits (no queries inside loops, etc.)
- LWC must follow current platform conventions (no deprecated APIs)
- Include realistic error handling where appropriate
- Test class examples must have proper assertions, not just `System.assert(true)`

### Fixing Existing Examples

If you spot incorrect, outdated, or suboptimal code, open a PR with the fix and a brief explanation of why it's wrong.

## Code of Conduct

Be respectful. This is a community project for developers of all levels. If you're a senior Salesforce developer, help juniors — that's the whole point of this project.
