"""
Code Review & Debugging Dataset Generator
Generates training examples for Salesforce code review and debugging.

Usage:
    pip install openai
    export MIMO_API_KEY="your-key-here"
    caffeinate -i python3 codereview_generator.py
"""

import os, json, time, re
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MIMO_API_KEY"],
    base_url="https://opengateway.gitlawb.com/v1",
    timeout=600,
    default_headers={"Accept-Encoding": "identity"}
)
MODEL = "mimo-v2.5-pro"

OUTPUT_DIR      = Path("codereview_dataset")
CHECKPOINT_FILE = Path("codereview_checkpoint.json")
OUTPUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are a senior Salesforce architect generating code review and debugging training examples.

## YOUR ROLE
You review code like a senior engineer who:
- Catches governor limit violations immediately
- Knows Salesforce security pitfalls deeply
- Gives specific, actionable feedback (not vague)
- Explains WHY something is wrong, not just what
- Provides the corrected version, not just criticism

## SALESFORCE-SPECIFIC ISSUES TO KNOW
Governor Limits:
- SOQL in loops = Too many SOQL queries 101 error
- DML in loops = Too many DML statements 151 error
- Callouts in loops = Too many callouts error
- No LIMIT on queries = Too many query rows 50001 error

Security Issues:
- Missing WITH SECURITY_ENFORCED = data leakage
- Missing sharing declaration = privilege escalation risk
- Hardcoded IDs = breaks across orgs/sandboxes
- String concatenation in SOQL = injection vulnerability
- Missing CRUD/FLS checks = security vulnerability

Common Bugs:
- Missing recursion guard in triggers
- DML in before trigger (same object)
- Callout after DML in same transaction
- Missing null checks on Trigger.old
- Not checking Database.SaveResult for errors
- Missing Test.startTest()/stopTest() for async

## OUTPUT FORMAT
Output ONLY a valid JSON array. No markdown fences. No preamble.

For review/debug examples:
[
  {
    "instruction": "Review this code / Debug this error / What is wrong with this code",
    "input": "The code or error to review (can be empty string if in instruction)",
    "output": "Detailed review with issues identified + corrected code"
  }
]"""

GENERATION_CALLS = [

    # ══════════════════════════════════════════════════════════════════════════
    # GOVERNOR LIMIT BUGS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-01-soql-in-loop", "cr_01_soql_in_loop.jsonl", """
Generate 10 training examples where SOQL is incorrectly placed inside a loop.

For each example:
- Show the BROKEN code with SOQL in a loop
- Explain exactly why it fails (governor limit math: e.g. "200 records x 1 query = 200 queries, limit is 100")
- Show the FIXED code using Map-based pre-query pattern
- Show the test that would catch this bug

Cover these 10 scenarios with domain rotation:
1. FSI: Trigger iterating accounts and querying LoanApplication__c inside loop
2. Healthcare: Batch execute() querying Patient__c for each scope record
3. Manufacturing: Service method querying WorkOrder for each item in a List
4. Retail: Trigger querying inventory for each Order line in loop
5. Telco: For loop querying Contract for each ServiceOrder__c
6. Energy: Scheduled Apex querying Meter readings inside for loop
7. PS: InvocableMethod querying Project for each input record
8. Insurance: REST endpoint querying Policy for each ID in request body
9. Generic: Nested loop — outer loop on accounts, inner loop queries contacts (O(n²))
10. Generic: While loop — SOQL inside while loop that processes records one at a time

Each output must include:
- BROKEN code clearly labeled as wrong
- Governor limit math in comments
- FIXED code with Map pre-query
- Test class that catches the bug with 101 records
"""),

    ("CR-02-dml-in-loop", "cr_02_dml_in_loop.jsonl", """
Generate 10 training examples where DML is incorrectly placed inside a loop.

For each example:
- Show the BROKEN code with DML in a loop
- Explain the governor limit impact
- Show the FIXED code using List/Map accumulation then single DML
- Show the test

Cover these 10 scenarios with domain rotation:
1. FSI: Trigger inserting Transaction__c records one by one inside for loop
2. Healthcare: Batch execute() updating Patient__c records individually in loop
3. Manufacturing: Service method inserting WorkOrder line items in for loop
4. Retail: Trigger updating Stock_Level__c for each Order line in loop
5. Telco: Queueable inserting Usage_Record__c one at a time
6. Energy: Scheduled Apex updating Meter__c readings in for loop
7. PS: InvocableMethod upserting Timesheet records in loop
8. Insurance: REST endpoint inserting Claim records one by one
9. Generic: Update inside for-each with Database.update inside loop
10. Generic: Delete inside loop — deleting related records one at a time

Each output: BROKEN code + governor limit math + FIXED bulk pattern + test.
"""),

    ("CR-03-callout-issues", "cr_03_callout_issues.jsonl", """
Generate 10 training examples covering callout-related bugs.

Cover these 10 scenarios:
1. Callout after DML in same transaction — System.CalloutException
2. Callout in Batch execute() without AllowsCallouts
3. Callout in trigger (not async) — not allowed
4. Callout in loop — Too many callouts
5. Callout in Queueable without AllowsCallouts interface
6. Missing timeout on callout — hangs indefinitely
7. Callout without Named Credential — hardcoded endpoint
8. No error handling for non-200 response
9. Callout in @future called from trigger with DML
10. Continuation Apex callback not properly handling null response

Each example: BROKEN code + exact error message that would appear + FIXED code + test with HttpCalloutMock.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # SECURITY BUGS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-04-security-issues", "cr_04_security_issues.jsonl", """
Generate 10 training examples covering Salesforce security bugs.

Cover these 10 security issues with domain rotation:
1. Missing WITH SECURITY_ENFORCED — FSI: exposing loan data to unauthorized users
2. Missing sharing declaration — Healthcare: patient data accessible without sharing enforcement
3. SOQL injection via string concatenation — Manufacturing: dynamic SOQL built unsafely
4. Missing CRUD check before insert — Retail: inserting Order without checking isCreateable()
5. Missing FLS check before field update — Telco: updating billing fields without FLS check
6. Hardcoded record ID — Energy: trigger using literal 15-char ID that breaks in other orgs
7. Hardcoded username — PS: service method using 'admin@company.com' hardcoded
8. Missing stripInaccessible — Insurance: returning fields user cannot see
9. AuraHandledException exposing internal details — leaking stack trace to LWC
10. Debug log with sensitive data — Healthcare: System.debug logging PHI/PII

Each example:
- BROKEN code showing the vulnerability
- Explanation of exactly what attack/data leak is possible
- FIXED code with proper security
- How to test the fix verifies security
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # TRIGGER BUGS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-05-trigger-bugs", "cr_05_trigger_bugs.jsonl", """
Generate 10 training examples covering common trigger bugs.

Cover these 10 trigger-specific issues:
1. Missing recursion guard — trigger fires itself infinitely on afterUpdate
2. DML in before trigger on same object — System.SObjectException
3. Logic directly in trigger file — business logic that should be in handler
4. Not handling null Trigger.old — NullPointerException on insert context
5. Using Trigger.new in after delete — should use Trigger.old
6. Using addError() in after context — only works in before context
7. Multiple triggers on same object — unpredictable execution order
8. SOQL using Trigger.new IDs — correct but missing Map optimization
9. Trigger not bulkified — processing Trigger.new[0] instead of full list
10. Missing before insert check — trigger that should prevent insert not using addError correctly

Each example: BROKEN trigger + exact behavior/error + FIXED trigger + handler + test with 200 records.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # ASYNC APEX BUGS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-06-async-bugs", "cr_06_async_bugs.jsonl", """
Generate 10 training examples covering async Apex bugs.

Cover these 10 async-specific issues:
1. Batch: not handling Database.SaveResult in execute() — silently swallowing errors
2. Batch: SOQL in execute() when records could be fetched in start()
3. Batch: stateful batch not implementing Database.Stateful — losing state between chunks
4. Queueable: not checking System.isQueueable() before enqueueing — test failures
5. Queueable: chaining without checking depth limit — System.AsyncException
6. Scheduled: scheduling same job twice — duplicate job error
7. @Future: passing SObject parameter — not allowed, must pass primitive or collection
8. @Future: callout=true missing when making callout
9. Batch: scope size too large for complex records — CPU timeout
10. Queueable: not handling exception in execute() — job silently fails

Each example: BROKEN code + what goes wrong silently or explicitly + FIXED code + test.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # TEST CLASS ISSUES
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-07-test-issues", "cr_07_test_issues.jsonl", """
Generate 10 training examples covering test class problems.

Cover these 10 test-specific issues:
1. Test relies on org data — SeeAllData=true making test brittle
2. Missing Test.startTest()/stopTest() — async code not actually tested
3. No assertions — test passes but verifies nothing
4. Assertion without message — assertEquals(a,b) without descriptive message
5. Test passes in sandbox, fails in production — org data dependency
6. Test coverage at 74% blocked on deployment — missing branch coverage
7. HttpCalloutMock not set up — test fails with CalloutException
8. Test creating records but wrong sharing context — not testing sharing correctly
9. Test not testing bulk — only testing 1 record, misses governor limit bugs
10. Test testing private methods — better to test through public interface

Each example: BAD test class + explanation of what it misses + GOOD test class that properly covers the code.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # CODE REVIEW — GENERAL QUALITY
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-08-quality-review", "cr_08_quality_review.jsonl", """
Generate 10 code review training examples covering general code quality issues.

Cover these 10 quality issues with domain rotation:
1. God class doing too much — FSI: one class handling queries, business logic, DML, emails
2. Missing error handling — Healthcare: service method with no try/catch
3. Meaningless variable names — Manufacturing: variables named a, b, temp, x
4. Dead code — Retail: commented-out code blocks and unused methods
5. Missing Javadoc — Telco: public methods with no @description comments
6. Magic numbers — Energy: hardcoded threshold values instead of named constants or CMT
7. Method too long — PS: 200-line method that should be broken into smaller methods
8. Copy-paste code — Insurance: same logic repeated in 3 places instead of shared method
9. Wrong sharing model — Generic: without sharing on public-facing controller
10. Missing null safety — Generic: NullPointerException waiting to happen on chained calls

Each example: PROBLEMATIC code + detailed review explaining every issue + REFACTORED code.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # SPECIFIC ERROR DIAGNOSIS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-09-error-diagnosis", "cr_09_error_diagnosis.jsonl", """
Generate 10 training examples for diagnosing specific Salesforce error messages.

For each: show the error, the code causing it, diagnosis, and fix.

Cover these 10 errors:
1. "System.LimitException: Too many SOQL queries: 101"
2. "System.LimitException: Too many DML statements: 151"
3. "System.NullPointerException: Attempt to de-reference a null object"
4. "System.QueryException: List has no rows for assignment to SObject"
5. "System.CalloutException: You have uncommitted work pending"
6. "MIXED_DML_OPERATION: DML operation on setup and non-setup objects"
7. "UNABLE_TO_LOCK_ROW: unable to obtain exclusive access to this record"
8. "System.SObjectException: DML not allowed on User in triggers"
9. "System.AsyncException: Maximum depth has been reached"
10. "System.EmailException: SendEmail failed. First exception on row 0"

Each example: show what code causes it, exactly why it happens, how to fix it, how to prevent it.
"""),

    ("CR-10-error-diagnosis-2", "cr_10_error_diagnosis_2.jsonl", """
Generate 10 more training examples for diagnosing Salesforce errors.

Cover these 10 errors:
1. "FIELD_CUSTOM_VALIDATION_EXCEPTION" — trigger DML violating validation rule
2. "Required fields are missing: [Name]" — missing required field before insert
3. "ENTITY_IS_DELETED" — querying or DML on deleted record
4. "INVALID_CROSS_REFERENCE_KEY" — lookup field pointing to wrong object
5. "DUPLICATE_VALUE on external ID" — upsert with existing external ID conflict
6. "System.StringException: Invalid id value" — malformed record ID
7. "System.JSONException: Malformed JSON" — incorrect JSON structure in callout response
8. "Variable does not exist" — Apex compile error on field name typo
9. "Compile error: Method does not exist" — wrong method signature or missing import
10. "Test coverage: 0%" — why a class shows 0% even when test runs

Each: code causing it + exact error + root cause explanation + fix + prevention.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAIN-SPECIFIC CODE REVIEWS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-11-domain-reviews", "cr_11_domain_reviews.jsonl", """
Generate 10 domain-specific code review examples.

Cover these 10 domain scenarios:
1. FSI: Review a loan calculation service — find precision errors, missing rounding, currency issues
2. Healthcare: Review a patient data sync — find HIPAA violations, PHI in debug logs, missing audit
3. Manufacturing: Review a WorkOrder batch — find scope size issue, missing error collection
4. Retail: Review an Order trigger — find inventory race condition, missing lock
5. Telco: Review a provisioning Queueable — find missing AllowsCallouts, no finalizer
6. Energy: Review a meter reading service — find timezone bug, missing validation
7. PS: Review a timesheet approval flow — find missing permission check, wrong sharing
8. Insurance: Review a claims adjuster assignment — find hardcoded adjuster ID, missing null check
9. Generic: Review a REST endpoint — find missing authentication, no rate limiting, info leakage
10. Generic: Review a scheduled batch — find duplicate scheduling risk, missing abort before reschedule

Each: show realistic domain code with subtle bugs + detailed review + fixed version.
"""),

    ("CR-12-lwc-review", "cr_12_lwc_review.jsonl", """
Generate 10 LWC code review training examples.

Cover these 10 LWC-specific issues:
1. Missing error handling on wire adapter — shows undefined instead of error message
2. isLoading resolving too early — multiple wire adapters, loading clears before all ready
3. Direct DOM manipulation — using querySelector instead of reactive properties
4. Memory leak — event listener added in connectedCallback not removed in disconnectedCallback
5. Invalid ternary in template — expression not supported inside lwc:if binding
6. Missing trackable state — @track missing on object property mutation
7. Hardcoded label text — should use custom labels for i18n support
8. Missing SLDS classes — not following Salesforce Lightning Design System
9. Apex method called in connectedCallback — should use wire adapter instead
10. Missing accessibility — no aria labels, no keyboard navigation support

Each: BROKEN LWC (html + js) + detailed review + FIXED LWC.
"""),

    ("CR-13-integration-review", "cr_13_integration_review.jsonl", """
Generate 10 integration code review examples covering REST/SOAP callout patterns.

Cover these 10 integration issues:
1. Missing timeout — callout hangs if external API is slow
2. No retry logic — single failure breaks entire process
3. Synchronous callout for long operations — should use Continuation or Queueable
4. Hardcoded endpoint URL — breaks in sandbox, should use Named Credential
5. No response code check — assuming 200 always returned
6. Parsing without null check — NPE when response field is missing
7. Logging full response including sensitive data — security risk
8. No idempotency key — duplicate processing on retry
9. Missing correlation ID — cannot trace request through systems
10. Synchronous callout in trigger — not allowed, must be async

Each: PROBLEMATIC integration code + security/reliability issues + FIXED version + test with mock.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # CPU TIME & HEAP LIMIT BUGS
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-14-cpu-heap-limits", "cr_14_cpu_heap_limits.jsonl", """
Generate 10 training examples covering CPU time limit and heap size limit bugs in Salesforce Apex.

These are the "other" governor limits that catch developers off guard — NOT SOQL/DML in loops (those are covered elsewhere).

Cover these 10 scenarios:

CPU Time Limit (10s sync / 60s async):
1. String concatenation in a loop — building large strings with += instead of List<String> + String.join()
2. Heavy regex in a loop — Pattern.compile() inside loop instead of compiling once outside
3. Recursive method without base case depth check — CPU exhaustion via deep recursion
4. Sorting a massive list inside a loop — O(n² log n) when it should be O(n log n)
5. JSON.serialize() on huge nested object graph — CPU spike deserializing complex object trees

Heap Size Limit (6MB sync / 12MB async):
6. Querying all fields (SELECT *-equivalent) on large objects — heap blowup from unused fields
7. Building a Map<Id, List<SObject>> without limit — accumulating all child records in memory
8. String.split() on a multi-MB string — creates huge array in heap
9. Deserializing a large JSON response into a typed object graph — heap exhaustion
10. Batch execute() accumulating results in a Stateful list without bounding size

For each example:
- BROKEN code clearly labeled
- Why it hits the CPU/heap limit (rough math where possible)
- FIXED code with the efficient pattern
- How to test/detect (debug log profiling tip)
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # PLATFORM EVENTS & CHANGE DATA CAPTURE
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-15-platform-events-review", "cr_15_platform_events.jsonl", """
Generate 10 training examples covering Platform Events and Change Data Capture (CDC) bugs and review issues.

Cover these 10 scenarios:

Platform Event pitfalls:
1. Publishing Platform Event inside a trigger without checking transaction context — event not published on rollback
2. Missing ReplayId handling in trigger subscriber — replaying from -1 causing missed events
3. Platform Event trigger not bulkified — processing EventBus.TriggerContext.currentPosition() wrong
4. Publishing too many events per transaction (>1000) — hitting publish limit
5. Not handling duplicate event delivery — subscriber not idempotent, processes same event twice
6. Using publishImmediately=true incorrectly — bypasses transaction rollback behavior unexpectedly
7. Platform Event subscriber trigger doing DML synchronously on high-volume feed — causes delays

Change Data Capture pitfalls:
8. CDC trigger not checking ChangeEventHeader.changetype — treating CREATE and UPDATE the same
9. CDC trigger not handling null changedFields — NPE when all fields changed
10. CDC subscriber not filtering by recordIds in ChangeEventHeader — processing irrelevant org-wide changes

Each example:
- BROKEN code showing the pitfall
- Exact behavior or failure that results
- FIXED code with correct pattern
- Test approach (Platform Event test patterns, Test.enableChangeDataCapture())
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # SOQL PERFORMANCE & SELECTIVITY
    # ══════════════════════════════════════════════════════════════════════════
    ("CR-16-soql-performance", "cr_16_soql_performance.jsonl", """
Generate 10 training examples covering SOQL performance and selectivity issues.

These are NOT "SOQL in a loop" bugs — these are poorly designed queries that cause full table scans, timeouts, and degraded performance even when called once.

Cover these 10 scenarios:
1. Non-selective filter on large object — WHERE on a non-indexed field with millions of records causing full scan
2. Negative filter operator — WHERE Status != 'Closed' is never selective; show the selective alternative
3. OFFSET on large result sets — pagination with OFFSET 10000 causes full scan; use keyset pagination instead
4. NOT IN on large set — WHERE Id NOT IN :largeSet scanning entire table
5. Missing LIMIT on aggregate query — COUNT() on full table without filter
6. Querying all child records with no filter — SELECT (SELECT Id FROM Contacts) on Account without limit
7. Cross-object filter on non-indexed field — WHERE Account.Industry = 'Tech' on Opportunity — non-selective
8. LIKE with leading wildcard — WHERE Name LIKE '%Corp' never uses index
9. OR condition breaking selectivity — WHERE IndexedField = 'A' OR NonIndexedField = 'B' — full scan
10. Date formula in WHERE clause — WHERE DAY_ONLY(CreatedDate) = TODAY vs the selective indexed alternative

Each example:
- SLOW query with explanation of why it's non-selective
- What error or degradation occurs (timeout, "Your query request was running for too long", System.QueryException)
- FAST rewritten query using indexed fields, selective filters, or keyset pagination
- How to verify selectivity (Query Plan tool in Developer Console)
"""),
]

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return set(json.load(f))
    return set()

def save_checkpoint(done):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(list(done), f)

def _try_generate(prompt, max_tokens, attempts=3):
    for attempt in range(attempts):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt.strip()}
                ],
                temperature=0.7,
                max_tokens=max_tokens,
                timeout=600
            )
            raw = r.choices[0].message.content
            if raw is None:
                raise ValueError("Empty response from model")
            raw = raw.strip()

            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            raw = re.sub(r'^```json\s*', '', raw).strip()
            raw = re.sub(r'\s*```$', '', raw).strip()
            raw = re.sub(r'^```\s*', '', raw).strip()
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                raw = match.group(0)

            examples = json.loads(raw)
            if not isinstance(examples, list):
                raise ValueError("Not a JSON array")

            valid = [ex for ex in examples
                     if all(k in ex for k in ["instruction", "output"])
                     and len(ex["output"]) > 200]
            for ex in valid:
                if "input" not in ex:
                    ex["input"] = ""

            if valid:
                return valid
            print(f"  ↩️  attempt {attempt+1}: no valid examples, retrying...")

        except json.JSONDecodeError as e:
            print(f"  ↩️  attempt {attempt+1}: JSON error: {e}, retrying...")
        except Exception as e:
            print(f"  ↩️  attempt {attempt+1}: error: {e}, retrying...")
        time.sleep(2)
    return []

def generate(call_id, user_prompt):
    # First try full 10 examples
    result = _try_generate(user_prompt, max_tokens=20000, attempts=3)
    if result:
        return result
    # Fallback: ask for only 5 examples to avoid token overflow
    print(f"  ⬇️  falling back to 5 examples...")
    short_prompt = re.sub(r'Generate \d+ training examples', 'Generate 5 training examples', user_prompt)
    short_prompt = re.sub(r'Cover these \d+ ', 'Cover 5 of these ', short_prompt)
    return _try_generate(short_prompt, max_tokens=20000, attempts=3)

def main():
    done = load_checkpoint()
    remaining = [c for c in GENERATION_CALLS if c[0] not in done]

    print(f"🚀 Code Review & Debugging Dataset Generator")
    print(f"   Total calls  : {len(GENERATION_CALLS)}")
    print(f"   Already done : {len(done)}")
    print(f"   Remaining    : {len(remaining)}")
    print(f"   Output dir   : {OUTPUT_DIR}/\n")

    total = 0
    for call_id, filename, prompt in GENERATION_CALLS:
        if call_id in done:
            print(f"⏭️  {call_id}")
            continue

        output_path = OUTPUT_DIR / filename
        print(f"[{call_id}] → {filename}", end=" ", flush=True)

        examples = generate(call_id, prompt)
        if not examples:
            print(f"❌ failed")
            continue

        with open(output_path, "a") as f:
            for ex in examples:
                ex["category"] = call_id
                ex["type"] = "code_review"
                f.write(json.dumps(ex) + "\n")

        total += len(examples)
        done.add(call_id)
        save_checkpoint(done)
        print(f"✅ {len(examples)} examples")
        time.sleep(1)

    print(f"\n🎉 Done! {total} total examples")
    print("\n📊 Summary:")
    grand = 0
    for _, filename, _ in GENERATION_CALLS:
        path = OUTPUT_DIR / filename
        if path.exists():
            count = sum(1 for _ in open(path))
            grand += count
            print(f"   {filename}: {count}")
    print(f"\n   GRAND TOTAL: {grand} examples")

if __name__ == "__main__":
    main()
