"""
Synthetic GraphQL LWC Dataset Generator — v3 (Official Docs Based)
Generates LWC components using the Salesforce GraphQL wire adapter.

Key fix: Uses lightning/graphql (new recommended module) not lightning/uiGraphQLApi
Official docs: https://developer.salesforce.com/docs/platform/graphql/guide/graphql-wire-lwc.html

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    caffeinate -i python3 generate_synthetic_graphql.py

Output: synthetic_graphql_dataset_v2.jsonl
"""

import os, json, time, re
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com"
)
MODEL = "deepseek-v4-pro"

# ── SYSTEM PROMPT WITH OFFICIAL DOCS EMBEDDED ─────────────────────────────────
SYSTEM_PROMPT = """You are a senior Salesforce LWC developer specializing in the Salesforce GraphQL wire adapter.

Below is the official Salesforce documentation for the GraphQL wire adapter. Read it carefully before generating any code.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OFFICIAL SALESFORCE GRAPHQL WIRE ADAPTER DOCS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Module Import — ALWAYS use lightning/graphql (NOT lightning/uiGraphQLApi)
```javascript
import { LightningElement, wire } from 'lwc';
import { gql, graphql } from 'lightning/graphql';
// For refresh: import { gql, graphql, refreshGraphQL } from 'lightning/graphql';
```
NOTE: lightning/uiGraphQLApi is the OLD module. The recommended module is lightning/graphql.
Only use lightning/uiGraphQLApi for Mobile Offline use cases.

## Wire Adapter Syntax
```javascript
@wire(graphql, {
    query: QUERY_CONSTANT,
    variables: '$myVariablesGetter'   // string reference to a getter
})
wiredResult;

// Variables MUST be a getter for reactivity:
get myVariablesGetter() {
    return { after: this.cursor, searchTerm: this.search };
}
```

## Query Structure — CRITICAL RULES
1. Every scalar field MUST have { value } subfield: Name { value }, Phone { value }
2. Id is the only field that does NOT need { value }
3. Always include edges { node { ... } } for list queries
4. Always include pageInfo { hasNextPage endCursor } for paginated queries
5. Use first: N to limit results (default is 10, max 2000)
6. Use after: $cursor for cursor-based pagination
7. Use where: { FieldName: { eq: $value } } for filtering
8. Use orderBy: { FieldName: { order: ASC } } for sorting

```graphql
query getAccounts($after: String, $searchTerm: String) {
    uiapi {
        query {
            Account(
                first: 10
                after: $after
                where: { Name: { like: $searchTerm } }
                orderBy: { Name: { order: ASC } }
            ) {
                edges {
                    node {
                        Id
                        Name { value }
                        Phone { value }
                        BillingCity { value }
                        Industry { value }
                        AnnualRevenue { value }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
}
```

## Data Mapping — CRITICAL RULES
1. ALWAYS extract .value from scalar fields: edge.node.Name.value NOT edge.node.Name
2. Use optional chaining for nullable fields: edge.node.Phone?.value ?? ''
3. Id does NOT need .value: edge.node.Id
4. Access pageInfo: data.uiapi.query.Account.pageInfo

```javascript
wiredResult({ data, errors }) {
    this.isLoading = false;
    if (errors) {
        this.error = errors[0]?.message ?? 'An error occurred';
        return;
    }
    if (data) {
        const result = data.uiapi.query.Account;
        // ALWAYS extract .value from each field
        this.accounts = result.edges.map(edge => ({
            id: edge.node.Id,                          // Id — no .value needed
            name: edge.node.Name.value,                // required field — .value
            phone: edge.node.Phone?.value ?? '',       // nullable — optional chain
            city: edge.node.BillingCity?.value ?? '',  // nullable — optional chain
        }));
        this.hasNextPage = result.pageInfo.hasNextPage;
        this.endCursor = result.pageInfo.endCursor;
    }
}
```

## Pagination — Official Pattern
- Forward pagination only (backward with last/before is NOT supported)
- cursor must be a reactive property — changing it triggers re-wire
- Store cursor history in an array for Previous button

```javascript
cursor = null;        // reactive — changing triggers re-wire via getter
hasNextPage = false;
endCursor = null;
cursorHistory = [];   // for Previous button

get graphqlVariables() {
    return { after: this.cursor };
}

handleNext() {
    if (this.hasNextPage) {
        this.cursorHistory = [...this.cursorHistory, this.cursor];
        this.cursor = this.endCursor;
        this.isLoading = true;
    }
}

handlePrevious() {
    const history = [...this.cursorHistory];
    this.cursor = history.pop() ?? null;
    this.cursorHistory = history;
    this.isLoading = true;
}

handleReset() {
    this.cursor = null;
    this.cursorHistory = [];
    this.isLoading = true;
}
```

## Error Handling — CRITICAL
- GraphQL wire uses errors (plural array) NOT error like other wire adapters
- Always use optional chaining: errors[0]?.message

```javascript
wiredResult({ data, errors }) {
    if (errors) {
        this.error = errors[0]?.message ?? 'Unknown error';
        return;
    }
}
```

## Best Practices from Official Docs
1. Use first argument to limit results — never query without a limit
2. Do NOT request totalCount unless needed — causes full table scan
3. Use variables for all dynamic values — never string interpolation in query
4. Add aliases to custom object/field names to preserve referential integrity
5. Use operationName for debugging: query getAccounts(...) not just query (...)
6. Combine multiple objects in one query instead of multiple wire adapters
7. Use where filters to reduce returned records

## Template Syntax — ALWAYS use lwc:if/lwc:else (NEVER if:true/if:false)
```html
<template lwc:if={isLoading}>
    <lightning-spinner alternative-text="Loading"></lightning-spinner>
</template>
<template lwc:elseif={error}>
    <div class="slds-text-color_error">{error}</div>
</template>
<template lwc:else>
    <!-- main content -->
</template>
```

## Complete Working Example — Account List with Pagination
```html
<!-- accountList.html -->
<template>
    <lightning-card title="Accounts" icon-name="standard:account">
        <div class="slds-p-around_medium">
            <template lwc:if={isLoading}>
                <div class="slds-align_absolute-center slds-p-around_medium">
                    <lightning-spinner alternative-text="Loading accounts"></lightning-spinner>
                </div>
            </template>
            <template lwc:elseif={error}>
                <div class="slds-notify slds-notify_alert slds-alert_error" role="alert">
                    <span>{error}</span>
                </div>
            </template>
            <template lwc:else>
                <lightning-datatable
                    key-field="id"
                    data={accounts}
                    columns={columns}
                    hide-checkbox-column>
                </lightning-datatable>
                <div class="slds-m-top_medium slds-grid slds-grid_align-spread">
                    <lightning-button
                        label="Previous"
                        onclick={handlePrevious}
                        disabled={isPreviousDisabled}>
                    </lightning-button>
                    <lightning-button
                        label="Next"
                        variant="brand"
                        onclick={handleNext}
                        disabled={!hasNextPage}>
                    </lightning-button>
                </div>
            </template>
        </div>
    </lightning-card>
</template>
```

```javascript
// accountList.js
import { LightningElement, wire } from 'lwc';
import { gql, graphql } from 'lightning/graphql';

const ACCOUNT_QUERY = gql`
    query getAccounts($after: String) {
        uiapi {
            query {
                Account(
                    first: 10
                    after: $after
                    orderBy: { Name: { order: ASC } }
                ) {
                    edges {
                        node {
                            Id
                            Name { value }
                            Phone { value }
                            BillingCity { value }
                            Industry { value }
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
    }
`;

export default class AccountList extends LightningElement {
    /** @type {Array} List of account records for the datatable */
    accounts = [];
    isLoading = true;
    error = null;
    cursor = null;
    hasNextPage = false;
    endCursor = null;
    cursorHistory = [];

    columns = [
        { label: 'Name', fieldName: 'name', type: 'text' },
        { label: 'Phone', fieldName: 'phone', type: 'phone' },
        { label: 'City', fieldName: 'city', type: 'text' },
        { label: 'Industry', fieldName: 'industry', type: 'text' },
    ];

    get graphqlVariables() {
        return { after: this.cursor };
    }

    get isPreviousDisabled() {
        return this.cursorHistory.length === 0;
    }

    @wire(graphql, {
        query: ACCOUNT_QUERY,
        variables: '$graphqlVariables'
    })
    wiredResult({ data, errors }) {
        this.isLoading = false;
        if (errors) {
            this.error = errors[0]?.message ?? 'Failed to load accounts';
            return;
        }
        if (data) {
            const result = data.uiapi.query.Account;
            this.accounts = result.edges.map(edge => ({
                id: edge.node.Id,
                name: edge.node.Name.value,
                phone: edge.node.Phone?.value ?? '',
                city: edge.node.BillingCity?.value ?? '',
                industry: edge.node.Industry?.value ?? '',
            }));
            this.hasNextPage = result.pageInfo.hasNextPage;
            this.endCursor = result.pageInfo.endCursor;
        }
    }

    handleNext() {
        if (this.hasNextPage) {
            this.cursorHistory = [...this.cursorHistory, this.cursor];
            this.cursor = this.endCursor;
            this.isLoading = true;
        }
    }

    handlePrevious() {
        const history = [...this.cursorHistory];
        this.cursor = history.pop() ?? null;
        this.cursorHistory = history;
        this.isLoading = true;
    }

    handleReset() {
        this.cursor = null;
        this.cursorHistory = [];
        this.isLoading = true;
    }
}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF OFFICIAL DOCS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## CHECKLIST — Before finalizing any component, verify:
☐ Import is from 'lightning/graphql' NOT 'lightning/uiGraphQLApi'
☐ Every scalar field has { value } in the query
☐ Data mapping uses .value: edge.node.Name.value
☐ Nullable fields use optional chaining: edge.node.Phone?.value ?? ''
☐ pageInfo includes hasNextPage and endCursor
☐ cursor is a reactive property (changing triggers re-wire via getter)
☐ errors (plural) used not error
☐ Template uses lwc:if/lwc:else NOT if:true/if:false
☐ No hardcoded Salesforce IDs
☐ Loading state handled correctly

## Format — EXACTLY this structure, no extra text:
=== INSTRUCTION ===
<one clear sentence>

=== HTML ===
<complete .html file>

=== JS ===
<complete .js file>

=== CSS ===
<complete .css file or NONE>"""

# ── PROMPTS ───────────────────────────────────────────────────────────────────
GRAPHQL_PROMPTS = [
    # Basic queries
    "Build an LWC using the @wire graphQL adapter from lightning/graphql to fetch a list of Accounts with Name, Phone, BillingCity, and Industry fields in a lightning-datatable with loading and error handling.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql to fetch a single Account by recordId with Name, Type, AnnualRevenue, Website using a reactive recordId variable.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql to fetch Contacts with Name, Email, Phone, Title in a card grid showing initials as avatar.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql to fetch Opportunities with Name, StageName, Amount, CloseDate, Probability in a lightning-datatable.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql to fetch Cases with Subject, Status, Priority, CreatedDate with conditional row coloring based on Priority.",

    # Pagination
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with cursor-based Next/Previous pagination showing 10 Accounts per page — use cursorHistory array for Previous button.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with cursor-based pagination for Contacts — show page number, loading state between transitions, and a Reset button.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with infinite scroll for Opportunities — append new records to the list on scroll using endCursor.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql paginating Leads with configurable page size selector (10, 25, 50) that resets cursor to null on size change.",

    # Filtering
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with reactive Account Type combobox filter — changing selection updates graphqlVariables getter and re-queries.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with debounced 300ms search input filtering Contacts by Name using reactive $searchTerm variable.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with multiple reactive filters — Status and Priority comboboxes for Cases — combined in graphqlVariables getter.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with date range filter for Opportunities CloseDate — start and end date inputs as reactive variables.",

    # Sorting
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with sortable column headers changing orderBy variable reactively for Account list.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql with multi-column sorting for Opportunities — ascending/descending toggle per column with sort icons.",

    # Nested/related records
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching Account with nested Contacts (Name, Email, Phone) in one query — all scalar fields need { value }.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching Opportunities with nested Account Name and Owner Name in one query — all scalars need { value }.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching Contact with nested Cases (Subject, Status, Priority) displaying both in tabs.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching Account with nested Contacts, Opportunities, and Cases all in one query with separate sections.",

    # Aggregates
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching aggregate Opportunity data — total count and sum of Amount — shown as summary tiles.",
    "Build an LWC using the @wire graphQL adapter from lightning/graphql fetching Opportunity count grouped by StageName displayed as SLDS horizontal bar chart.",

    # Combined
    "Build an LWC using @wire graphQL from lightning/graphql for Account list AND @wire getRecord from lightning/uiRecordApi for selected Account details — combined isLoading getter.",
    "Build an LWC using @wire graphQL from lightning/graphql that reactively re-queries when host recordId changes, showing related Contacts immediately.",

    # Domain-specific — Financial Services
    "Build an LWC using @wire graphQL from lightning/graphql for a bank fetching Loan_Application__c with Status__c { value }, Amount__c { value }, SubmittedDate__c { value } and cursor pagination.",
    "Build an LWC using @wire graphQL from lightning/graphql for wealth management fetching Portfolio__c with nested Financial_Account__c children — all scalars need { value }.",

    # Domain-specific — Healthcare
    "Build an LWC using @wire graphQL from lightning/graphql for a hospital fetching Patient__c with nested Appointment__c records — all scalar fields need { value } subfields.",
    "Build an LWC using @wire graphQL from lightning/graphql for healthcare fetching Care_Plan__c filtered by Status__c with cursor pagination.",

    # Domain-specific — Manufacturing
    "Build an LWC using @wire graphQL from lightning/graphql for manufacturing fetching Work_Order__c with Status__c { value } filter and nested Asset__c data.",
    "Build an LWC using @wire graphQL from lightning/graphql for manufacturing fetching Quality_Inspection__c sorted by InspectionDate__c with pagination.",

    # Domain-specific — Retail
    "Build an LWC using @wire graphQL from lightning/graphql for retail fetching Order__c with nested Product__c line items — all scalar fields need { value }.",
    "Build an LWC using @wire graphQL from lightning/graphql for retail fetching Loyalty_Points__c filtered by Member__c reactively on a record page.",

    # Domain-specific — Telecom
    "Build an LWC using @wire graphQL from lightning/graphql for telecom fetching Service_Request__c with Status__c filter and cursor pagination.",
    "Build an LWC using @wire graphQL from lightning/graphql for telecom fetching Usage_Summary__c with date range filtering and aggregate total usage display.",

    # Domain-specific — Energy
    "Build an LWC using @wire graphQL from lightning/graphql for a utility company fetching Meter__c with nested Energy_Usage__c readings — all scalars need { value }.",
    "Build an LWC using @wire graphQL from lightning/graphql for energy fetching Outage_Report__c sorted by ReportedDate__c descending with pagination.",

    # Domain-specific — Professional Services
    "Build an LWC using @wire graphQL from lightning/graphql for consulting fetching Project__c with nested Milestone__c and Timesheet__c in one query.",
    "Build an LWC using @wire graphQL from lightning/graphql for professional services fetching Resource__c with availability filter and skill-based sorting.",

    # Domain-specific — Insurance
    "Build an LWC using @wire graphQL from lightning/graphql for insurance fetching Claim__c with Status__c filter, nested Policy__c data, and cursor pagination.",
    "Build an LWC using @wire graphQL from lightning/graphql for insurance fetching Risk_Assessment__c sorted by RiskScore__c with threshold-based row coloring.",

    # Advanced
    "Build an LWC using @wire graphQL from lightning/graphql with live debounced search (300ms), spinner during re-query, and text highlighting in results.",
    "Build an LWC using @wire graphQL from lightning/graphql with client-side caching — show last result while new query loads after filter change.",
    "Build an LWC using @wire graphQL from lightning/graphql with empty state illustration when edges array is empty after successful query.",
    "Build an LWC using @wire graphQL from lightning/graphql with a Retry button that resets cursor and clears error to re-trigger the wire adapter.",
    "Build an LWC using @wire graphQL from lightning/graphql for a split-pane layout — list on left fetched via GraphQL, selected record details on right via imperative Apex.",

    # Testing
    "Write Jest unit tests for an LWC using @wire graphQL from lightning/graphql — mock the adapter, test loading state, test correct .value field mapping, and test error state.",
    "Write Jest unit tests for an LWC GraphQL pagination component — test Next advances cursor, Previous goes back using cursorHistory, and Reset clears to null.",
    "Write Jest unit tests for an LWC GraphQL reactive filter component — test that changing combobox updates graphqlVariables getter and re-triggers wire.",
]

# ── PARSER ────────────────────────────────────────────────────────────────────
def parse_response(raw):
    try:
        instruction = re.search(r'=== INSTRUCTION ===\s*(.*?)\s*=== HTML ===', raw, re.DOTALL)
        html        = re.search(r'=== HTML ===\s*(.*?)\s*=== JS ===', raw, re.DOTALL)
        js          = re.search(r'=== JS ===\s*(.*?)\s*=== CSS ===', raw, re.DOTALL)
        css         = re.search(r'=== CSS ===\s*(.*?)$', raw, re.DOTALL)
        if not all([instruction, html, js]):
            return None
        html_text = html.group(1).strip()
        js_text   = js.group(1).strip()
        css_text  = css.group(1).strip() if css else "NONE"
        if css_text.upper() == "NONE":
            css_text = ""
        for lang in ['html', 'javascript', 'js', 'css', '']:
            html_text = re.sub(rf'^```{lang}\s*', '', html_text, flags=re.MULTILINE).strip()
            html_text = re.sub(r'\s*```$', '', html_text).strip()
            js_text   = re.sub(rf'^```{lang}\s*', '', js_text,   flags=re.MULTILINE).strip()
            js_text   = re.sub(r'\s*```$', '', js_text).strip()
        name_match = re.search(r'export default class (\w+)', js_text)
        name       = name_match.group(1) if name_match else "GraphqlComponent"
        file_name  = name[0].lower() + name[1:]
        combined   = f"<!-- {file_name}.html -->\n{html_text}\n\n// {file_name}.js\n{js_text}"
        if css_text:
            combined += f"\n\n/* {file_name}.css */\n{css_text}"
        return {
            "instruction": instruction.group(1).strip(),
            "input": "",
            "output": combined,
            "source": "synthetic_graphql",
            "type": "lwc",
            "category": "GraphQL Wire Adapter"
        }
    except Exception:
        return None

# ── GENERATOR ─────────────────────────────────────────────────────────────────
def generate(prompt):
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
                temperature=0.2,
                max_tokens=8000
            )
            raw    = r.choices[0].message.content
            raw    = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            parsed = parse_response(raw)
            if parsed and len(parsed["output"]) > 200:
                return parsed
            print(f"  ↩️  attempt {attempt+1} parse failed...", end=" ", flush=True)
        except Exception as e:
            print(f"  ⚠️  attempt {attempt+1} error: {e}", end=" ", flush=True)
        time.sleep(2)
    return None

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    output_path     = Path("synthetic_graphql_dataset_v2.jsonl")
    checkpoint_path = Path("synthetic_graphql_v2_checkpoint.jsonl")

    done_prompts = set()
    results      = []
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                rec = json.loads(line)
                done_prompts.add(rec["prompt"])
                results.append(rec["example"])
        print(f"▶️  Resuming — {len(results)} already generated")

    remaining = [p for p in GRAPHQL_PROMPTS if p not in done_prompts]
    print(f"📋 {len(remaining)} GraphQL components to generate")
    print(f"   Model: {MODEL}")
    print(f"   Temperature: 0.2 (precise, not creative)")
    print(f"   Module: lightning/graphql (official recommended)\n")

    with open(checkpoint_path, "a") as ckpt:
        for i, prompt in enumerate(remaining):
            print(f"[{i+1}/{len(remaining)}] {prompt[:75]}...", end=" ", flush=True)
            example = generate(prompt)
            if not example:
                print("⚠️  skipped")
                continue
            results.append(example)
            ckpt.write(json.dumps({"prompt": prompt, "example": example}) + "\n")
            ckpt.flush()
            print(f"✅ ({len(example['output'].splitlines())} lines)")
            time.sleep(1)

    with open(output_path, "w") as f:
        for ex in results:
            f.write(json.dumps(ex) + "\n")

    print(f"\n🎉 Done!")
    print(f"   synthetic_graphql_dataset_v2.jsonl → {len(results)} GraphQL components")
    print(f"   Module used: lightning/graphql (official recommended)")

if __name__ == "__main__":
    main()
