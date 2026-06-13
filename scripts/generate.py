"""
Dataset generation pipeline for SalesforceAI
Uses OpenAI API to generate Apex / LWC prompt-response pairs
"""

import os
import json
import time
import argparse
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """You are an expert Salesforce developer with deep knowledge of:
- Apex (triggers, classes, batch jobs, queueable, test classes)
- Lightning Web Components (LWC) and Aura
- SOQL/SOSL and DML operations
- Salesforce governor limits and best practices
- Integration patterns (REST, SOAP, Platform Events)
- Salesforce architecture patterns (bulkification, separation of concerns)

When generating code examples:
1. Always respect governor limits (no SOQL/DML inside loops)
2. Follow Salesforce best practices
3. Write clean, readable, production-quality code
4. Include comments for complex logic
5. Return ONLY valid JSON, no markdown, no explanation outside the JSON."""

PROMPT_TEMPLATES = {
    "apex": [
        "Write an Apex trigger that {scenario}.",
        "Create an Apex batch class that {scenario}.",
        "Write an Apex class with a method that {scenario}.",
        "Write an Apex test class for a trigger that {scenario}.",
        "Create a Schedulable Apex class that {scenario}.",
        "Write a Queueable Apex class that {scenario}.",
    ],
    "lwc": [
        "Create an LWC component that {scenario}.",
        "Write an LWC component with a wire adapter that {scenario}.",
        "Build an LWC component that communicates with a parent component by {scenario}.",
        "Create an LWC component that calls an Apex method to {scenario}.",
    ],
    "integrations": [
        "Write an Apex REST callout class that {scenario}.",
        "Create a Platform Event publisher class that {scenario}.",
        "Write an Apex class that handles inbound REST requests to {scenario}.",
        "Create a Change Data Capture handler that {scenario}.",
    ],
    "architecture": [
        "Demonstrate the bulkification pattern in Apex for {scenario}.",
        "Show a separation of concerns pattern in Apex for {scenario}.",
        "Write an Apex implementation of the Service Layer pattern for {scenario}.",
        "Demonstrate the Selector pattern in Apex for {scenario}.",
    ],
}

SCENARIOS = {
    "apex": [
        "prevents duplicate Contact emails on insert and update",
        "auto-populates the Account's billing address onto related Contacts",
        "sends an email notification when an Opportunity stage changes to Closed Won",
        "processes large volumes of records with proper governor limit handling",
        "rolls up the count of closed Opportunities onto the Account",
        "validates that a Case cannot be closed without a resolution",
        "creates a follow-up Task when a Lead is converted",
        "enforces that Opportunity close date cannot be in the past",
    ],
    "lwc": [
        "displays a paginated list of Accounts with search functionality",
        "renders a custom data table with inline editing for Contacts",
        "shows a progress bar based on Opportunity stage",
        "lets users upload files and attach them to a record",
        "displays a toast notification on successful form submission",
    ],
    "integrations": [
        "retrieves weather data from a public REST API and stores it on a custom object",
        "sends Opportunity data to an external ERP system on stage change",
        "publishes order events to downstream systems when a contract is signed",
        "syncs Contact updates from Salesforce to an external marketing platform",
    ],
    "architecture": [
        "updating Account records from multiple triggers",
        "managing Opportunity-related business logic across multiple objects",
        "querying and processing large datasets efficiently",
        "handling complex validation rules across related objects",
    ],
}


def generate_example(category: str, template: str, scenario: str) -> dict | None:
    prompt = template.format(scenario=scenario)
    user_message = f"""Generate a Salesforce dataset example for this task:

"{prompt}"

Return ONLY a JSON object with this exact structure:
{{
  "instruction": "{prompt}",
  "input": "",
  "output": "<the complete, correct Salesforce code here>",
  "category": "{category}",
  "subcategory": "<specific subcategory>",
  "difficulty": "<beginner|intermediate|advanced>",
  "tags": ["<tag1>", "<tag2>"]
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  Error: {e}")
        return None


def generate_dataset(category: str, count: int, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{category}.jsonl")
    templates = PROMPT_TEMPLATES[category]
    scenarios = SCENARIOS[category]

    print(f"\nGenerating {count} examples for category: {category}")
    generated = 0

    with open(output_file, "a") as f:
        while generated < count:
            template = templates[generated % len(templates)]
            scenario = scenarios[generated % len(scenarios)]
            print(f"  [{generated + 1}/{count}] {template[:50]}...")
            example = generate_example(category, template, scenario)
            if example:
                f.write(json.dumps(example) + "\n")
                generated += 1
            time.sleep(0.5)  # Rate limit buffer

    print(f"  Done. Saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Salesforce AI dataset")
    parser.add_argument("--category", choices=["apex", "lwc", "integrations", "architecture", "all"], default="all")
    parser.add_argument("--count", type=int, default=100, help="Number of examples per category")
    parser.add_argument("--output", type=str, default="dataset", help="Output directory")
    args = parser.parse_args()

    categories = ["apex", "lwc", "integrations", "architecture"] if args.category == "all" else [args.category]
    for cat in categories:
        generate_dataset(cat, args.count, os.path.join(args.output, cat))

    print("\nDataset generation complete!")
