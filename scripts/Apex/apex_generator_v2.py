"""
Salesforce Apex SFT Dataset Generator — v2
==========================================
Master generator script incorporating all learnings from the dataset pipeline.

Model  : meta/llama-4-maverick-17b-128e-instruct (NIM) — fast, clean JSON, ~2.5s/call
Format : Alpaca (instruction, input, output, category, type)
Output : apex_dataset_v2/   one JSONL per category
Resume : apex_gen_v2_checkpoint.json

Run:
    caffeinate -dims python3 -u apex_generator_v2.py | tee apex_gen_v2.log
"""

import json, time, re, requests, os, sys
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
NIM_API_KEY = os.environ.get("NIM_API_KEY")
if not NIM_API_KEY:
    sys.exit("ERROR: Set NIM_API_KEY environment variable before running.\n  export NIM_API_KEY=nvapi-...")
NIM_URL     = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL       = "meta/llama-4-maverick-17b-128e-instruct"   # best performing on NIM for Apex
# Fallback: "mistralai/mistral-medium-3.5-128b" if Maverick is rate-limited

OUTPUT_DIR  = Path("apex_dataset_v2")
CHECKPOINT  = Path("apex_gen_v2_checkpoint.json")
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {NIM_API_KEY}",
    "Content-Type":  "application/json",
}

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
# Enforces every Apex best practice we learned matters for QC pass rate
SYSTEM_PROMPT = """You are an expert Salesforce Apex developer generating high-quality SFT training examples.

## ABSOLUTE PROHIBITIONS (instant fail if violated)
❌ NEVER put a SOQL query inside a for loop — query BEFORE the loop, store in Map<Id, SObject>
❌ NEVER put DML (insert/update/delete/upsert) inside a for loop — collect in List, DML ONCE outside
❌ NEVER put HTTP callouts inside a for loop
❌ NEVER truncate or abbreviate code — every class/method must be 100% complete and compilable
❌ NEVER use placeholder comments like // TODO, // implement, // add logic here, ...
❌ NEVER hardcode record IDs, org-specific URLs, usernames, or email addresses

## MANDATORY REQUIREMENTS (every example must have ALL)
✅ public with sharing class ClassName  — on every class (triggers and interfaces are exempt)
✅ WITH SECURITY_ENFORCED               — on every inline SOQL query
✅ Database.SaveResult[] results = Database.insert/update/delete(list, false)  — after every DML
✅ Loop over SaveResult[] and log errors — never assume DML succeeded
✅ /** @description <one line> */ Javadoc block on every public and private method
✅ try/catch with AuraHandledException for @AuraEnabled methods
✅ try/catch for HTTP callouts and DML in batch/queueable contexts

## PRE-OUTPUT CHECKLIST — verify before writing
[ ] All SOQL outside loops?
[ ] All DML outside loops?
[ ] Every class has `with sharing`?
[ ] Every SOQL has `WITH SECURITY_ENFORCED`?
[ ] Every DML uses Database.SaveResult[] with error check?
[ ] Code is 100% complete — no stubs, no TODOs, no truncation?
[ ] Output directly implements what the instruction asks?

## DOMAIN FIELD NAMES
Financial  : Loan_Amount__c, KYC_Status__c, AUM__c, Premium__c, Risk_Score__c
Healthcare : MRN__c, DOB__c, NPI__c, PHI never in debug logs
Manufacturing: Work_Center__c, BOM__c, Capacity__c, Batch_Number__c
Retail     : SKU__c, Loyalty_Points__c, Stock_Level__c, Promotion_Code__c
Telecom    : MSISDN__c, IMEI__c, Plan_Type__c, NOC__c, Overage__c
Energy     : Meter_Reading__c, Tariff__c, Service_Point__c, Zone__c
Insurance  : Premium__c, Deductible__c, Adjuster__c, Policy_Number__c

## OUTPUT FORMAT
Output ONLY a valid JSON array with exactly ONE object. No markdown, no explanation:
[{"instruction": "Specific task. Mention SObject, operation, pattern, domain.", "input": "", "output": "Complete compilable Apex. Never truncate."}]"""


# ── GENERATION CALLS ──────────────────────────────────────────────────────────
# Import from original generator to reuse the full category list
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("NVIDIA_API_KEY", "placeholder")
try:
    from apex_generator import GENERATION_CALLS
    print(f"Loaded {len(GENERATION_CALLS)} generation calls from apex_generator.py")
except ImportError:
    print("WARNING: Could not import apex_generator.py — define GENERATION_CALLS manually")
    GENERATION_CALLS = []


# ── HELPERS ───────────────────────────────────────────────────────────────────
def clean_json(text: str) -> str:
    """Strip markdown fences and fix invalid Apex backslash escapes."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$',          '', text, flags=re.MULTILINE)
    text = text.strip()
    # Fix \s \d \w etc. in Apex regex literals that break JSON parsing
    text = re.sub(r'\\(?!["\\/bfnrtu0-9])', r'\\\\', text)
    return text


def call_nim(prompt: str, max_attempts: int = 4):
    """Call Llama 4 Maverick on NIM with retry + rate-limit handling."""
    payload = {
        "model":       MODEL,
        "messages":    [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.7,    # creative but not chaotic
        "max_tokens":  6000,   # enough for 1 complete Apex class + test
    }
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.post(NIM_URL, json=payload, headers=HEADERS, timeout=60)
            if r.status_code == 429:
                wait = 45 * attempt
                print(f" [429 — waiting {wait}s]", end="", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            cleaned = clean_json(content)
            examples = json.loads(cleaned)
            if not isinstance(examples, list):
                examples = [examples]
            return examples
        except Exception as e:
            wait = 8 * attempt
            print(f" [err {str(e)[:50]} — wait {wait}s]", end="", flush=True)
            if attempt < max_attempts:
                time.sleep(wait)
    return None


def load_checkpoint() -> set:
    if CHECKPOINT.exists():
        return set(json.loads(CHECKPOINT.read_text()))
    return set()


def save_checkpoint(done: set):
    CHECKPOINT.write_text(json.dumps(sorted(done)))


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    completed = load_checkpoint()
    remaining = [(cid, fname, prompt) for cid, fname, prompt in GENERATION_CALLS
                 if cid not in completed]

    print(f"\n{'='*60}")
    print(f"  Apex SFT Generator v2")
    print(f"  Model  : {MODEL}")
    print(f"  Total  : {len(GENERATION_CALLS)} categories")
    print(f"  Done   : {len(completed)}")
    print(f"  To do  : {len(remaining)}")
    print(f"  Output : {OUTPUT_DIR}/")
    print(f"{'='*60}\n")

    total_new = 0

    for call_id, filename, original_prompt in remaining:
        out_path = OUTPUT_DIR / filename
        print(f"[{call_id}] → {filename} ", end="", flush=True)

        # Force 1 example per call — prevents truncation at token limit
        prompt = re.sub(r'\bGenerate\s+\d+\b', 'Generate 1', original_prompt, flags=re.IGNORECASE)
        prompt += "\n\nIMPORTANT: Output EXACTLY 1 example (JSON array with ONE object). 100% complete, compilable, no truncation."

        examples = call_nim(prompt)

        if examples:
            records = []
            for ex in examples:
                if not ex.get("output", "").strip():
                    continue
                records.append({
                    "instruction": ex.get("instruction", ""),
                    "input":       "",
                    "output":      ex.get("output", ""),
                    "category":    call_id.split("-")[0] if "-" in call_id else call_id,
                    "type":        "domain" if "domain" in call_id else "generic",
                })

            if records:
                with open(out_path, "w") as f:
                    for rec in records:
                        f.write(json.dumps(rec) + "\n")
                completed.add(call_id)
                save_checkpoint(completed)
                total_new += len(records)
                print(f"✅ {len(records)} example(s)")
            else:
                print("❌ empty output")
        else:
            print("❌ failed after retries")

        time.sleep(1)  # gentle rate limiting

    # Final summary
    all_files = list(OUTPUT_DIR.glob("*.jsonl"))
    grand_total = sum(sum(1 for _ in open(f)) for f in all_files)

    print(f"\n{'='*60}")
    print(f"  ✅ Categories done : {len(completed)}")
    print(f"  📦 New examples    : {total_new}")
    print(f"  📊 Grand total     : {grand_total} in {OUTPUT_DIR}/")
    print(f"\n  Next: run apex_qc_v2.py to judge and build final dataset")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
