# SalesforceAI — Open Apex & LWC Fine-Tuning Dataset

> The first large-scale, open-source fine-tuning dataset for Salesforce Apex and Lightning Web Components (LWC).

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Hugging Face](https://img.shields.io/badge/🤗%20Hugging%20Face-Dataset-yellow)](https://huggingface.co/datasets/RahulShettyRavipudi/salesforce-apex-lwc-dataset)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Why This Exists

The Salesforce ecosystem has over **9 million developers** worldwide, yet no open, high-quality training dataset exists for its core languages — Apex and LWC. General-purpose LLMs routinely hallucinate Salesforce-specific APIs, ignore governor limits, and produce code that would fail in a real Salesforce org.

This project changes that. Built by a certified Salesforce developer with  hands-on experience across Apex, LWC, integrations, and architecture — this dataset is grounded in real platform knowledge, not just scraped code.

**Goal:** Enable anyone to fine-tune a model that genuinely understands Salesforce development — making the platform accessible to developers everywhere, regardless of budget or background.

---

## Dataset Coverage

| Category | Examples | Topics |
|---|---|---|
| **Apex** | `dataset/apex/` | Triggers, classes, batch jobs, queueable, test classes |
| **LWC / Aura** | `dataset/lwc/` | Components, controllers, events, wire adapters |
| **Integrations** | `dataset/integrations/` | REST, SOAP, Platform Events, Change Data Capture |
| **Architecture** | `dataset/architecture/` | Bulkification, separation of concerns, design patterns |

Each example is a structured `prompt → response` pair in JSONL format, validated against real Salesforce platform behavior.

---

## Dataset Format

Each record follows the instruction-tuning format:

1. Alpaca (Instruction-Tuning) Format
Used for single-turn, instruction-response pairs.

```json
{
  "instruction": "Build an LWC component using getRecord LDS wire to display a Contact's Name, Email, Phone, Title, Account Name with spinner and error panel.",
  "input": "",
  "output": "<!-- contactCard.html -->\n<template>\n  ...\n</template>\n\n// contactCard.js\nimport { LightningElement, api, wire } from 'lwc';\n...",
  "source": "synthetic_lwc_expanded/lds_wire_adapters",
  "type": "lwc",
  "category": "LDS Wire Adapters",
  "domain": "Financial Services"
}
```

instruction — the task or question posed to the model
input — optional additional context; empty string if not needed
output — the expected model response

2. Chat / Messages Format
Used for multi-turn conversations.

```json
{
  "messages": [
    { "role": "system", "content": "You are a Salesforce Apex expert." },
    { "role": "user", "content": "Write an Apex trigger that prevents duplicate Account names." },
    { "role": "assistant", "content": "trigger PreventDuplicateAccounts on Account (before insert, before update) { ... }" }
  ],
  "category": "apex",
  "subcategory": "triggers",
  "difficulty": "intermediate",
  "tags": ["trigger", "deduplication"]
}

```
messages — ordered list of turns; each has a role (system, user, or assistant) and content
A system message is optional but recommended for context-setting

---

## Quickstart

```bash
git clone https://github.com/rahulravipudi/salesforce-ai-dataset.git
cd salesforce-ai-dataset
pip install -r scripts/requirements.txt
```

Load the dataset in Python:

```python
from datasets import load_dataset

ds = load_dataset("json", data_files="dataset/apex/*.jsonl")
print(ds["train"][0])
```

---

## Repo Structure

```
salesforce-ai-dataset/
├── dataset/
│   ├── apex/           # Apex prompt-response pairs (.jsonl)
│   ├── lwc/            # LWC / Aura prompt-response pairs (.jsonl)
│   ├── integrations/   # Integration patterns (.jsonl)
│   └── architecture/   # Design patterns & architecture (.jsonl)
├── scripts/
│   ├── generate.py     # Dataset generation pipeline (OpenAI API)
│   ├── validate.py     # Validation & quality checks
│   └── requirements.txt
├── evaluation/
│   └── benchmark.py    # Evaluation benchmarks
├── examples/
│   └── finetune.ipynb  # Example fine-tuning notebook
├── docs/
│   └── DATASET_CARD.md # Hugging Face dataset card
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

---

## Generation Pipeline

Dataset examples are generated using the OpenAI API (Codex / GPT-4) and validated through:

1. **Prompt diversity** — covering beginner to advanced scenarios across all categories
2. **Platform validation** — all examples reviewed for governor limit compliance, best practices, and real org behavior
3. **Automated review** — PR-level quality checks using Codex CLI
4. **Community review** — open PRs welcome for corrections and additions

---

## Contributing

We welcome contributions from the Salesforce developer community! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Adding new dataset examples
- Fixing incorrect or outdated code
- Proposing new categories or subcategories
- Improving the generation pipeline

---

## Roadmap

- [x] Repo structure and dataset format
- [ ] 1,500 Apex examples (seed dataset)
- [ ] 1,500 LWC examples (seed dataset)
- [ ] 500 Integration pattern examples
- [ ] 500 Architecture & design pattern examples
- [ ] 500 SOQL & SOSL examples
- [ ] 500 Visualforce examples
- [ ] 500 Multi-turn conversations examples
- [ ] 500 Code review and debugging examples
- [ ] 200 Migration patterns examples
- [ ] 200 Metadata deployment  examples
- [ ] Publish to Hugging Face Hub
- [ ] Fine-tuned model (based on Qwen Models)
- [ ] Evaluation benchmark against GPT-4 and Copilot on Salesforce tasks

---

## License

Dataset and scripts are released under the [Apache 2.0 License](LICENSE). Free to use, fine-tune, and build upon — with attribution.

---

## Author

**Rahul Ravipudi** — Certified Salesforce Developer 
[GitHub](https://github.com/rahulravipudi) 

---

*Supported by the [OpenAI Codex Open Source Fund](https://openai.com/form/codex-open-source-fund/)*
