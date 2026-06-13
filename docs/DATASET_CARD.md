# Dataset Card — SalesforceAI: Open Apex & LWC Fine-Tuning Dataset

## Dataset Summary

SalesforceAI is the first large-scale, open fine-tuning dataset for Salesforce Apex and Lightning Web Components (LWC). It contains thousands of instruction-following prompt-response pairs covering real Salesforce development scenarios, validated by a certified Salesforce developer with hands-on platform experience.

## Supported Tasks

- **Code generation** (Apex, LWC, SOQL)
- **Code completion**
- **Instruction following** for Salesforce-specific tasks

## Languages

English (instructions), Apex / JavaScript (code outputs)

## Dataset Structure

Each record contains:

| Field | Type | Description |
|---|---|---|
| `instruction` | string | Natural language coding task |
| `input` | string | Optional context (usually empty) |
| `output` | string | Complete, correct Salesforce code |
| `category` | string | `apex`, `lwc`, `integrations`, `architecture` |
| `subcategory` | string | e.g. `triggers`, `batch`, `forms` |
| `difficulty` | string | `beginner`, `intermediate`, `advanced` |
| `tags` | list | Relevant keywords |

## Source Data

Generated using OpenAI API (GPT-4) with a Salesforce-expert system prompt, reviewed and validated against real Salesforce platform behavior by Rahul Ravipudi (certified Salesforce Developer & Architect, 3–5 years experience).

## Licensing

Apache 2.0 — free to use, fine-tune, and build upon with attribution.

## Citation

```
@dataset{ravipudi2025salesforceai,
  author = {Rahul Ravipudi},
  title = {SalesforceAI: Open Apex & LWC Fine-Tuning Dataset},
  year = {2025},
  url = {https://github.com/rahulravipudi/salesforce-ai-dataset}
}
```
