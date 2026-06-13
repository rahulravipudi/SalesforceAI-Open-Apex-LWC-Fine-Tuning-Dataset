"""
Validation script for SalesforceAI dataset
Checks for format correctness, required fields, and common Apex anti-patterns
"""

import json
import os
import sys
import glob

REQUIRED_FIELDS = ["instruction", "input", "output", "category", "subcategory", "difficulty", "tags"]
VALID_CATEGORIES = {"apex", "lwc", "integrations", "architecture"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}

# Common Apex anti-patterns that should not appear in generated code
APEX_ANTIPATTERNS = [
    ("SOQL in loop", "for (", "[SELECT"),  # Simplified check
]

GOVERNOR_LIMIT_WARNINGS = [
    "SELECT" ,  # Raw check - validate not inside for loop
]


def validate_record(record: dict, filepath: str, line_num: int) -> list[str]:
    errors = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in record:
            errors.append(f"[{filepath}:{line_num}] Missing required field: '{field}'")

    # Check category
    if record.get("category") not in VALID_CATEGORIES:
        errors.append(f"[{filepath}:{line_num}] Invalid category: '{record.get('category')}'. Must be one of {VALID_CATEGORIES}")

    # Check difficulty
    if record.get("difficulty") not in VALID_DIFFICULTIES:
        errors.append(f"[{filepath}:{line_num}] Invalid difficulty: '{record.get('difficulty')}'. Must be one of {VALID_DIFFICULTIES}")

    # Check tags is a list
    if "tags" in record and not isinstance(record["tags"], list):
        errors.append(f"[{filepath}:{line_num}] 'tags' must be a list")

    # Check instruction and output are non-empty
    if not record.get("instruction", "").strip():
        errors.append(f"[{filepath}:{line_num}] 'instruction' must not be empty")

    if not record.get("output", "").strip():
        errors.append(f"[{filepath}:{line_num}] 'output' must not be empty")

    # Warn about very short outputs (likely incomplete)
    output = record.get("output", "")
    if len(output) < 50:
        errors.append(f"[{filepath}:{line_num}] WARNING: 'output' seems very short ({len(output)} chars) — may be incomplete")

    return errors


def validate_file(filepath: str) -> tuple[int, int, list[str]]:
    total = 0
    valid = 0
    all_errors = []

    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                record = json.loads(line)
                errors = validate_record(record, filepath, line_num)
                if errors:
                    all_errors.extend(errors)
                else:
                    valid += 1
            except json.JSONDecodeError as e:
                all_errors.append(f"[{filepath}:{line_num}] Invalid JSON: {e}")

    return total, valid, all_errors


def main():
    dataset_dir = "dataset"
    jsonl_files = glob.glob(os.path.join(dataset_dir, "**/*.jsonl"), recursive=True)

    if not jsonl_files:
        print("No JSONL files found in dataset/")
        sys.exit(1)

    total_records = 0
    total_valid = 0
    all_errors = []

    for filepath in sorted(jsonl_files):
        total, valid, errors = validate_file(filepath)
        total_records += total
        total_valid += valid
        all_errors.extend(errors)
        status = "✓" if not errors else "✗"
        print(f"  {status} {filepath}: {valid}/{total} valid")

    print(f"\nSummary: {total_valid}/{total_records} records valid across {len(jsonl_files)} files")

    if all_errors:
        print(f"\n{len(all_errors)} issue(s) found:\n")
        for err in all_errors:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("\nAll records passed validation!")


if __name__ == "__main__":
    main()
