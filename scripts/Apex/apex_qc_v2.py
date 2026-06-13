"""
Salesforce Apex SFT Dataset Quality Checker — v2
=================================================
Master QC script incorporating all learnings from the dataset pipeline.

Judge  : meta/llama-4-maverick-17b-128e-instruct (NIM) — 94.2% acceptance in final run
Scoring: completeness, alignment, best_practices, code_quality (1-5 each)
Accept : all scores >= 3 AND avg >= 3.5
Workers: 3 parallel (safe NIM rate limit)

Input  : apex_dataset_v2/   (or any directory with JSONL files)
Output :
  apex_dataset_v2_clean/       accepted examples
  apex_dataset_v2_rejected.jsonl  rejected with reasons
  quality_report_v2.json          stats + category breakdown
  qc_v2_checkpoint.json           safe to resume if interrupted

Run:
    caffeinate -dims python3 -u apex_qc_v2.py | tee apex_qc_v2.log
    caffeinate -dims python3 -u apex_qc_v2.py --input my_dir | tee apex_qc_v2.log
"""

import json, time, re, sys, os, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

# ── CONFIG ────────────────────────────────────────────────────────────────────
NIM_API_KEY = os.environ.get("NIM_API_KEY")
if not NIM_API_KEY:
    sys.exit("ERROR: Set NIM_API_KEY environment variable before running.\n  export NIM_API_KEY=nvapi-...")
NIM_URL     = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL       = "meta/llama-4-maverick-17b-128e-instruct"

# Parse --input flag
INPUT_DIR     = Path(sys.argv[sys.argv.index("--input") + 1]) if "--input" in sys.argv else Path("apex_dataset_v2")
CLEAN_DIR     = Path(str(INPUT_DIR) + "_clean")
REJECTED_FILE = Path(str(INPUT_DIR) + "_rejected.jsonl")
REPORT_FILE   = Path("quality_report_v2.json")
CHECKPOINT    = Path("qc_v2_checkpoint.json")

CLEAN_DIR.mkdir(exist_ok=True)
NIM_SEM = Semaphore(3)   # 3 parallel workers — safe for NIM rate limits

HEADERS = {
    "Authorization": f"Bearer {NIM_API_KEY}",
    "Content-Type":  "application/json",
    "Accept-Encoding": "identity",
}

# ── PROMPTS ───────────────────────────────────────────────────────────────────
SYSTEM = """You are a strict Salesforce Apex code quality judge for an LLM fine-tuning dataset.
Be critical — reject anything that would teach bad patterns to a model being trained on Apex."""

USER = """Evaluate this Salesforce Apex SFT training example.

INSTRUCTION:
{instruction}

APEX CODE OUTPUT:
{output}

Score each criterion 1-5 (5=perfect, 1=completely wrong):
1. COMPLETENESS  — Full, compilable code. No truncation, no TODO stubs, no ellipsis.
2. ALIGNMENT     — Code exactly implements what the instruction asks for.
3. BEST_PRACTICES — Bulkified (no SOQL/DML in loops), with sharing, WITH SECURITY_ENFORCED, SaveResult checked.
4. CODE_QUALITY  — Realistic production Apex, proper error handling, Javadoc, not pseudocode.

ACCEPT if ALL scores >= 3 AND average >= 3.5
REJECT if ANY score <= 2 OR average < 3.5

Respond with ONLY valid JSON — no markdown, no explanation:
{{"completeness": <1-5>, "alignment": <1-5>, "best_practices": <1-5>, "code_quality": <1-5>, "verdict": "accept" or "reject", "reason": "<one sentence max>"}}"""

# ── HELPERS ───────────────────────────────────────────────────────────────────
def clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$',          '', text, flags=re.MULTILINE)
    m = re.search(r'\{.*\}', text, re.DOTALL)
    return m.group(0) if m else text


def judge(instruction: str, output: str, max_attempts: int = 4):
    """Call Llama 4 Maverick to score an example."""
    prompt  = USER.format(instruction=instruction[:800], output=output[:3000])
    payload = {
        "model":       MODEL,
        "messages":    [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.1,    # low temp for consistent scoring
        "max_tokens":  300,
    }
    for attempt in range(1, max_attempts + 1):
        try:
            with NIM_SEM:
                r = requests.post(NIM_URL, json=payload, headers=HEADERS, timeout=45)
            if r.status_code == 429:
                wait = 30 * attempt
                time.sleep(wait)
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            parsed  = json.loads(clean_json(content))

            # Validate required keys
            for key in ["completeness", "alignment", "best_practices", "code_quality", "verdict", "reason"]:
                if key not in parsed:
                    raise ValueError(f"Missing key: {key}")

            # Enforce verdict logic (don't trust model's verdict blindly)
            scores = [parsed["completeness"], parsed["alignment"],
                      parsed["best_practices"], parsed["code_quality"]]
            avg = round(sum(scores) / 4, 2)
            parsed["avg_score"] = avg
            parsed["verdict"]   = "accept" if all(s >= 3 for s in scores) and avg >= 3.5 else "reject"
            return parsed

        except Exception as e:
            if attempt < max_attempts:
                time.sleep(5 * attempt)

    # Judge failed — conservative reject
    return {
        "completeness": 0, "alignment": 0, "best_practices": 0, "code_quality": 0,
        "avg_score": 0.0,  "verdict": "reject",
        "reason": f"Judge error after {max_attempts} attempts",
    }


def evaluate(args):
    idx, example = args
    result = judge(example.get("instruction", ""), example.get("output", ""))
    return idx, example, result


# ── CHECKPOINT ────────────────────────────────────────────────────────────────
def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        data = json.loads(CHECKPOINT.read_text())
        # Filter out zero-score entries from previous failed judge calls
        return {k: v for k, v in data.items() if v.get("avg_score", 0) > 0}
    return {}


def save_checkpoint(done: dict):
    CHECKPOINT.write_text(json.dumps(done))


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    if not INPUT_DIR.exists():
        print(f"ERROR: Input directory '{INPUT_DIR}' not found.")
        print(f"  Run apex_generator_v2.py first, or pass --input <dir>")
        sys.exit(1)

    # Load all examples
    all_examples = []
    for jf in sorted(INPUT_DIR.glob("*.jsonl")):
        for line in open(jf):
            line = line.strip()
            if line:
                ex = json.loads(line)
                ex["_source_file"] = jf.name
                all_examples.append(ex)

    total     = len(all_examples)
    ckpt      = load_checkpoint()
    remaining = [(i, ex) for i, ex in enumerate(all_examples) if str(i) not in ckpt]

    print(f"\n{'='*60}")
    print(f"  Apex SFT Quality Checker v2")
    print(f"  Judge  : {MODEL}")
    print(f"  Input  : {INPUT_DIR}/ ({total} examples)")
    print(f"  Done   : {len(ckpt)}")
    print(f"  To do  : {len(remaining)}")
    print(f"  Workers: 3 parallel")
    print(f"{'='*60}\n")

    # Seed from checkpoint
    accepted, rejected = [], []
    for key, val in ckpt.items():
        ex = all_examples[int(key)]
        (accepted if val["verdict"] == "accept" else rejected).append((ex, val))

    processed = len(ckpt)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(evaluate, w): w for w in remaining}
        for future in as_completed(futures):
            idx, example, result = future.result()
            ckpt[str(idx)] = result
            processed += 1

            icon = "✅" if result["verdict"] == "accept" else "❌"
            cat  = example.get("category", "?")
            print(f"  [{processed:>4}/{total}] {icon} {result['avg_score']:.1f}  {cat:<28}  {result['reason'][:55]}")

            (accepted if result["verdict"] == "accept" else rejected).append((example, result))

            if processed % 25 == 0:
                save_checkpoint(ckpt)

    save_checkpoint(ckpt)

    # ── WRITE OUTPUTS ─────────────────────────────────────────────────────────
    print(f"\n  Writing outputs...")

    # Clean — group by source file
    clean_by_file = {}
    for ex, _ in accepted:
        clean_by_file.setdefault(ex["_source_file"], []).append(ex)
    for fname, examples in clean_by_file.items():
        with open(CLEAN_DIR / fname, "w") as f:
            for ex in examples:
                record = {k: v for k, v in ex.items() if not k.startswith("_")}
                f.write(json.dumps(record) + "\n")

    # Rejected
    with open(REJECTED_FILE, "w") as f:
        for ex, result in rejected:
            record = {k: v for k, v in ex.items() if not k.startswith("_")}
            record["_qc"] = result
            f.write(json.dumps(record) + "\n")

    # ── REPORT ────────────────────────────────────────────────────────────────
    cat_stats = {}
    for ex, result in (accepted + rejected):
        cat = ex.get("category", "unknown")
        cat_stats.setdefault(cat, {"accept": 0, "reject": 0})
        cat_stats[cat][result["verdict"]] += 1

    report = {
        "judge":              MODEL,
        "total":              total,
        "accepted":           len(accepted),
        "rejected":           len(rejected),
        "acceptance_rate":    round(len(accepted) / max(total, 1) * 100, 1),
        "avg_score_accepted": round(sum(v["avg_score"] for _, v in accepted) / max(len(accepted), 1), 2),
        "avg_score_rejected": round(sum(v["avg_score"] for _, v in rejected) / max(len(rejected), 1), 2),
        "by_category": {
            cat: {**s, "pass_rate": round(s["accept"] / max(s["accept"] + s["reject"], 1) * 100, 1)}
            for cat, s in sorted(cat_stats.items())
        },
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2))

    # ── BUILD FINAL JSONL ──────────────────────────────────────────────────────
    final_file = Path(str(INPUT_DIR) + "_final.jsonl")
    with open(final_file, "w") as f:
        for ex, _ in accepted:
            record = {k: v for k, v in ex.items() if not k.startswith("_")}
            f.write(json.dumps(record) + "\n")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ Accepted : {len(accepted):>5}  ({report['acceptance_rate']}%)")
    print(f"  ❌ Rejected : {len(rejected):>5}")
    print(f"  📊 Avg score (accepted) : {report['avg_score_accepted']}")
    print(f"  📊 Avg score (rejected) : {report['avg_score_rejected']}")
    print(f"\n  📁 Final dataset → {final_file}")
    print(f"  📁 Clean dir     → {CLEAN_DIR}/")
    print(f"  📁 Rejected      → {REJECTED_FILE}")
    print(f"  📁 Report        → {REPORT_FILE}")
    print(f"{'='*60}\n")

    # Worst categories
    worst = sorted(report["by_category"].items(), key=lambda x: x[1]["pass_rate"])[:5]
    if worst:
        print("  ⚠️  Lowest quality categories:")
        for cat, s in worst:
            print(f"     {cat:<35} {s['pass_rate']}% pass ({s['reject']} rejected)")
    print()


if __name__ == "__main__":
    main()
