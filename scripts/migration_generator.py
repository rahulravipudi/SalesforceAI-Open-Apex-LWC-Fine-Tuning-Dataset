"""
Migration Dataset Generator
Covers: Apex/LWC migrations, Salesforce CLI deployments, legacy pattern modernization.

Usage:
    pip install openai
    export MIMO_API_KEY="your-key-here"
    caffeinate -i python3 migration_generator.py
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

OUTPUT_DIR      = Path("migration_dataset")
CHECKPOINT_FILE = Path("migration_checkpoint.json")
OUTPUT_DIR.mkdir(exist_ok=True)

SYSTEM_PROMPT = """You are an expert Salesforce architect generating migration and deployment training examples.

## OFFICIAL DOCUMENTATION REFERENCES
Salesforce CLI Reference: https://developer.salesforce.com/docs/atlas.en-us.sfdx_cli_reference.meta/sfdx_cli_reference/cli_reference.htm
Salesforce DX Developer Guide: https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_intro.htm
Metadata API Developer Guide: https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_intro.htm
Unlocked Packages: https://developer.salesforce.com/docs/atlas.en-us.sfdx_dev.meta/sfdx_dev/sfdx_dev_unlocked_pkg_intro.htm

## KEY CLI COMMANDS TO KNOW
sf org login web                          -- authenticate to org
sf project deploy start                   -- deploy metadata to org
sf project retrieve start                 -- retrieve metadata from org
sf apex run                               -- run anonymous Apex
sf apex test run                          -- run tests
sf data query                             -- run SOQL query
sf org create scratch                     -- create scratch org
sf package create                         -- create unlocked package
sf package version create                 -- create package version
sf package install                        -- install package

## MIGRATION PRINCIPLES
- Always test in sandbox before production
- Use change sets for simple migrations, Salesforce DX for complex
- Version control everything — never deploy directly from org
- Run all tests before deployment — require 75% coverage minimum
- Have a rollback plan before every production deployment
- Migrate data separately from metadata

## OUTPUT FORMAT
Output ONLY a valid JSON array. No markdown fences. No preamble.

[
  {
    "instruction": "Clear migration or deployment task description",
    "input": "",
    "output": "Complete migration guide, CLI commands, or code conversion"
  }
]"""

GENERATION_CALLS = [

    # ══════════════════════════════════════════════════════════════════════════
    # SALESFORCE CLI — DEPLOYMENT
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-01-cli-basics", "migration_MIG01_cli_basics.jsonl", """
Generate 10 Salesforce CLI deployment training examples covering essential deployment tasks.

Each example should be a realistic developer task with complete CLI commands and explanation.

Cover these 10 scenarios:
1. Deploy a single Apex class to a sandbox using sf project deploy start
2. Deploy multiple metadata types (trigger + class + custom object) together
3. Retrieve metadata from production to local project
4. Run Apex tests after deployment and check results
5. Deploy with --test-level RunLocalTests and interpret the output
6. Deploy to multiple orgs (dev sandbox → QA sandbox → UAT sandbox → production)
7. Check deployment status with sf project deploy report
8. Perform a destructive change — delete a component from production safely
9. Use --dry-run flag to validate deployment without committing
10. Fix a failed deployment — interpret error messages and correct issues

Each output must include:
- The exact sf CLI commands with all flags
- Expected output snippets showing success
- Common errors and how to handle them
- The project structure (force-app/main/default layout)
"""),

    ("MIG-02-cli-advanced", "migration_MIG02_cli_advanced.jsonl", """
Generate 10 advanced Salesforce CLI training examples.

Cover these 10 advanced CLI scenarios:
1. Create and authenticate to a scratch org for development
2. Set up a scratch org definition file (project-scratch-def.json) with features
3. Push source to scratch org and pull changes back
4. Create an unlocked package from existing metadata
5. Create a package version and promote it to released
6. Install an unlocked package into a sandbox
7. Set up CI/CD pipeline — GitHub Actions workflow for automated deployment
8. Use sf data query to run SOQL from command line
9. Use sf apex run to execute anonymous Apex from file
10. Set up multiple org aliases and switch between them

Each output must include:
- Complete CLI commands with all required flags
- File contents where relevant (sfdx-project.json, scratch def, GitHub workflow YAML)
- Explanation of what each command does and when to use it
"""),

    ("MIG-03-package-xml", "migration_MIG03_package_xml.jsonl", """
Generate 10 training examples covering package.xml and metadata retrieval.

Cover these 10 scenarios:
1. Write a package.xml to retrieve a specific Apex class and its test
2. Write a package.xml for a complete feature (trigger + class + object + fields + layout)
3. Use wildcard (*) in package.xml for all classes vs specific list — tradeoffs
4. Retrieve all custom objects and their fields
5. Retrieve Flow metadata including active versions
6. Retrieve Permission Sets and Profiles
7. Retrieve Custom Metadata Types and their records
8. Build package.xml from org using sf project generate manifest
9. Validate package.xml before deployment
10. Destructive package.xml — remove components from org

Each output must include:
- Complete package.xml XML content
- The sf CLI command to use it
- Common mistakes (wrong API version, wrong member name format)
- How to verify the retrieval was complete
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # LEGACY PATTERN MIGRATIONS
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-04-workflow-to-flow", "migration_MIG04_workflow_to_flow.jsonl", """
Generate 10 training examples for migrating Workflow Rules to Flow + Apex.

Workflow Rules are being retired — developers need to migrate them.

Cover these 10 migration scenarios with domain rotation:
1. FSI: Field update workflow on LoanApplication__c → Record-Triggered Flow + Apex
2. Healthcare: Email alert workflow on Appointment__c → Flow with Apex email action
3. Manufacturing: Task creation workflow on WorkOrder__c → Flow + InvocableMethod
4. Retail: Field update on Order status change → Record-Triggered Flow
5. Telco: Outbound message workflow → Flow + Apex REST callout invocable
6. Energy: Time-based workflow (7 days after close) → Scheduled Flow
7. PS: Cross-object field update workflow → Flow with Update Records element
8. Insurance: Multiple actions workflow → Flow with multiple action elements
9. Generic: Show the Workflow Rule metadata XML + equivalent Flow setup + any Apex needed
10. Generic: Common gotchas — order of execution differences, re-evaluation differences

Each output:
- Describe the original Workflow Rule configuration
- Provide the equivalent implementation (Flow metadata XML or description + any Apex)
- Highlight behavioral differences to test
- Deployment steps for the new Flow
"""),

    ("MIG-05-process-builder-to-flow", "migration_MIG05_pb_to_flow.jsonl", """
Generate 10 training examples for migrating Process Builder to Flow.

Process Builder is also being retired.

Cover these 10 scenarios:
1. Simple field update Process Builder → Record-Triggered Flow
2. Process Builder with multiple criteria groups → Flow with decision elements
3. Process Builder calling Apex → Flow with Apex action (InvocableMethod)
4. Process Builder creating child records → Flow Create Records element
5. Process Builder with scheduled actions → Scheduled Path in Flow
6. Process Builder with cross-object field updates → Flow with Update Records
7. Process Builder with Email Alerts → Flow Send Email action
8. Process Builder with chained processes → Single consolidated Flow
9. Process Builder calling another Process → Flow subflow pattern
10. Process Builder with custom metadata lookup → Flow Get Records element

Each output includes:
- Original Process Builder configuration description
- Equivalent Flow implementation with Apex where needed
- Migration checklist — things to verify after migration
- Test plan to confirm behavior matches
"""),

    ("MIG-06-future-to-queueable", "migration_MIG06_future_to_queueable.jsonl", """
Generate 10 training examples for migrating @future methods to Queueable Apex.

Cover these 10 scenarios with domain rotation:
1. FSI: @future credit check callout → Queueable with AllowsCallouts
2. Healthcare: @future EHR sync → Queueable with retry and Finalizer
3. Manufacturing: @future ERP update → Queueable with chaining
4. Retail: @future inventory sync → Queueable with progress tracking
5. Telco: @future provisioning → Queueable with status update
6. Energy: @future meter submission → Queueable with error logging
7. PS: @future report generation → Queueable with platform event notification
8. Insurance: @future adjuster notification → Queueable with finalizer
9. Generic: @future(callout=true) → Queueable with AllowsCallouts interface
10. Generic: Multiple @future methods → single Queueable with job type parameter

Each output:
- Original @future code (the bad version)
- Why Queueable is better (monitoring, chaining, finalizer, parameters)
- Complete Queueable replacement
- How to update callers to use System.enqueueJob()
- Test class for the Queueable
"""),

    ("MIG-07-trigger-modernization", "migration_MIG07_trigger_modernization.jsonl", """
Generate 10 training examples for modernizing legacy triggers.

Cover these 10 legacy trigger patterns and their modern equivalents:
1. Logic directly in trigger → TriggerHandler pattern with delegation
2. Multiple triggers on same object → Single trigger + handler dispatch
3. No recursion guard → Add static Boolean guard
4. SOQL in trigger → Move to Map pre-query before loop
5. DML in trigger loop → Accumulate list, single DML outside loop
6. Direct field updates in trigger → Before context handler method
7. @future calls in trigger → Queueable from handler
8. No sharing declaration on handler → Add with sharing
9. No error handling → try/catch with custom exception
10. Hardcoded values in trigger → Custom Metadata driven configuration

Each output:
- ORIGINAL legacy trigger (realistic, showing the anti-pattern)
- MODERNIZED trigger + handler
- What changed and why
- Test class for the modernized version
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # APEX API VERSION MIGRATIONS
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-08-apex-modernization", "migration_MIG08_apex_modernization.jsonl", """
Generate 10 training examples for modernizing old Apex patterns.

Cover these 10 Apex modernization scenarios:
1. String.escapeSingleQuotes → Database.queryWithBinds() for dynamic SOQL
2. Old-style list iteration → Enhanced for loop and stream-style patterns
3. Manual null checking → Safe navigation operator (?.) in Apex
4. System.assert() → System.assertEquals() with descriptive message
5. Insert without SaveResult → Database.insert() with allOrNone=false + result checking
6. Static SOQL with hardcoded fields → Field set dynamic SOQL
7. Manual JSON building with string concat → JSON.serialize() pattern
8. PageReference redirect in Visualforce controller → NavigationMixin in LWC
9. Custom settings → Custom Metadata Types (when to migrate and how)
10. Old WebService annotation → @RestResource modern REST API

Each output:
- OLD code with the deprecated/anti-pattern approach
- WHY the old approach is problematic
- NEW modernized code
- Test class comparison
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # DATA MIGRATION
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-09-data-migration", "migration_MIG09_data_migration.jsonl", """
Generate 10 training examples covering data migration in Salesforce.

Cover these 10 data migration scenarios with domain rotation:
1. FSI: Migrate loan data from external system using Batch Apex + external IDs
2. Healthcare: Migrate patient records preserving relationships — parent before children
3. Manufacturing: Upsert product catalog using SKU as external ID
4. Retail: Migrate historical orders with order lines — transaction control
5. Telco: Migrate usage records in bulk — 10M records in chunks using keyset
6. General: Data Loader CLI usage — bulk import from CSV file
7. General: Bulk API 2.0 — upload large CSV directly via REST
8. General: Pre-migration checklist — validation, deduplication, field mapping
9. General: Post-migration verification — count checks, spot checks, reconciliation
10. General: Rollback strategy — what to do if migration fails partway

Each output includes:
- Migration Apex code or CLI commands
- Error handling and partial failure recovery
- Verification queries to run after migration
- Common pitfalls for that data type
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # CI/CD AND DEVOPS
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-10-cicd", "migration_MIG10_cicd.jsonl", """
Generate 10 training examples covering Salesforce CI/CD and DevOps patterns.

Cover these 10 scenarios:
1. Set up GitHub Actions for automated Salesforce deployment on push to main
2. Set up GitHub Actions to run Apex tests on every pull request
3. Configure sfdx-project.json for a multi-package project
4. Set up scratch org pooling for parallel CI runs
5. Implement git branching strategy for Salesforce development (GitFlow adapted)
6. Set up environment-specific configuration using Custom Metadata per org
7. Configure deployment order for dependent packages
8. Set up Slack notification on deployment success/failure
9. Implement deployment gates — require test coverage, static analysis
10. Handle merge conflicts in Salesforce XML metadata files

Each output includes:
- GitHub Actions YAML workflow files (complete)
- sfdx-project.json configuration
- Shell scripts where needed
- Explanation of the strategy and why
"""),

    ("MIG-11-sandbox-management", "migration_MIG11_sandbox.jsonl", """
Generate 10 training examples for Salesforce sandbox management.

Cover these 10 scenarios:
1. Create and set up a new Developer sandbox using CLI
2. Refresh a sandbox and preserve configuration
3. Set up sandbox post-copy Apex class to configure environment
4. Seed a sandbox with test data using Apex data factory
5. Promote code from Developer → Full sandbox → Production
6. Handle sandbox-specific configuration (different named credentials per env)
7. Authorize CI/CD service account to sandbox non-interactively
8. Clean up old sandboxes and sandbox licenses
9. Compare metadata between two orgs using sf project generate manifest
10. Set up a partial data sandbox with masked sensitive data

Each output includes complete CLI commands and configuration files.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # SPECIFIC MIGRATION GUIDES
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-12-soap-to-rest", "migration_MIG12_soap_to_rest.jsonl", """
Generate 10 training examples for migrating SOAP integrations to REST.

Cover these 10 scenarios with domain rotation:
1. FSI: Migrate bank SOAP payment API to REST JSON equivalent
2. Healthcare: Migrate HL7 SOAP service to FHIR REST API
3. Manufacturing: Migrate ERP SOAP to REST OData endpoint
4. General: Replace WSDL2Apex stub with REST HttpRequest pattern
5. General: Compare SOAP vs REST — when REST is better (and when SOAP still makes sense)
6. General: Migrate SOAP authentication (WS-Security) to OAuth 2.0
7. General: Handle SOAP error faults vs REST error status codes
8. General: Map XML SOAP envelope to JSON REST body
9. General: Migrate synchronous SOAP to async REST with polling
10. General: Test migration — HttpCalloutMock for both old SOAP and new REST

Each output: original SOAP Apex + equivalent REST Apex + behavioral comparison + test.
"""),

    ("MIG-13-classic-to-lightning", "migration_MIG13_classic_to_lightning.jsonl", """
Generate 10 training examples for migrating Salesforce Classic features to Lightning.

Cover these 10 scenarios:
1. S-Control → Lightning Web Component equivalent
2. Custom Button (JavaScript) → Quick Action with LWC
3. Sidebar component → Utility Bar LWC
4. Classic Dashboard → Lightning Dashboard with SOQL-powered LWC
5. Classic Home Page → Lightning App Page with LWC
6. Custom Link → Navigation button in LWC
7. Classic Email Template → Lightning Email Template
8. Classic Report Type → Report type with Lightning Report Builder
9. JavaScript Buttons → LWC action buttons
10. Classic Console → Lightning Console with Workspace API

Each output: original Classic approach + Lightning equivalent + migration steps.
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # AURA TO LWC MIGRATION
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-14-aura-to-lwc", "migration_MIG14_aura_to_lwc.jsonl", """
Generate 10 training examples for migrating Aura Components to Lightning Web Components (LWC).

This is the most actively relevant migration for Salesforce developers today. Aura is still supported but LWC is the modern standard and Salesforce is pushing teams to migrate.

Cover these 10 migration scenarios:

Core syntax and lifecycle:
1. Aura component attribute + helper method → LWC reactive property + JS method (component.get/set → direct property assignment)
2. Aura init handler (afterScriptsLoaded / init) → LWC connectedCallback lifecycle hook
3. Aura component event (APPLICATION vs COMPONENT event) → LWC custom event with bubbles/composed options
4. Aura action ($A.enqueueAction) → LWC imperative Apex call with async/await

Data and server calls:
5. Aura @AuraEnabled Apex call with callback → LWC @wire adapter + wireResult handling
6. Aura force:recordData → LWC lightning-record-view-form or getRecord wire adapter
7. Aura storable action (caching) → LWC @wire automatic caching behavior

Navigation and UI:
8. Aura force:navigateToURL / force:navigateToSObject → LWC NavigationMixin.Navigate
9. Aura ui:message / aura:if → LWC lwc:if + ShowToastEvent for messages

Composition:
10. Aura component with aura:method for parent-to-child calls → LWC with @api method exposure

For each example:
- Complete ORIGINAL Aura component (.cmp + controller.js + helper.js) — realistic, not trivial
- Complete MIGRATED LWC (.html + .js) achieving identical behavior
- Key conceptual shift explained (e.g. "Aura's two-way binding → LWC's explicit event dispatch")
- Migration gotchas specific to that pattern
- Test class if Apex was involved
"""),

    # ══════════════════════════════════════════════════════════════════════════
    # PROFILES TO PERMISSION SET GROUPS
    # ══════════════════════════════════════════════════════════════════════════
    ("MIG-15-profiles-to-psg", "migration_MIG15_profiles_to_psg.jsonl", """
Generate 10 training examples for migrating from Profile-based access control to Permission Sets and Permission Set Groups.

Salesforce has announced a long-term direction away from profiles toward permission set groups — many orgs are actively migrating.

Cover these 10 scenarios:
1. Understand the difference — Profile vs Permission Set vs Permission Set Group; when to use each
2. Audit existing profiles — sf CLI commands to export profile metadata and analyze what's in them
3. Extract object CRUD permissions from a Profile → create equivalent Permission Set
4. Extract field-level security from a Profile → create FLS Permission Set
5. Extract App and Tab visibility from a Profile → App Permission Set
6. Extract Apex class and VF page access from a Profile → create Access Permission Set
7. Group Permission Sets into a Permission Set Group — the PSG design pattern
8. Assign Permission Set Group to users via Apex and CLI
9. Handle the "minimum access profile" — stripping a profile down to baseline after migration
10. Test and validate migration — verify users retain same access, catch regressions

Each output:
- Metadata XML snippets for Permission Sets / PSG
- sf CLI commands to deploy and assign
- Apex code to assign PSG to users programmatically
- Verification queries (SOQL on PermissionSetAssignment)
- Common migration pitfalls (record types still on profiles, etc.)
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
                raise ValueError("Not a list")

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
    print(f"🚀 Migration Dataset Generator")
    print(f"   Total calls  : {len(GENERATION_CALLS)}")
    print(f"   Already done : {len(done)}")
    print(f"   Remaining    : {sum(1 for c in GENERATION_CALLS if c[0] not in done)}")
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
                ex["type"] = "migration"
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
