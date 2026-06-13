"""
Expanded Synthetic LWC Dataset Generator — 20 Categories x 8 Domains
Target: 800 examples

Structure:
  20 categories x 8 generic variations = 160 generic
  20 categories x 8 domains x 4 domain variations = 640 domain-specific
  Total = 800 examples


"""

import os, json, time, re
from pathlib import Path
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["NVIDIA_API_KEY"],
    base_url="https://integrate.api.nvidia.com/v1"
)
MODEL = "Model of your choice"

SYSTEM_PROMPT = """You are a senior Salesforce LWC developer with 10 years of experience.
When asked to build a Lightning Web Component, you always follow these rules strictly:

## Lightning Data Service (LDS) Rules — CRITICAL
- ALWAYS prefer LDS wire adapters over Apex for reading record data:
  * Use getRecord instead of Apex for single record fetching
  * Use getRelatedListRecords instead of Apex SOQL for related records
  * Use getListUi instead of Apex for list views
  * Use getPicklistValues instead of Apex for picklist options
  * Use getObjectInfo instead of Apex for object metadata
  * Use lightning-record-form variants instead of custom Apex forms
- Only use Apex when LDS genuinely cannot do it:
  * Complex multi-object queries or SOSL
  * Business logic, calculations, decisions
  * DML with validation or triggers
  * Aggregations or SOQL features not in LDS

## LWC Best Practices — ALWAYS FOLLOW
- Handle error property on ALL wire adapters — never ignore it
- Always use error.body?.message with optional chaining — never error.body.message
- Show loading spinner while data loads — hide content while loading
- When showing error, hide the main content — never show both simultaneously
- Use combined isLoading getter when multiple wire adapters present
- Clean up subscriptions (empApi, LMS, setInterval) in disconnectedCallback
- Never hardcode Salesforce IDs, usernames, org values, URLs, or record type IDs
- Use SLDS classes for all styling (slds-*, lightning-*)
- Handle null/undefined from wire adapters using optional chaining (?.)
- Add JSDoc comments on ALL public @api properties including recordId

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OFFICIAL SALESFORCE LWC DATA GUIDELINES (from developer.salesforce.com)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Decision Tree — How to fetch data (official Salesforce guidance)
Use in this order of preference:
1. lightning-record-form / lightning-record-edit-form / lightning-record-view-form
   → Use when you need a form-based UI to view, create, or edit a single record
   → Handles validation, FLS, layout automatically
   → Specify fields instead of layout for better performance

2. GraphQL wire adapter (lightning/graphql)
   → Use when fetching multiple objects in one query
   → Use when you need filtering, sorting, pagination
   → More performant than multiple LDS wire adapters for complex queries

3. LDS wire adapters (lightning/uiRecordApi, lightning/uiRelatedListApi etc.)
   → getRecord: fetch a single record's fields
   → getRelatedListRecords: fetch related list records
   → getListUi: fetch list view records
   → getPicklistValues: fetch picklist options
   → getObjectInfo: fetch object metadata

4. Apex — ONLY when LDS and GraphQL cannot handle it:
   → Objects not supported by User Interface API (Task, Event for complex queries)
   → Complex multi-object transactions (create Account + Opportunity atomically)
   → Business logic, calculations, aggregations
   → Custom search across multiple objects (SOSL)

## Key LDS Facts (official)
- LDS does NOT incur API usage calls
- LDS automatically caches and invalidates data when records change
- LDS auto-refreshes ALL components using same wire adapter when data changes
- Custom metadata types are NOT supported by LDS
- refreshApex() only for Apex wire adapters — use notifyRecordUpdateAvailable() for LDS
- Data from Apex is NOT managed by LDS — must refresh manually

## getRecord — Official Pattern
```javascript
import { LightningElement, api, wire } from 'lwc';
import { getRecord, getFieldValue } from 'lightning/uiRecordApi';
import NAME_FIELD from '@salesforce/schema/Contact.Name';
import EMAIL_FIELD from '@salesforce/schema/Contact.Email';
import PHONE_FIELD from '@salesforce/schema/Contact.Phone';

const FIELDS = [NAME_FIELD, EMAIL_FIELD, PHONE_FIELD];

export default class MyComponent extends LightningElement {
    @api recordId;

    @wire(getRecord, { recordId: '$recordId', fields: FIELDS })
    contact;

    // Use getFieldValue for safe access
    get name() { return getFieldValue(this.contact.data, NAME_FIELD); }
    get email() { return getFieldValue(this.contact.data, EMAIL_FIELD); }
    get isLoading() { return !this.contact.data && !this.contact.error; }
    get error() { return this.contact.error; }
}
```

## lightning-record-form — Official Pattern
```html
<!-- View and edit mode with automatic switching -->
<lightning-record-form
    record-id={recordId}
    object-api-name="Contact"
    fields={fields}
    mode="view">
</lightning-record-form>
```
```javascript
// Specify fields for better performance (not layout)
fields = ['Contact.Name', 'Contact.Email', 'Contact.Phone', 'Contact.Title'];
```

## lightning-record-edit-form — Official Pattern
```html
<lightning-record-edit-form
    record-id={recordId}
    object-api-name="Contact"
    onsubmit={handleSubmit}
    onsuccess={handleSuccess}
    onerror={handleError}>
    <lightning-messages></lightning-messages>
    <lightning-input-field field-name="Name"></lightning-input-field>
    <lightning-input-field field-name="Email"></lightning-input-field>
    <lightning-button type="submit" label="Save"></lightning-button>
</lightning-record-edit-form>
```
```javascript
handleSubmit(event) {
    event.preventDefault();
    this.isLoading = true;
    event.target.submit();  // submit after custom logic
}
handleSuccess(event) {
    this.isLoading = false;
    this.dispatchEvent(new ShowToastEvent({ title: 'Success', variant: 'success' }));
}
handleError(event) {
    this.isLoading = false;
    // error details in event.detail
}
```

## Reactivity Rules (official)
- Objects passed to a component are READ-ONLY — never mutate directly
- To update: make a shallow copy first
  WRONG: this.record.Name = 'new'
  RIGHT: this.record = { ...this.record, Name: 'new' }
- Arrays: WRONG: this.items.push(x)  RIGHT: this.items = [...this.items, x]
- Data flows ONE direction: parent → child
- To trigger mutation: child fires event → parent handles → parent updates

## Wire Adapter Refresh (official)
- For Apex wire: use refreshApex(this.wiredResult)
- For LDS wire: use notifyRecordUpdateAvailable([{ recordId }])
- refreshApex on non-Apex wire adapters is DEPRECATED

## Template Syntax (official)
- ALWAYS: lwc:if, lwc:elseif, lwc:else
- NEVER: if:true, if:false (deprecated)
- For lists: for:each={items} for:item="item" — always set key={item.id}
- Alternatively: lwc:for={items} lwc:for-item="item" (newer syntax)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF OFFICIAL DOCS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Template Syntax — CRITICAL
- ALWAYS use lwc:if and lwc:else — NEVER use deprecated if:true or if:false
- NEVER put data-* attributes on <template> tags — only on real HTML elements
- NEVER use a method call as a template conditional — use a getter property instead
- Disabled attribute must use JavaScript expression: disabled={!isValid} not disabled={not isValid}

## Reactivity Rules — CRITICAL  
- NEVER mutate arrays directly (push, pop, splice) — always use spread operator:
  WRONG: this.items.push(newItem)
  RIGHT: this.items = [...this.items, newItem]
- NEVER mutate object properties directly for reactive updates — assign new object:
  WRONG: this.record.Name = 'new'
  RIGHT: this.record = { ...this.record, Name: 'new' }
- @track is NOT needed on objects/arrays since Spring '20 — never add it unnecessarily

## Import Correctness — CRITICAL
- refreshApex imports from 'lightning/uiRecordApi' NOT from '@salesforce/apex'
- graphql and gql import from 'lightning/uiGraphQLApi'
- getRecord, getRelatedListRecords, getListUi import from 'lightning/uiRecordApi' or 'lightning/uiRelatedListApi'
- NavigationMixin imports from 'lightning/navigation'
- ShowToastEvent imports from 'lightning/platformShowToastEvent'
- Always double-check import paths are correct before including them

## Data Mapping — CRITICAL
- getListUi data structure: data.records.records (array of records)
- getRecord data structure: use getSObjectValue(data, fieldApiName)
- getRelatedListRecords: data.records.records (array)
- graphQL: data.uiapi.query.ObjectName.edges.map(e => e.node)
- Always check the correct data structure before mapping

## Format — EXACTLY this structure, no extra text:
=== INSTRUCTION ===
<one clear sentence describing what to build>

=== HTML ===
<complete .html file>

=== JS ===
<complete .js file>

=== CSS ===
<complete .css file or the word NONE>"""

DOMAINS = [
    {"name": "Financial Services", "objects": "Loan_Application__c, Portfolio__c, KYC_Document__c, Financial_Account__c", "context": "bank or wealth management firm", "examples": "loan applications, portfolio dashboards, KYC verification, account statements"},
    {"name": "Healthcare", "objects": "Patient__c, Appointment__c, Care_Plan__c, Medical_Record__c", "context": "hospital or healthcare provider", "examples": "patient intake, appointment scheduling, care plans, medication tracking"},
    {"name": "Manufacturing", "objects": "Work_Order__c, Asset__c, Quality_Inspection__c, Production_Run__c", "context": "manufacturing plant", "examples": "work orders, asset tracking, quality inspections, production runs"},
    {"name": "Retail", "objects": "Product__c, Order__c, Loyalty_Points__c, Store__c", "context": "retail company or e-commerce platform", "examples": "product catalog, order management, loyalty points, store inventory"},
    {"name": "Telecommunications", "objects": "Service_Request__c, Usage_Summary__c, Billing_Account__c, Network_Asset__c", "context": "telecom company", "examples": "service requests, usage dashboards, billing management, network assets"},
    {"name": "Energy & Utilities", "objects": "Meter__c, Outage_Report__c, Field_Service_Job__c, Energy_Usage__c", "context": "energy or utility company", "examples": "meter readings, outage reporting, field service jobs, energy consumption"},
    {"name": "Professional Services", "objects": "Project__c, Timesheet__c, Resource__c, Milestone__c", "context": "consulting or professional services firm", "examples": "project tracking, timesheets, resource allocation, milestone management"},
    {"name": "Insurance", "objects": "Claim__c, Policy__c, Risk_Assessment__c, Coverage__c", "context": "insurance company", "examples": "claims filing, policy management, risk assessments, coverage details"},
]

CATEGORIES = [
    {
        "name": "LDS Wire Adapters",
        "generic_prompts": [
            "Build an LWC component using getRecord LDS wire to display a Contact's Name, Email, Phone, Title, Account Name with spinner and error panel — no Apex.",
            "Build an LWC component using getRelatedListRecords LDS wire to show related Opportunities on an Account in a lightning-datatable with Stage, Amount, Close Date — no Apex.",
            "Build an LWC component using getPicklistValues LDS wire to populate a combobox with Case Priority values and filter a datatable of Cases by selected priority.",
            "Build an LWC component using getObjectInfo LDS wire to display all field labels, data types, and required status for the Lead object dynamically.",
            "Build an LWC component using both getRecord and getRelatedListRecords simultaneously with a combined isLoading getter and combined error getter.",
            "Build an LWC component using getListUi LDS wire to display a paginated list of Accounts with Next/Previous buttons — no Apex.",
            "Build an LWC component using getRecord with static schema imports and getSObjectValue to display Opportunity fields safely with null checking.",
            "Build an LWC component using getCurrentUserInfo LDS wire to display the current user's name, profile, and role in a card with initials as avatar.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} that uses LDS wire adapters (getRecord, getRelatedListRecords, or getListUi — no Apex) to display {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Focus on the list view with filtering and sorting.",
            "Focus on the detail view with related records panel.",
            "Include a combined isLoading getter waiting for multiple wire adapters.",
            "Include error handling with a custom error panel component.",
        ],
    },
    {
        "name": "Lightning Record Form",
        "generic_prompts": [
            "Build an LWC using lightning-record-view-form with lightning-output-field in two-column layout for a Contact with an Edit button switching to lightning-record-edit-form.",
            "Build an LWC using lightning-record-edit-form for creating a Case with custom onsubmit spinner and onsuccess/onerror toast notifications.",
            "Build an LWC using lightning-record-form in edit mode for updating Account billing address with a Cancel button using the reset() method.",
            "Build an LWC using lightning-record-edit-form reading URL state via CurrentPageReference to pre-populate fields when creating a new Opportunity.",
            "Build an LWC toggling between lightning-record-view-form and lightning-record-edit-form with Edit/Cancel buttons and auto-switch back to view on save success.",
            "Build an LWC using lightning-record-edit-form with a custom onsubmit handler that validates fields before submission and shows inline field errors.",
            "Build an LWC using lightning-record-view-form with conditional lightning-output-field visibility based on record field values.",
            "Build an LWC using lightning-record-edit-form for a clone operation — reads source record via getRecord LDS wire and pre-populates a new record form.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} using lightning-record-edit-form or lightning-record-view-form to manage {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Focus on the create/new record form with validation and success toast.",
            "Focus on the edit form with cancel, reset, and dirty-state detection.",
            "Focus on the view form with conditional field display based on record status.",
            "Include both view and edit modes with a toggle button and auto-refresh after save.",
        ],
    },
    {
        "name": "Navigation",
        "generic_prompts": [
            "Build an LWC using NavigationMixin with buttons to navigate to a record view, record edit, object home, and related list for Accounts.",
            "Build an LWC using NavigationMixin to open a new Opportunity creation form with pre-populated AccountId and StageName as defaultFieldValues.",
            "Build an LWC using CurrentPageReference to read URL state params and NavigationMixin to update them when filters change.",
            "Build an LWC using NavigationMixin to navigate to a named community page, open an external URL in a new tab, and preview a file.",
            "Build an LWC using NavigationMixin with standard__objectPage to navigate to list views with different filterApiName values from a dropdown.",
            "Build an LWC using NavigationMixin to navigate to a standard new record page with prepopulated lookup fields and custom field values.",
            "Build an LWC using CurrentPageReference to detect whether it is on a record page, object home, or app page and adjust its display accordingly.",
            "Build an LWC breadcrumb navigation component using CurrentPageReference that shows the navigation history and allows going back using NavigationMixin.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} using NavigationMixin to navigate between related {domain_objects} records for {domain_example} workflows. {variation}",
        "variations": [
            "Include buttons for view, edit, create new, and navigate to related list.",
            "Include navigation to a new record form with pre-populated lookup and status fields.",
            "Include breadcrumb navigation showing the current record hierarchy.",
            "Include deep-link navigation that preserves filter state in URL parameters.",
        ],
    },
    {
        "name": "Apex Integration",
        "generic_prompts": [
            "Build an LWC with a debounced search input (300ms) calling Apex imperatively to search Accounts by name, showing results in a datatable with spinner.",
            "Build an LWC calling Apex to get dashboard metrics — open Opportunities count, closed-won revenue, overdue Tasks — shown in three summary tiles.",
            "Build an LWC calling Apex for bulk Stage update on selected Opportunities in a datatable, with confirmation modal, spinner, and toasts.",
            "Build an LWC calling Apex to run SOSL search across Accounts, Contacts, and Opportunities, displaying results in three lightning-tabs.",
            "Build an LWC calling Apex to send a custom email to selected Contacts with rich-text body, subject, CC, and attachment support.",
            "Build an LWC calling Apex to clone a record including child records, with a step-by-step progress indicator for each phase.",
            "Build an LWC calling Apex to generate a PDF report for a record and display the download link, with spinner during generation.",
            "Build an LWC calling Apex to check duplicate records before saving, showing matched records in a warning panel with options to save anyway or cancel.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} calling Apex for complex business logic on {domain_objects} records for {domain_example} where LDS cannot handle it. {variation}",
        "variations": [
            "Focus on a complex search or filter operation returning paginated results.",
            "Focus on a bulk update or mass action with confirmation and progress tracking.",
            "Focus on a calculation or aggregation that requires server-side business logic.",
            "Focus on an integration action like sending notifications or generating documents.",
        ],
    },
    {
        "name": "Lightning Datatable",
        "generic_prompts": [
            "Build an LWC with a lightning-datatable showing Opportunities with inline editing for Stage and Amount, Save button calling Apex with row-level error handling.",
            "Build an LWC with a lightning-datatable showing Contacts with custom row actions — View, Edit, Delete — with confirmation modal before deletion.",
            "Build an LWC with a lightning-datatable showing Cases with sortable columns, client-side search filtering, and column resizing using getListUi LDS wire.",
            "Build an LWC with a lightning-datatable loading more Account records on scroll using onloadmore and Apex with OFFSET pagination.",
            "Build an LWC with a lightning-datatable showing Leads with bulk selection, mass-update status button, and custom badge column type.",
            "Build an LWC with a lightning-datatable with custom data type columns showing currency with formatting, date with relative time, and status with colored badges.",
            "Build an LWC with a lightning-datatable supporting column-level filtering with a filter row below the header, filtering data client-side.",
            "Build an LWC with a lightning-datatable showing a hierarchy — parent and expandable child rows — using tree-grid for Account and related Contacts.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} with a lightning-datatable displaying {domain_objects} records for {domain_example}. {variation}",
        "variations": [
            "Include sortable columns, row actions (view, edit, delete), and bulk selection with mass-update.",
            "Include inline editing for key fields, Save/Cancel buttons, and row-level error display.",
            "Include infinite scroll pagination, client-side search, and column resizing.",
            "Include custom data type columns for status badges, currency formatting, and date display.",
        ],
    },
    {
        "name": "Events & Communication",
        "generic_prompts": [
            "Build a parent-child LWC pair where parent uses getListUi wire for Accounts, passes each to a child card, and child fires 'accountselected' event parent handles.",
            "Build an LWC LMS publisher that publishes RecordSelected message on datatable row click, and a subscriber that uses getRecord LDS wire to display the selected record.",
            "Build an LWC using LMS with APPLICATION_SCOPE to broadcast filter changes from a filter panel to a results list on the same flexipage.",
            "Build a three-component LWC system — search bar, results list, detail panel — communicating via custom events to a coordinator parent.",
            "Build an LWC using CustomEvent with bubbles:true and composed:true to communicate across shadow DOM boundaries.",
            "Build an LWC using LMS to synchronize two datatable components on the same page — selecting a row in one highlights the related record in the other.",
            "Build a pub/sub pattern LWC where multiple subscriber components on a page all react to a single publisher's filter selection change.",
            "Build an LWC component pair using CustomEvent for child-to-parent communication and public @api methods for parent-to-child communication.",
        ],
        "domain_prompt_template": "Build a parent-child LWC pair for a {domain_name} {context} communicating via LMS or custom events to manage {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Parent shows a list, child shows detail — connected via custom event on row selection.",
            "Publisher component filters data, subscriber components react — using LMS APPLICATION_SCOPE.",
            "Three-component coordinator pattern: filter panel, results list, and action panel.",
            "Sibling communication via LMS where selecting in one component highlights in another.",
        ],
    },
    {
        "name": "Modals & Overlays",
        "generic_prompts": [
            "Build an LWC pair where a button opens a lightning-modal containing lightning-record-edit-form for creating a Contact, fires event on success.",
            "Build an LWC with a confirmation dialog before deleting a record, showing record name, warning icon, and Cancel/Delete buttons using lwc:if.",
            "Build an LWC using the lightning/modal base class, passing data via public properties, receiving a result event back on save.",
            "Build an LWC with a slide-out panel using CSS transitions showing record details on datatable row click with close button and backdrop.",
            "Build an LWC multi-step modal wizard — step 1 basic info, step 2 address, step 3 summary — with Back/Next/Submit and step validation.",
            "Build an LWC with a popover that appears on icon hover showing related record quick view using getRecord LDS wire.",
            "Build an LWC with a full-screen overlay for a complex form, with a minimize button that collapses it to a floating bar.",
            "Build an LWC with a bulk action modal that appears after selecting rows in a datatable, showing a form applied to all selected records.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} with a modal for creating or editing {domain_objects} records for {domain_example}. {variation}",
        "variations": [
            "Include form validation, loading spinner during save, and success/error toast after close.",
            "Include a confirmation dialog before destructive actions with record name display.",
            "Include a multi-step wizard with step validation and progress indicator.",
            "Include a slide-out detail panel that opens on row selection without blocking the main view.",
        ],
    },
    {
        "name": "Forms & Input",
        "generic_prompts": [
            "Build an LWC multi-step form — Personal Info, Address, Preferences — with lightning-input, step validation, progress bar, and Apex submission.",
            "Build an LWC with dynamic form fields where selecting a Case record type shows different fields, using getPicklistValues LDS wire for picklists.",
            "Build an LWC with lightning-file-upload restricted to PDF and images, upload progress, image thumbnails, and Apex to attach to a record.",
            "Build an LWC with lightning-input-rich-text for notes, character count, auto-save every 30 seconds using setInterval, and Save button calling Apex.",
            "Build an LWC with a dynamic field builder where users add/remove input fields at runtime, validate all on submit, call Apex with field values as JSON.",
            "Build an LWC form with dependent picklists — Country drives State drives City — all using getPicklistValues LDS wire with controller field.",
            "Build an LWC form with real-time field validation showing inline errors as the user types, using custom validity with setCustomValidity.",
            "Build an LWC form with a signature pad using HTML5 canvas where users draw their signature, captured as base64 and saved via Apex.",
        ],
        "domain_prompt_template": "Build an LWC multi-step form for a {domain_name} {context} collecting information for {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Include three steps with validation at each step and a progress bar.",
            "Include dynamic fields that show/hide based on previous selections using getPicklistValues LDS wire.",
            "Include file upload with preview and attachment to the record via Apex.",
            "Include dependent picklists, real-time validation, and auto-save draft functionality.",
        ],
    },
    {
        "name": "Platform Events & Streaming",
        "generic_prompts": [
            "Build an LWC subscribing to a Platform Event via empApi, showing events in a real-time feed with timestamps, with error handling and unsubscribe in disconnectedCallback.",
            "Build an LWC subscribing to Change Data Capture for Opportunity via empApi, highlighting changed fields, showing toast when record is deleted.",
            "Build an LWC publishing a Platform Event via Apex on button click, showing spinner during publish and result in a feed.",
            "Build an LWC subscribing to multiple Platform Event channels via empApi, filtering by type field, routing to different display sections.",
            "Build an LWC using CDC for Account records, maintaining a local change log showing field-level diffs with before/after values and timestamps.",
            "Build an LWC that subscribes to a Platform Event and uses the event payload to refresh a getRecord LDS wire adapter using the refresh function.",
            "Build an LWC with a real-time notification bell using empApi that shows a badge count and dropdown of incoming Platform Events.",
            "Build an LWC using empApi to subscribe to a streaming topic and display live data updates in a chart that refreshes on each event.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} using lightning/empApi to subscribe to Platform Events or CDC events related to {domain_objects} for {domain_example}. {variation}",
        "variations": [
            "Display incoming events in a real-time scrollable feed with timestamps.",
            "Refresh related wire adapters when events arrive to keep data current.",
            "Show a notification badge count with a dropdown list of recent events.",
            "Display field-level change diffs when CDC events arrive for record updates.",
        ],
    },
    {
        "name": "Utility & UX Patterns",
        "generic_prompts": [
            "Build an LWC vertical activity timeline for a record showing Tasks and Events via Apex, with icons per type, relative timestamps, and expand/collapse.",
            "Build an LWC kanban board showing Opportunities by Stage via getListUi LDS wire, with drag-and-drop calling Apex to update Stage.",
            "Build an LWC using platformResourceLoader to load Chart.js from Static Resource and render a bar chart of monthly Opportunity revenue via Apex.",
            "Build an LWC displaying Account billing addresses as pins on a lightning-map via getListUi LDS wire, with click-to-navigate to the record.",
            "Build a reusable LWC toast service accepting variant, title, message via public properties, with auto-dismiss and queue support.",
            "Build an LWC with a virtual scrolling list that renders only visible rows, loading more data via Apex as the user scrolls.",
            "Build an LWC with a global search bar that searches Accounts, Contacts, and Opportunities via Apex SOSL, showing categorized results with icons.",
            "Build an LWC skeleton loading component that shows animated placeholder cards while wire adapter data is loading, replacing them with real content on load.",
        ],
        "domain_prompt_template": "Build an LWC utility component for a {domain_name} {context} visualizing {domain_example} data from {domain_objects} records. {variation}",
        "variations": [
            "Use a timeline layout with icons, timestamps, and expand/collapse for each item.",
            "Use a kanban board with drag-and-drop between status columns.",
            "Use a chart (bar, line, or pie) loaded via platformResourceLoader from a Static Resource.",
            "Use a map with pins for location-based records and click-to-navigate to record pages.",
        ],
    },
    {
        "name": "App Builder & Record Pages",
        "generic_prompts": [
            "Build an LWC for a Record Page reading recordId and objectApiName from page context, using getRecord LDS wire, showing different layouts per object.",
            "Build an LWC for App Builder with @api design attributes for title, icon, object API name, record count, and filter field — configurable without code.",
            "Build an LWC implementing lightning__RecordAction as a quick action, reading host record via getRecord LDS wire, opening pre-populated edit form in modal.",
            "Build an LWC using CurrentPageReference to detect record page vs object home vs app page and adjust display and data fetching.",
            "Build an LWC implementing lightning__FlowScreen target to be used inside a Flow, with @api input/output properties and validate() method.",
            "Build an LWC for App Builder that supports both desktop and mobile layouts using formFactor design attribute and conditional SLDS grid classes.",
            "Build an LWC implementing lightning__UtilityBar target with a badge count that updates via empApi Platform Events.",
            "Build an LWC with targetConfigs for multiple page types — record page, home page, and app page — with different design attributes for each.",
        ],
        "domain_prompt_template": "Build an LWC component for App Builder used by a {domain_name} {context} displaying {domain_example} from {domain_objects} on a record page. {variation}",
        "variations": [
            "Include configurable design attributes for field selection and display density.",
            "Include support for multiple page targets with different layouts per target type.",
            "Include mobile-responsive layout using formFactor and SLDS responsive grid.",
            "Include a quick action implementation with pre-populated form from the host record.",
        ],
    },
    {
        "name": "Community & Experience Cloud",
        "generic_prompts": [
            "Build an LWC for Experience Cloud checking isGuestUser to show login prompt for guests and personalized content using getCurrentUserInfo for authenticated users.",
            "Build an LWC community self-service portal where authenticated users submit a Case via lightning-record-edit-form and view open Cases via getListUi LDS wire.",
            "Build an LWC community knowledge base using Apex to search Knowledge Articles by keyword, with title, summary, category results and view tracking.",
            "Build an LWC community profile page using getRecord LDS wire for the current user's Contact with Edit button and lightning-record-edit-form.",
            "Build an LWC community dashboard showing the authenticated user's open Cases, upcoming Events, and recent Account activity using multiple LDS wire adapters.",
            "Build an LWC community registration form that creates a Contact and User record via Apex, with email verification step before final submission.",
            "Build an LWC community component that shows personalized product recommendations using Apex based on the authenticated user's purchase history.",
            "Build an LWC community header component showing branding, navigation links, a search bar, and cart icon, adapting for guest vs authenticated users.",
        ],
        "domain_prompt_template": "Build an LWC component for an Experience Cloud community portal for a {domain_name} {context} allowing authenticated users to manage {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Include guest user detection with login prompt and personalized authenticated view.",
            "Include a self-service list view and create form with community context.",
            "Include a community profile section and record detail with edit capability.",
            "Include community-specific navigation and branding adaptation for guest vs authenticated.",
        ],
    },
    {
        "name": "Flow & Screen Flow",
        "generic_prompts": [
            "Build an LWC implementing lightning__FlowScreen with @api input/output properties, custom validate() method returning error messages, and SLDS form layout.",
            "Build an LWC Flow screen component with a multi-field input form that receives default values from Flow variables and passes collected data back to Flow.",
            "Build an LWC Flow screen component that displays a datatable of records passed from Flow as a JSON string, allows row selection, and returns selected IDs.",
            "Build an LWC Flow screen component with a map showing locations passed from Flow as a JSON array, allowing the user to select a location and return it.",
            "Build an LWC Flow screen component that renders a rich text preview of a document template with dynamic merge fields replaced by Flow input variables.",
            "Build an LWC Flow screen component for a signature capture using canvas, returning the signature as a base64 string Flow output variable.",
            "Build an LWC Flow action component implementing lightning__FlowAction that calls Apex and returns structured results to the Flow.",
            "Build an LWC Flow screen component with a file upload that stores the ContentDocumentId as a Flow output variable for use in subsequent Flow elements.",
        ],
        "domain_prompt_template": "Build an LWC Flow screen component for a {domain_name} {context} that collects or displays {domain_example} information from {domain_objects} as part of a guided Flow. {variation}",
        "variations": [
            "Include @api input variables pre-populated from Flow and @api output variables returned to Flow.",
            "Include a custom validate() method that prevents Flow from advancing if required fields are missing.",
            "Include a datatable of records passed from Flow allowing selection and returning selected IDs.",
            "Include a summary/preview step showing collected data before final Flow submission.",
        ],
    },
    {
        "name": "Offline & Mobile",
        "generic_prompts": [
            "Build an LWC using lightning/mobileCapabilities to detect if the component is running on mobile and adapt the UI layout using formFactor.",
            "Build an LWC using the barcode scanner from lightning/mobileCapabilities to scan a barcode and look up a Product record by barcode value via Apex.",
            "Build an LWC using the camera from lightning/mobileCapabilities to capture a photo and upload it as a ContentVersion attached to a record via Apex.",
            "Build an LWC using the geolocation from lightning/mobileCapabilities to get the current GPS coordinates and update a record's location fields via Apex.",
            "Build an LWC mobile-optimized list component using SLDS responsive grid that shows a card layout on mobile and a datatable on desktop based on formFactor.",
            "Build an LWC using the NFC reader from lightning/mobileCapabilities to read an NFC tag and look up an Asset record by tag ID via Apex.",
            "Build an LWC offline-capable component that uses localStorage to cache record data and sync changes back to Salesforce when connectivity is restored.",
            "Build an LWC using lightning/mobileCapabilities biometrics to authenticate the user with Face ID or fingerprint before showing sensitive record data.",
        ],
        "domain_prompt_template": "Build a mobile-optimized LWC component for a {domain_name} {context} field worker managing {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Include barcode or NFC scanning to look up records in the field.",
            "Include camera capture to attach photos to records as ContentVersions.",
            "Include GPS geolocation to update location fields on records in the field.",
            "Include offline caching with localStorage and sync-on-reconnect pattern.",
        ],
    },
    {
        "name": "Performance Patterns",
        "generic_prompts": [
            "Build an LWC with a debounced search input that waits 300ms after the user stops typing before calling Apex, preventing excessive API calls.",
            "Build an LWC with lazy loading — shows only the first 10 records initially and loads more on scroll — using Apex with OFFSET-based pagination.",
            "Build an LWC with client-side memoization caching Apex results in a Map by key, avoiding repeated API calls for the same data in a session.",
            "Build an LWC with skeleton loading placeholders (animated gray bars) shown while wire data loads, replaced by real content on load.",
            "Build an LWC with virtual scrolling rendering only visible rows using IntersectionObserver, handling 10,000+ records without performance degradation.",
            "Build an LWC using wire adapter refresh strategically — only refreshing after DML instead of polling — with a manual Refresh button as fallback.",
            "Build an LWC with optimistic UI — immediately updating the local list on user action and rolling back with an error toast if the Apex call fails.",
            "Build an LWC with chunked DML — splitting a large array of records into batches of 200 and calling Apex sequentially, showing progress per batch.",
        ],
        "domain_prompt_template": "Build a performance-optimized LWC component for a {domain_name} {context} that efficiently handles large volumes of {domain_example} data from {domain_objects} records. {variation}",
        "variations": [
            "Use debouncing, lazy loading, and client-side caching to minimize Apex calls.",
            "Use skeleton loading, optimistic UI updates, and targeted wire refresh after DML.",
            "Use virtual scrolling or windowing to handle large lists without degradation.",
            "Use chunked batch processing with progress tracking for bulk operations.",
        ],
    },
    {
        "name": "Security Patterns",
        "generic_prompts": [
            "Build an LWC that checks CRUD and FLS permissions using Apex before displaying edit buttons, hiding actions the current user lacks permission for.",
            "Build an LWC that uses WITH SECURITY_ENFORCED in all Apex SOQL queries and handles the resulting SecurityException gracefully.",
            "Build an LWC that sanitizes user input before passing to Apex, preventing SOQL injection by validating against an allowlist of field API names.",
            "Build an LWC using Security.stripInaccessible() in Apex to remove fields the user cannot access before returning records to the component.",
            "Build an LWC that respects Sharing rules — using 'with sharing' in Apex — and shows a friendly message when the user has no accessible records.",
            "Build an LWC that uses CSRF protection by including a custom header in Apex callouts and validating it server-side.",
            "Build an LWC implementing field-level permission checks using getObjectInfo LDS wire to show or hide fields based on the current user's FLS.",
            "Build an LWC that safely handles sensitive data — masking SSN and credit card fields in the UI — with Apex controlling what is returned based on permission sets.",
        ],
        "domain_prompt_template": "Build a security-hardened LWC component for a {domain_name} {context} that safely handles sensitive {domain_example} data from {domain_objects} records. {variation}",
        "variations": [
            "Include CRUD/FLS checks before showing edit, delete, or create actions.",
            "Include field-level masking for sensitive data based on user permissions.",
            "Include input sanitization and SOQL injection prevention for search inputs.",
            "Include sharing rule enforcement with a friendly message for restricted records.",
        ],
    },
    {
        "name": "Testing (Jest)",
        "generic_prompts": [
            "Write LWC Jest tests for a component using @wire with getRecord, mocking the wire adapter, testing loading state, data display, and error state.",
            "Write LWC Jest tests for a component calling Apex imperatively, mocking the Apex method, testing success response rendering and error handling.",
            "Write LWC Jest tests for a parent-child component pair, testing that a child custom event causes the correct state change in the parent.",
            "Write LWC Jest tests for a lightning-record-edit-form component, simulating form submission, testing onsuccess and onerror handlers fire correctly.",
            "Write LWC Jest tests for a component using LMS, mocking the message channel, testing that publish and subscribe work correctly.",
            "Write LWC Jest tests for a component with NavigationMixin, mocking the navigation service, and asserting the correct page reference is generated.",
            "Write LWC Jest tests for a datatable component with inline editing, testing that draftValues are captured correctly and the Save button calls Apex.",
            "Write LWC Jest tests for a Flow screen component, testing the validate() method returns correct errors and @api properties are correctly set.",
        ],
        "domain_prompt_template": "Write LWC Jest unit tests for a {domain_name} {context} component that manages {domain_example} using {domain_objects} objects. {variation}",
        "variations": [
            "Test wire adapter loading, data display, and error states with wire mocks.",
            "Test imperative Apex calls with success and error scenario mocks.",
            "Test custom events, LMS publish/subscribe, and parent-child communication.",
            "Test form submission, validation, navigation, and permission-based UI rendering.",
        ],
    },
    {
        "name": "GraphQL Wire Adapter",
        "generic_prompts": [
            "Build an LWC using the @wire graphQL adapter to fetch a list of Accounts with Name, Phone, and BillingCity fields, with loading and error handling.",
            "Build an LWC using the @wire graphQL adapter with cursor-based pagination — Next/Previous buttons — to page through a large list of Contacts.",
            "Build an LWC using the @wire graphQL adapter with a dynamic filter variable that changes based on a combobox selection, re-fetching data reactively.",
            "Build an LWC using the @wire graphQL adapter to fetch an Account with its nested related Contacts in a single GraphQL query, displaying both in the component.",
            "Build an LWC using the @wire graphQL adapter with sorting — allowing the user to click column headers to sort by different fields ascending or descending.",
            "Build an LWC using the @wire graphQL adapter to fetch Opportunities with aggregate fields — sum of Amount and count — displayed as summary metrics.",
            "Build an LWC using the @wire graphQL adapter with a search variable that filters records by name as the user types, with debouncing.",
            "Build an LWC comparing a @wire graphQL implementation vs a getListUi LDS implementation for the same data, showing both side by side with a toggle.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} using the @wire graphQL adapter to fetch and display {domain_example} from {domain_objects} records. {variation}",
        "variations": [
            "Include cursor-based pagination with Next/Previous navigation.",
            "Include dynamic filtering with a reactive filter variable from a combobox.",
            "Include nested related records fetched in a single GraphQL query.",
            "Include column sorting with ascending/descending toggle.",
        ],
    },
    {
        "name": "Agentforce & Einstein",
        "generic_prompts": [
            "Build an LWC component that displays Einstein Next Best Action recommendations for a record using the recommendationStrategy wire adapter.",
            "Build an LWC component that shows Einstein Prediction field values for a Lead with a visual confidence score indicator.",
            "Build an LWC component that acts as an Agentforce custom action, accepting input from the agent and returning structured output via @api properties.",
            "Build an LWC component with an embedded Einstein Copilot chat interface using the lightning/copilot module.",
            "Build an LWC component that calls an Apex method invoking an Einstein prompt template and displays the generated text response with streaming.",
            "Build an LWC component showing Einstein Activity Capture summary — email count, meeting count — for a Contact using getRecord LDS wire.",
            "Build an LWC component that integrates with Einstein Document Reader, uploading a document and displaying extracted field values from it.",
            "Build an LWC component that shows Einstein Opportunity Scoring with a visual score meter and key factors driving the score.",
        ],
        "domain_prompt_template": "Build an LWC component for a {domain_name} {context} that uses Einstein AI or Agentforce capabilities to assist with {domain_example} decisions using {domain_objects} data. {variation}",
        "variations": [
            "Show AI-generated recommendations or predictions with confidence scores.",
            "Include a custom Agentforce action component with @api input and output properties.",
            "Include a prompt template invocation via Apex with streamed response display.",
            "Include Einstein scoring or classification displayed as a visual meter or badge.",
        ],
    },
]

def get_domains_for_category(category_index):
    """Rotate all 8 domains across categories — each category gets all 8 domains."""
    start = (category_index * 2) % len(DOMAINS)
    return [DOMAINS[(start + i) % len(DOMAINS)] for i in range(len(DOMAINS))]

def build_all_prompts():
    all_prompts = []
    for cat_idx, category in enumerate(CATEGORIES):
        for prompt in category["generic_prompts"]:
            all_prompts.append({
                "prompt": prompt,
                "category": category["name"],
                "domain": "Generic",
                "type": "generic"
            })
        domains = get_domains_for_category(cat_idx)
        for domain in domains:
            for variation in category["variations"]:
                prompt = category["domain_prompt_template"].format(
                    domain_name=domain["name"],
                    context=domain["context"],
                    domain_example=domain["examples"],
                    domain_objects=domain["objects"],
                    variation=variation
                )
                all_prompts.append({
                    "prompt": prompt,
                    "category": category["name"],
                    "domain": domain["name"],
                    "type": "domain_specific"
                })
    return all_prompts

def parse_response(raw):
    try:
        instruction = re.search(r'=== INSTRUCTION ===\s*(.*?)\s*=== HTML ===', raw, re.DOTALL)
        html        = re.search(r'=== HTML ===\s*(.*?)\s*=== JS ===', raw, re.DOTALL)
        js          = re.search(r'=== JS ===\s*(.*?)\s*=== CSS ===', raw, re.DOTALL)
        css         = re.search(r'=== CSS ===\s*(.*?)$', raw, re.DOTALL)
        if not all([instruction, html, js]):
            return None
        instruction_text = instruction.group(1).strip()
        html_text        = html.group(1).strip()
        js_text          = js.group(1).strip()
        css_text         = css.group(1).strip() if css else "NONE"
        if css_text.upper() == "NONE":
            css_text = ""
        for lang in ['html', 'javascript', 'js', 'css', '']:
            html_text = re.sub(rf'^```{lang}\s*', '', html_text, flags=re.MULTILINE).strip()
            html_text = re.sub(r'\s*```$', '', html_text).strip()
            js_text   = re.sub(rf'^```{lang}\s*', '', js_text,   flags=re.MULTILINE).strip()
            js_text   = re.sub(r'\s*```$', '', js_text).strip()
        name_match = re.search(r'export default class (\w+)', js_text)
        name       = name_match.group(1) if name_match else "MyComponent"
        file_name  = name[0].lower() + name[1:]
        combined   = f"<!-- {file_name}.html -->\n{html_text}\n\n// {file_name}.js\n{js_text}"
        if css_text:
            combined += f"\n\n/* {file_name}.css */\n{css_text}"
        return {"instruction": instruction_text, "input": "", "output": combined}
    except Exception:
        return None

def generate_component(item):
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": item["prompt"]}
                ],
                temperature=0.5,
                max_tokens=9500
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

def main():
    output_path     = Path("synthetic_lwc_expanded.jsonl")
    checkpoint_path = Path("synthetic_lwc_expanded_checkpoint.jsonl")
    all_prompts     = build_all_prompts()

    done_prompts = set()
    results      = []
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            for line in f:
                rec = json.loads(line)
                done_prompts.add(rec["prompt"])
                results.append(rec["example"])
        print(f"▶️  Resuming — {len(results)} already generated")

    remaining     = [p for p in all_prompts if p["prompt"] not in done_prompts]
    generic_total = sum(1 for p in all_prompts if p["type"] == "generic")
    domain_total  = sum(1 for p in all_prompts if p["type"] == "domain_specific")

    print(f"\n📋 Prompt breakdown:")
    print(f"   20 categories × 8 generic prompts        = {generic_total}")
    print(f"   20 categories × 8 domains × 4 variations = {domain_total}")
    print(f"   Total                                     = {len(all_prompts)}")
    print(f"   Remaining                                 = {len(remaining)}\n")

    with open(checkpoint_path, "a") as ckpt:
        for i, item in enumerate(remaining):
            tag   = f"[{item['domain']}]" if item["type"] == "domain_specific" else "[Generic]"
            label = f"{item['category']} {tag}"
            print(f"[{i+1}/{len(remaining)}] {label[:70]}", end=" ", flush=True)

            example = generate_component(item)
            if not example:
                print("⚠️  skipped")
                continue

            example["source"]   = f"synthetic_lwc_expanded/{item['category'].lower().replace(' ','_')}"
            example["type"]     = "lwc"
            example["category"] = item["category"]
            example["domain"]   = item["domain"]
            results.append(example)
            ckpt.write(json.dumps({"prompt": item["prompt"], "example": example}) + "\n")
            ckpt.flush()
            print(f"✅ ({len(example['output'].splitlines())} lines)")
            time.sleep(1)

    with open(output_path, "w") as f:
        for ex in results:
            f.write(json.dumps(ex) + "\n")

    generic_done = [r for r in results if r.get("domain") == "Generic"]
    domain_done  = [r for r in results if r.get("domain") != "Generic"]
    print(f"\n🎉 Done!")
    print(f"   synthetic_lwc_expanded.jsonl → {len(results)} total examples")
    print(f"   Generic   : {len(generic_done)}")
    print(f"   Domain    : {len(domain_done)}")
    print(f"\n   By category:")
    for cat in CATEGORIES:
        n = len([r for r in results if r.get("category") == cat["name"]])
        print(f"   {cat['name']:<40}: {n}")
    print(f"\n   By domain:")
    for domain in DOMAINS:
        n = len([r for r in results if r.get("domain") == domain["name"]])
        print(f"   {domain['name']:<25}: {n}")

if __name__ == "__main__":
    main()
