"""
LWC Master Dataset Generator — Single unified script for all 25 categories
=============================================================================
Generates the complete synthetic_lwc_final.jsonl from scratch.

Usage:
    export TOKENROUTER_API_KEY=sk-...
    python3 generate_lwc_master.py

Config:
    TARGET   = examples per category (default 40)
    WORKERS  = parallel API threads (default 8)
    OUTPUT   = output JSONL path
    CHECKPOINT = checkpoint path (resumes interrupted runs)

Architecture:
    25 categories × 40 examples = 1,000 target
    ├── 19 original categories: 8 generic prompts + 8 domains × 4 variations = 40 each
    └──  6 gap categories:      40 hand-crafted expert prompts each

Post-processing applied inline (no separate fix scripts needed):
    • Strip @track from primitive fields
    • Remove redundant isLoading class field when getter exists
    • Normalize CSS from markdown fences to raw
    • Remove duplicate HTML section headers
    • Skip Jest examples that have no describe/it/test blocks
"""

import os, json, re, time, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from openai import OpenAI

# ── Config ────────────────────────────────────────────────────────────────────
TARGET     = 40          # examples per category
WORKERS    = 8           # parallel API threads
MODEL      = "MiniMax-M3"
OUTPUT     = Path("synthetic_lwc_final.jsonl")
CHECKPOINT = Path("lwc_master_checkpoint.jsonl")

client = OpenAI(
    api_key=os.environ["TOKENROUTER_API_KEY"],
    base_url="https://api.tokenrouter.com/v1",
)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior Salesforce LWC developer with 10 years of experience.
When asked to build a Lightning Web Component, always follow these rules:

## Data Fetching Priority (official Salesforce guidance)
1. lightning-record-form / lightning-record-edit-form / lightning-record-view-form
2. GraphQL wire adapter (lightning/uiGraphQLApi) for multi-object queries
3. LDS wire adapters (getRecord, getRelatedListRecords, getListUi, getPicklistValues, getObjectInfo)
4. Apex — ONLY when LDS/GraphQL cannot handle it (complex DML, aggregations, integrations)

## LWC Rules — CRITICAL
- lwc:if / lwc:elseif / lwc:else — NEVER deprecated if:true / if:false
- Handle error on ALL wire adapters — use error.body?.message with optional chaining
- Show lightning-spinner while data loads; hide content while loading
- Clean up subscriptions (empApi, LMS, setInterval) in disconnectedCallback
- Never hardcode Salesforce IDs, record type IDs, or org URLs
- @track NOT needed on objects/arrays — NEVER add it to primitive fields
- NEVER mutate arrays/objects directly: use [...arr] and {...obj}
- refreshApex() for Apex wires; notifyRecordUpdateAvailable() for LDS wires
- NavigationMixin from 'lightning/navigation'
- ShowToastEvent from 'lightning/platformShowToastEvent'
- MessageContext, publish, subscribe from 'lightning/messageService'
- graphql, gql from 'lightning/uiGraphQLApi'

## CSS Rules — for styled components
- Always open CSS with :host { } containing CSS custom properties
- Use SLDS design tokens: var(--lwc-colorBrand, #0176d3), var(--lwc-borderRadiusMedium, 0.5rem)
- Never use inline style= in HTML — use CSS classes instead
- Use @keyframes for animations, CSS Grid/Flexbox for layout, @media for responsive
- Status colors = CSS classes (.status-success, .status-warning, .status-error), not inline styles

## Testing (Jest) — CRITICAL
- HTML section = the component template being tested (a realistic component HTML)
- JS section = the JEST TEST FILE with import, describe, it/test, expect blocks
- Always mock wires with registerApexTestWireAdapter or registerLdsTestWireAdapter
- Always clean up in afterEach with document.body.removeChild

## LWC Service Components
- Empty <template></template>, expose functionality via @api methods only

## Dynamic Components
- import Comp from 'c/comp'; this.dynamicCtor = Comp; <lwc:component lwc:is={dynamicCtor}>

## Lightning Message Service
- import MyChannel from '@salesforce/messageChannel/MyChannel__c'
- @wire(MessageContext) messageContext; unsubscribe in disconnectedCallback

## Response Format — FOLLOW EXACTLY:
=== INSTRUCTION ===
<one sentence>

=== HTML ===
<html>

=== JS ===
<js>

=== CSS ===
<css or NONE>"""

FORMAT_REMINDER = (
    "\n\nRespond using EXACTLY this format — no prose before or after:\n"
    "=== INSTRUCTION ===\n<one sentence>\n"
    "=== HTML ===\n<html>\n"
    "=== JS ===\n<js>\n"
    "=== CSS ===\n<css or NONE>"
)

# ── Domains ───────────────────────────────────────────────────────────────────
DOMAINS = [
    {"name": "Financial Services", "objects": "Loan_Application__c, Portfolio__c, KYC_Document__c, Financial_Account__c",  "context": "bank or wealth management firm",             "examples": "loan applications, portfolio dashboards, KYC verification, account statements"},
    {"name": "Healthcare",         "objects": "Patient__c, Appointment__c, Care_Plan__c, Medical_Record__c",               "context": "hospital or healthcare provider",             "examples": "patient intake, appointment scheduling, care plans, medication tracking"},
    {"name": "Manufacturing",      "objects": "Work_Order__c, Asset__c, Quality_Inspection__c, Production_Run__c",         "context": "manufacturing plant",                        "examples": "work orders, asset tracking, quality inspections, production runs"},
    {"name": "Retail",             "objects": "Product__c, Order__c, Loyalty_Points__c, Store__c",                         "context": "retail company or e-commerce platform",      "examples": "product catalog, order management, loyalty points, store inventory"},
    {"name": "Telecommunications", "objects": "Service_Request__c, Usage_Summary__c, Billing_Account__c, Network_Asset__c","context": "telecom company",                           "examples": "service requests, usage dashboards, billing management, network assets"},
    {"name": "Energy & Utilities", "objects": "Meter__c, Outage_Report__c, Field_Service_Job__c, Energy_Usage__c",         "context": "energy or utility company",                  "examples": "meter readings, outage reporting, field service jobs, energy consumption"},
    {"name": "Professional Services","objects":"Project__c, Timesheet__c, Resource__c, Milestone__c",                      "context": "consulting or professional services firm",   "examples": "project tracking, timesheets, resource allocation, milestone management"},
    {"name": "Insurance",          "objects": "Claim__c, Policy__c, Risk_Assessment__c, Coverage__c",                     "context": "insurance company",                          "examples": "claims filing, policy management, risk assessments, coverage details"},
]

# ── Template-based Categories (19 original) ───────────────────────────────────
TEMPLATE_CATEGORIES = [
    {
        "name": "LDS Wire Adapters",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC using getRecord LDS wire to display a Contact's Name, Email, Phone, Title, Account Name with spinner and error panel — no Apex.",
            "Build an LWC using getRelatedListRecords LDS wire to show related Opportunities on an Account in a lightning-datatable with Stage, Amount, Close Date.",
            "Build an LWC using getPicklistValues LDS wire to populate a combobox with Case Priority values and filter a datatable of Cases by selected priority.",
            "Build an LWC using getObjectInfo LDS wire to display all field labels, data types, and required status for the Lead object dynamically.",
            "Build an LWC using both getRecord and getRelatedListRecords simultaneously with a combined isLoading getter and combined error getter.",
            "Build an LWC using getListUi LDS wire to display a paginated list of Accounts with Next/Previous buttons — no Apex.",
            "Build an LWC using getRecord with static schema imports and getFieldValue to display Opportunity fields safely with null checking.",
            "Build an LWC using getRelatedListRecords to show related Contacts on an Account record page with inline editing and refreshApex after save.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using LDS wire adapters (getRecord, getRelatedListRecords, or getListUi — no Apex) to display {examples} using {objects}. {variation}",
        "variations": [
            "Focus on the list view with filtering by a combobox and sortable columns.",
            "Focus on the detail view with a related records panel using getRelatedListRecords.",
            "Include a combined isLoading getter waiting for multiple simultaneous wire adapters.",
            "Include error handling with an inline error panel showing error.body?.message.",
        ],
    },
    {
        "name": "Lightning Record Form",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC using lightning-record-view-form with lightning-output-field in two-column SLDS grid layout for Contact, with Edit button switching to lightning-record-edit-form.",
            "Build an LWC using lightning-record-edit-form for creating a Case with custom onsubmit spinner, onsuccess toast, and onerror toast.",
            "Build an LWC using lightning-record-form in edit mode for updating Account billing address with a Cancel button calling reset().",
            "Build an LWC using lightning-record-edit-form reading CurrentPageReference to pre-populate fields when creating a new Opportunity.",
            "Build an LWC toggling between lightning-record-view-form and lightning-record-edit-form with Edit/Cancel buttons and auto-switch back to view on success.",
            "Build an LWC using lightning-record-edit-form with a custom onsubmit handler that validates required fields before calling event.target.submit().",
            "Build an LWC using lightning-record-view-form with conditional lightning-output-field visibility based on record field values.",
            "Build an LWC using lightning-record-edit-form for a clone operation — reads source via getRecord and pre-populates a new record form.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using lightning-record-edit-form or lightning-record-view-form to manage {examples} using {objects}. {variation}",
        "variations": [
            "Focus on the create/new record form with onsuccess toast and NavigationMixin redirect.",
            "Focus on the edit form with Cancel, reset(), and dirty-state detection before cancel.",
            "Focus on the view form with conditional field display based on a status picklist value.",
            "Include both view and edit modes with toggle button and notifyRecordUpdateAvailable after save.",
        ],
    },
    {
        "name": "Navigation",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC using NavigationMixin with buttons to navigate to record view, record edit, object home, and related list for Accounts.",
            "Build an LWC using NavigationMixin to open a new Opportunity creation form with pre-populated AccountId and StageName as defaultFieldValues.",
            "Build an LWC using CurrentPageReference to read URL state params and NavigationMixin to update them when filters change.",
            "Build an LWC using NavigationMixin to navigate to a named community page, open an external URL in a new tab, and preview a ContentDocument file.",
            "Build an LWC using NavigationMixin with standard__objectPage to navigate to list views with different filterApiName values from a combobox.",
            "Build an LWC using NavigationMixin to navigate to a standard new record page with prepopulated lookup and custom field values.",
            "Build an LWC using CurrentPageReference to detect record page vs object home vs app page and adjust display accordingly.",
            "Build an LWC breadcrumb navigation component using CurrentPageReference showing record hierarchy and back navigation using NavigationMixin.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using NavigationMixin to navigate between related {objects} records for {examples} workflows. {variation}",
        "variations": [
            "Include buttons for view, edit, create new, and navigate to related list.",
            "Include navigation to a new record form with pre-populated lookup and status fields.",
            "Include breadcrumb navigation showing the current record hierarchy.",
            "Include deep-link navigation that preserves filter state in URL parameters via CurrentPageReference.",
        ],
    },
    {
        "name": "Apex Integration",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC with a debounced search input (300ms) calling Apex imperatively to search Accounts by name, showing results in a datatable with spinner.",
            "Build an LWC calling Apex to get dashboard metrics — open count, closed-won revenue, overdue count — shown in three KPI summary tiles.",
            "Build an LWC calling Apex for bulk Stage update on selected Opportunities in a datatable, with confirmation modal, spinner, and toasts.",
            "Build an LWC calling Apex to run SOSL search across Accounts, Contacts, and Opportunities, displaying results in three lightning-tabs.",
            "Build an LWC calling Apex to send a custom email to selected Contacts with subject, body, and CC field support.",
            "Build an LWC calling Apex to clone a record including child records, with a progress indicator for each phase.",
            "Build an LWC calling Apex to check duplicate records before saving, showing matched records in a warning panel with options to proceed or cancel.",
            "Build an LWC calling Apex to generate a PDF and display the download link, with spinner during generation and error handling.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} calling Apex for complex business logic on {objects} for {examples} where LDS cannot handle it. {variation}",
        "variations": [
            "Focus on a complex search operation returning paginated results with a datatable.",
            "Focus on a bulk update or mass action with a confirmation modal and progress tracking.",
            "Focus on a calculation or aggregation that requires server-side business logic.",
            "Focus on an integration action like sending notifications or generating documents.",
        ],
    },
    {
        "name": "Lightning Datatable",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC with lightning-datatable showing Opportunities with inline editing for Stage and Amount, Save button calling Apex with row-level error handling.",
            "Build an LWC with lightning-datatable showing Contacts with custom row actions — View, Edit, Delete — and confirmation modal before deletion.",
            "Build an LWC with lightning-datatable showing Cases with sortable columns, client-side search filtering, and column resizing using getListUi LDS wire.",
            "Build an LWC with lightning-datatable loading more Account records on scroll using onloadmore and Apex with OFFSET pagination.",
            "Build an LWC with lightning-datatable showing Leads with bulk selection, mass-update status button, and success/error toast.",
            "Build an LWC with lightning-datatable with custom data type columns showing currency formatting, relative date, and status with colored badges.",
            "Build an LWC with lightning-datatable supporting column-level filtering with a filter row, filtering data client-side.",
            "Build an LWC with lightning-datatable showing a hierarchy of parent accounts and expandable child contacts using tree-grid.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} with a lightning-datatable displaying {objects} records for {examples}. {variation}",
        "variations": [
            "Include sortable columns, row actions (view, edit, delete), and bulk selection with mass-update.",
            "Include inline editing for key fields, Save/Cancel buttons, and row-level error display.",
            "Include infinite scroll pagination, client-side search, and column resizing.",
            "Include custom data type columns for status badges, currency formatting, and date display.",
        ],
    },
    {
        "name": "Events & Communication",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build a parent-child LWC pair where parent uses getListUi wire for Accounts, passes each to a child card, and child fires 'accountselected' event the parent handles.",
            "Build an LWC LMS publisher that publishes RecordSelected on datatable row click, and a subscriber that uses getRecord LDS wire to display the selected record.",
            "Build an LWC using LMS with APPLICATION_SCOPE to broadcast filter changes from a filter panel to a results list on the same flexipage.",
            "Build a three-component LWC system — search bar, results list, detail panel — communicating via custom events through a coordinator parent.",
            "Build an LWC using CustomEvent with bubbles:true and composed:true to communicate across shadow DOM boundaries.",
            "Build an LWC using LMS to synchronize two datatable components — selecting a row in one highlights the related record in the other.",
            "Build a pub/sub pattern LWC where multiple subscriber components react to a single publisher filter selection change.",
            "Build an LWC component pair using CustomEvent for child-to-parent and public @api methods for parent-to-child communication.",
        ],
        "domain_template": "Build a parent-child LWC pair for a {domain_name} {context} communicating via LMS or custom events to manage {examples} using {objects}. {variation}",
        "variations": [
            "Parent shows a list, child shows detail — connected via custom event on row selection.",
            "Publisher component filters data, subscriber components react — using LMS APPLICATION_SCOPE.",
            "Three-component coordinator: filter panel, results list, and action panel.",
            "Sibling communication via LMS where selecting in one component highlights in another.",
        ],
    },
    {
        "name": "Modals & Overlays",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC pair where a button opens a lightning-modal containing lightning-record-edit-form for creating a Contact, fires event on success.",
            "Build an LWC with a confirmation dialog before deleting a record, showing record name, warning icon, and Cancel/Delete buttons using lwc:if.",
            "Build an LWC using the lightning/modal base class, passing data via public properties, receiving a result event back on save.",
            "Build an LWC with a slide-out panel using CSS transitions showing record details on datatable row click with close button and backdrop.",
            "Build an LWC multi-step modal wizard — step 1 basic info, step 2 address, step 3 summary — with Back/Next/Submit and step validation.",
            "Build an LWC with a popover that appears on icon hover showing related record quick view using getRecord LDS wire.",
            "Build an LWC with a bulk action modal that appears after selecting datatable rows, showing a form applied to all selected records.",
            "Build an LWC with a full-screen overlay for a complex form, with a minimize button that collapses it to a floating action bar.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} with a modal for creating or editing {objects} records for {examples}. {variation}",
        "variations": [
            "Include form validation, loading spinner during save, and success/error toast after close.",
            "Include a confirmation dialog before destructive actions with record name display.",
            "Include a multi-step wizard with step validation and progress indicator.",
            "Include a slide-out detail panel that opens on row selection without blocking the main view.",
        ],
    },
    {
        "name": "Forms & Input",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC multi-step form — Personal Info, Address, Preferences — with lightning-input, step validation, progress bar, and Apex submission.",
            "Build an LWC with dynamic form fields where selecting a record type shows different fields using getPicklistValues LDS wire for picklists.",
            "Build an LWC with lightning-file-upload restricted to PDF and images, file preview, and Apex to attach ContentVersion to a record.",
            "Build an LWC with lightning-input-rich-text for notes, character count, auto-save every 30 seconds using setInterval, and manual Save button.",
            "Build an LWC with dependent picklists — Country drives State drives City — all using getPicklistValues LDS wire with controller field.",
            "Build an LWC form with real-time field validation showing inline errors as the user types using setCustomValidity.",
            "Build an LWC with a dynamic field builder where users add/remove input fields at runtime, validate all on submit, call Apex with field values as JSON.",
            "Build an LWC form with a signature pad using HTML5 canvas where users draw their signature, captured as base64 and saved via Apex.",
        ],
        "domain_template": "Build an LWC multi-step form for a {domain_name} {context} collecting information for {examples} using {objects}. {variation}",
        "variations": [
            "Include three steps with per-step validation, progress bar, and Back/Next navigation.",
            "Include dynamic fields that show/hide based on previous selections using getPicklistValues.",
            "Include file upload with preview and attachment to the record via Apex.",
            "Include dependent picklists, real-time setCustomValidity, and auto-save draft.",
        ],
    },
    {
        "name": "Platform Events & Streaming",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC subscribing to a Platform Event via empApi, showing events in a real-time feed with timestamps, error handling, and unsubscribe in disconnectedCallback.",
            "Build an LWC subscribing to Change Data Capture for Opportunity via empApi, highlighting changed fields and showing a toast when a record is deleted.",
            "Build an LWC publishing a Platform Event via Apex on button click, showing spinner during publish and result in a scrollable feed.",
            "Build an LWC subscribing to multiple Platform Event channels, filtering by type field, routing events to different display sections.",
            "Build an LWC using CDC for Account records, maintaining a local change log showing field-level diffs with before/after values.",
            "Build an LWC that subscribes to a Platform Event and uses the payload to refresh a getRecord LDS wire adapter.",
            "Build an LWC with a real-time notification bell using empApi showing a badge count and dropdown of recent events.",
            "Build an LWC using empApi to subscribe to a CDC topic and display live field changes in a datatable row highlight animation.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using lightning/empApi to subscribe to Platform Events or CDC events related to {objects} for {examples}. {variation}",
        "variations": [
            "Display incoming events in a real-time scrollable feed with timestamps and type icons.",
            "Refresh related wire adapters when events arrive to keep data current.",
            "Show a notification badge count with a dropdown list of recent events.",
            "Display field-level change diffs when CDC events arrive for record updates.",
        ],
    },
    {
        "name": "Utility & UX Patterns",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC vertical activity timeline for a record showing Tasks and Events via Apex, with icons per type, relative timestamps, and expand/collapse.",
            "Build an LWC kanban board showing Opportunities by Stage via getListUi LDS wire, with drag-and-drop updating Stage via Apex.",
            "Build an LWC using platformResourceLoader to load Chart.js from Static Resource and render a bar chart of monthly revenue via Apex.",
            "Build an LWC displaying Account billing addresses as pins on a lightning-map via getListUi LDS wire, with click-to-navigate to the record.",
            "Build a reusable LWC toast service accepting variant, title, message via public @api properties, with auto-dismiss and queue support.",
            "Build an LWC with virtual scrolling rendering only visible rows using IntersectionObserver, loading more via Apex as the user scrolls.",
            "Build an LWC global search bar that searches Accounts, Contacts, and Opportunities via Apex SOSL, showing categorized results with icons.",
            "Build an LWC skeleton loading component showing animated placeholder cards while wire data loads, replacing with real content on load.",
        ],
        "domain_template": "Build an LWC utility component for a {domain_name} {context} visualizing {examples} data from {objects} records. {variation}",
        "variations": [
            "Use a timeline layout with icons, relative timestamps, and expand/collapse for each item.",
            "Use a kanban board with drag-and-drop between status columns.",
            "Use a chart (bar, line, or pie) loaded via platformResourceLoader from Static Resource.",
            "Use a map with location pins for records and click-to-navigate to record pages.",
        ],
    },
    {
        "name": "App Builder & Record Pages",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC for a Record Page reading recordId and objectApiName from page context, using getRecord LDS wire, showing different layouts per object type.",
            "Build an LWC for App Builder with @api design attributes for title, icon, object API name, record count, and filter field — configurable without code.",
            "Build an LWC implementing lightning__RecordAction as a quick action, reading host record via getRecord, opening pre-populated edit form in a modal.",
            "Build an LWC using CurrentPageReference to detect record page vs object home vs app page and adjust display and data fetching accordingly.",
            "Build an LWC implementing lightning__FlowScreen with @api input/output properties and validate() method for use inside a Flow.",
            "Build an LWC for App Builder supporting both desktop and mobile using formFactor design attribute and conditional SLDS responsive grid classes.",
            "Build an LWC implementing lightning__UtilityBar with a badge count that updates via empApi Platform Events.",
            "Build an LWC with targetConfigs for record page, home page, and app page — with different design attributes per target.",
        ],
        "domain_template": "Build an LWC for App Builder used by a {domain_name} {context} displaying {examples} from {objects} on a record or home page. {variation}",
        "variations": [
            "Include configurable design attributes for field selection and display density.",
            "Include support for multiple page targets with different layouts per target type.",
            "Include mobile-responsive layout using formFactor and SLDS responsive grid classes.",
            "Include a quick action implementation with pre-populated form from the host record.",
        ],
    },
    {
        "name": "Community & Experience Cloud",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC for Experience Cloud checking isGuestUser to show login prompt for guests and personalized content for authenticated users using getCurrentUserInfo.",
            "Build an LWC community self-service portal where authenticated users submit a Case via lightning-record-edit-form and view open Cases via getListUi.",
            "Build an LWC community knowledge base using Apex to search Knowledge Articles by keyword, with results showing title, summary, and category.",
            "Build an LWC community profile page using getRecord LDS wire for the current user's Contact with Edit button and lightning-record-edit-form.",
            "Build an LWC community dashboard showing the authenticated user's open Cases, upcoming Events, and recent activity using multiple wire adapters.",
            "Build an LWC community registration form that creates a Contact via Apex with email verification step before final submission.",
            "Build an LWC community component showing personalized product recommendations using Apex based on authenticated user's purchase history.",
            "Build an LWC community header with branding, navigation links, search bar, and adapting display for guest vs authenticated users.",
        ],
        "domain_template": "Build an LWC for an Experience Cloud portal for a {domain_name} {context} allowing authenticated users to manage {examples} using {objects}. {variation}",
        "variations": [
            "Include guest user detection with login prompt and personalized authenticated view.",
            "Include a self-service list view and create form with community context.",
            "Include a community profile section with record detail and edit capability.",
            "Include community-specific navigation adapting for guest vs authenticated users.",
        ],
    },
    {
        "name": "Flow & Screen Flow",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC implementing lightning__FlowScreen with @api input/output properties, custom validate() method returning error messages, and SLDS form layout.",
            "Build an LWC Flow screen component with a multi-field form receiving default values from Flow variables and passing collected data back.",
            "Build an LWC Flow screen component that displays a datatable of records passed from Flow as JSON, allows row selection, and returns selected IDs.",
            "Build an LWC Flow screen component with a map showing locations from Flow JSON array, allowing location selection and returning it.",
            "Build an LWC Flow screen component rendering a document preview with dynamic merge fields replaced by Flow input variables.",
            "Build an LWC Flow screen component for signature capture using canvas, returning base64 as a Flow output variable.",
            "Build an LWC Flow action implementing lightning__FlowAction that calls Apex and returns structured results to the Flow.",
            "Build an LWC Flow screen component with file upload that stores ContentDocumentId as a Flow output variable.",
        ],
        "domain_template": "Build an LWC Flow screen component for a {domain_name} {context} that collects or displays {examples} from {objects} as part of a guided Flow. {variation}",
        "variations": [
            "Include @api input variables pre-populated from Flow and @api output variables returned to Flow.",
            "Include a custom validate() method that prevents Flow from advancing if required fields are missing.",
            "Include a datatable of records from Flow allowing selection and returning selected IDs.",
            "Include a summary/preview step showing collected data before final Flow submission.",
        ],
    },
    {
        "name": "Offline & Mobile",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC using lightning/mobileCapabilities to detect mobile and adapt UI layout using formFactor.",
            "Build an LWC using the barcode scanner from lightning/mobileCapabilities to scan a barcode and look up a Product record via Apex.",
            "Build an LWC using the camera from lightning/mobileCapabilities to capture a photo and upload it as ContentVersion attached to a record via Apex.",
            "Build an LWC using geolocation from lightning/mobileCapabilities to get GPS coordinates and update a record's location fields via Apex.",
            "Build an LWC mobile-optimized list showing card layout on mobile and datatable on desktop based on formFactor.",
            "Build an LWC using NFC reader from lightning/mobileCapabilities to read an NFC tag and look up an Asset record by tag ID via Apex.",
            "Build an LWC offline-capable component using localStorage to cache record data and sync changes back when connectivity is restored.",
            "Build an LWC using lightning/mobileCapabilities biometrics to authenticate the user with Face ID before showing sensitive record data.",
        ],
        "domain_template": "Build a mobile-optimized LWC for a {domain_name} {context} field worker managing {examples} using {objects}. {variation}",
        "variations": [
            "Include barcode or NFC scanning to look up records in the field.",
            "Include camera capture to attach photos to records as ContentVersions.",
            "Include GPS geolocation to update location fields on records.",
            "Include offline caching with localStorage and sync-on-reconnect pattern.",
        ],
    },
    {
        "name": "Performance Patterns",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC with a debounced search input that waits 300ms after typing stops before calling Apex, preventing excessive API calls.",
            "Build an LWC with lazy loading — shows first 10 records initially and loads more on scroll — using Apex with OFFSET-based pagination.",
            "Build an LWC with client-side memoization caching Apex results in a Map by key, avoiding repeated calls for the same data in a session.",
            "Build an LWC with skeleton loading placeholders shown while wire data loads, replaced by real content on arrival.",
            "Build an LWC with virtual scrolling rendering only visible rows using IntersectionObserver, handling 10,000+ records.",
            "Build an LWC using wire adapter refresh strategically — only after DML — with a manual Refresh button as fallback and comment on why no polling.",
            "Build an LWC with optimistic UI — immediately updating the local list on button click and rolling back with an error toast if Apex fails.",
            "Build an LWC with chunked DML — splitting a large array into batches of 200 and calling Apex sequentially, showing progress per batch.",
        ],
        "domain_template": "Build a performance-optimized LWC for a {domain_name} {context} that efficiently handles large volumes of {examples} data from {objects}. {variation}",
        "variations": [
            "Use debouncing, lazy loading, and client-side caching to minimize Apex calls.",
            "Use skeleton loading, optimistic UI updates, and targeted wire refresh after DML.",
            "Use virtual scrolling to handle large lists without performance degradation.",
            "Use chunked batch processing with progress tracking for bulk operations.",
        ],
    },
    {
        "name": "Security Patterns",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC that checks CRUD and FLS permissions using Apex before displaying edit buttons, hiding actions the user lacks permission for.",
            "Build an LWC that uses WITH SECURITY_ENFORCED in Apex SOQL and handles SecurityException gracefully.",
            "Build an LWC that sanitizes user input before passing to Apex, validating against an allowlist of field API names to prevent SOQL injection.",
            "Build an LWC using Security.stripInaccessible() in Apex to remove inaccessible fields before returning records to the component.",
            "Build an LWC that uses 'with sharing' in Apex and shows a friendly no-access message when the user has no accessible records.",
            "Build an LWC implementing field-level permission checks using getObjectInfo LDS wire to show or hide fields based on the current user's FLS.",
            "Build an LWC that safely masks sensitive data — SSN, credit card — in the UI, with Apex controlling what is returned based on permission sets.",
            "Build an LWC that validates all @api inputs are non-empty strings and sanitizes them before using in Apex callouts.",
        ],
        "domain_template": "Build a security-hardened LWC for a {domain_name} {context} safely handling sensitive {examples} data from {objects}. {variation}",
        "variations": [
            "Include CRUD/FLS checks before showing edit, delete, or create actions.",
            "Include field-level masking for sensitive data based on user permission sets.",
            "Include input sanitization and SOQL injection prevention for search inputs.",
            "Include sharing rule enforcement with a friendly message for restricted records.",
        ],
    },
    {
        "name": "Testing (Jest)",
        "max_tokens": 7500,
        "generic_prompts": [
            "Write LWC Jest tests for a component using @wire with getRecord, mocking the wire adapter, testing loading state, data display, and error state.",
            "Write LWC Jest tests for a component calling Apex imperatively, mocking the Apex method, testing success response rendering and error handling.",
            "Write LWC Jest tests for a parent-child component pair, testing that a child custom event causes the correct state change in the parent.",
            "Write LWC Jest tests for a lightning-record-edit-form component, simulating form submission, testing onsuccess and onerror handlers.",
            "Write LWC Jest tests for a component using LMS, mocking the message channel, testing publish and subscribe work correctly.",
            "Write LWC Jest tests for a component with NavigationMixin, mocking the navigation service, and asserting the correct PageReference.",
            "Write LWC Jest tests for a datatable with inline editing, testing that draftValues are captured and the Save button calls Apex with the correct payload.",
            "Write LWC Jest tests for a Flow screen component, testing the validate() method returns correct errors and @api properties are set.",
        ],
        "domain_template": "Write LWC Jest unit tests for a {domain_name} {context} component that manages {examples} using {objects}. {variation}",
        "variations": [
            "Test wire adapter loading, data display, and error states with wire mocks.",
            "Test imperative Apex calls with success and error scenario mocks.",
            "Test custom events, LMS publish/subscribe, and parent-child communication.",
            "Test form submission, validation, navigation, and permission-based UI rendering.",
        ],
    },
    {
        "name": "GraphQL Wire Adapter",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC using @wire graphQL adapter to fetch Accounts with Name, Phone, BillingCity, with loading and error handling.",
            "Build an LWC using @wire graphQL adapter with cursor-based pagination — Next/Previous buttons — for a large Contacts list.",
            "Build an LWC using @wire graphQL adapter with a dynamic filter variable that changes based on a combobox, re-fetching reactively.",
            "Build an LWC using @wire graphQL adapter to fetch an Account with nested related Contacts in a single query, displaying both.",
            "Build an LWC using @wire graphQL adapter with column sort — clicking headers sorts by different fields ascending/descending.",
            "Build an LWC using @wire graphQL adapter to fetch Opportunities with aggregate sum of Amount displayed as a summary metric.",
            "Build an LWC using @wire graphQL adapter with a search variable filtering records as the user types, with 300ms debouncing.",
            "Build an LWC using @wire graphQL adapter comparing to getListUi LDS for the same data, shown side by side with a toggle.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using the @wire graphQL adapter to fetch and display {examples} from {objects}. {variation}",
        "variations": [
            "Include cursor-based pagination with Next/Previous navigation.",
            "Include dynamic filtering with a reactive filter variable from a combobox.",
            "Include nested related records fetched in a single GraphQL query.",
            "Include column sorting with ascending/descending toggle.",
        ],
    },
    {
        "name": "Agentforce & Einstein",
        "max_tokens": 7000,
        "generic_prompts": [
            "Build an LWC displaying Einstein Next Best Action recommendations for a record using the recommendationStrategy wire adapter.",
            "Build an LWC showing Einstein Prediction field values for a Lead with a visual confidence score indicator bar.",
            "Build an LWC acting as an Agentforce custom action, accepting input from the agent and returning structured output via @api properties.",
            "Build an LWC with an embedded Einstein Copilot chat interface using the lightning/copilot module.",
            "Build an LWC calling Apex to invoke an Einstein prompt template and displaying the generated text with a streaming animation.",
            "Build an LWC showing Einstein Activity Capture summary — email count, meeting count — for a Contact using getRecord LDS wire.",
            "Build an LWC integrating with Einstein Document Reader, uploading a document and displaying extracted field values.",
            "Build an LWC showing Einstein Opportunity Scoring with a visual score meter and key factors driving the score.",
        ],
        "domain_template": "Build an LWC for a {domain_name} {context} using Einstein AI or Agentforce capabilities to assist with {examples} decisions using {objects}. {variation}",
        "variations": [
            "Show AI-generated recommendations or predictions with confidence scores.",
            "Include a custom Agentforce action component with @api input and output properties.",
            "Include an Einstein prompt template invocation via Apex with streamed response display.",
            "Include Einstein scoring or classification displayed as a visual meter or badge.",
        ],
    },
]

# ── Expert-prompt Gap Categories (6) ──────────────────────────────────────────
GAP_CATEGORIES = [
    {
        "name": "Slots & Composition",
        "max_tokens": 7000,
        "prompts": [
            "Build an LWC card container with named slots header, body, footer using assignedElements() to detect empty header slot and show a default title instead.",
            "Build a three-level LWC composition — grandparent list passes selected record via @api to parent summary, which passes fields to a child badge component.",
            "Build an LWC tab panel with named slots (slot='tab-1' through slot='tab-3') where the shell controls which slot is visible based on active tab state.",
            "Build an LWC page layout shell with named slots for sidebar, main, and toolbar that collapses sidebar on mobile using CSS Grid and @media breakpoints.",
            "Build a composable LWC list card with a default slot for custom row content used by a parent to render heterogeneous record types in a single scrollable list.",
            "Build an LWC modal shell with named slots for header, body, and footer including fallback content shown when the consumer provides nothing.",
            "Build an LWC wizard shell with named slots per step (slot='step-1', slot='step-2', slot='step-3') controlling visibility and firing stepchange events.",
            "Build an LWC accordion where each panel is a child component using a named slot for content, with expand/collapse managed by the parent shell.",
            "Build an LWC data card with a default slot for actions and a named slot for the title — parent provides both from a different component.",
            "Build an LWC notification toast container with a default slot for custom message content, stacking multiple toasts with auto-dismiss.",
            "Build a Financial Services LWC portfolio card shell with named slots for header (fund name), body (metrics grid), and footer (action buttons).",
            "Build a Healthcare LWC patient summary shell with named slots for vitals, medications, and appointments panels filled by sibling components.",
            "Build a Manufacturing LWC work order card with default slot for custom checklist content and named slot for status badge.",
            "Build a Retail LWC product card shell with named slots for image, details, and price — rendered differently per product type by the parent.",
            "Build a Telecom LWC service dashboard shell with named slots for header KPIs, main chart, and sidebar alert feed.",
            "Build an Energy LWC field report card with named slots for meter data, readings table, and action buttons — parent provides domain-specific content.",
            "Build an Insurance LWC claim card shell with named slots for policy info, claim details, and decision buttons.",
            "Build a Professional Services LWC project status card with named slots for timeline, resources panel, and milestone tracker.",
            "Build an LWC table shell with named slots for the filter bar, column headers, and row actions — parent components fill each slot.",
            "Build an LWC with a conditional default slot that shows a skeleton placeholder when the parent has not slotted any content yet.",
            "Build an LWC split-panel layout with named slots for left and right panels, a draggable resize handle, and @api properties for initial widths.",
            "Build a Financial Services LWC loan application shell with named slots for applicant info, financial details, and document upload sections.",
            "Build a Healthcare LWC care plan shell with named slots for goals, interventions, and outcomes filled by specialized child components.",
            "Build a Retail LWC order summary shell with named slots for item list, pricing breakdown, and shipping info.",
            "Build an LWC with a named slot for empty-state content — parent provides custom zero-data illustration and message when list is empty.",
            "Build an LWC with a default slot for main content and a named slot for a persistent sticky footer — parent controls both from outside.",
            "Build a Manufacturing LWC inspection report shell with named slots for checklist items, photo evidence, and sign-off section.",
            "Build a Telecom LWC billing statement shell with named slots for usage breakdown, charges table, and payment actions.",
            "Build an Energy LWC outage report shell with named slots for incident details, affected areas map, and ETA panel.",
            "Build an Insurance LWC policy comparison shell with named slots for each policy column — parent renders up to four policy options side by side.",
            "Build a Professional Services LWC timesheet shell with named slots for date header, hours grid, and totals footer.",
            "Build an LWC multi-column layout shell with named slots for up to three columns, collapsing to single column via @media breakpoint.",
            "Build an LWC stepper shell where each step is a named slot (slot='step-n') and the shell animates between steps with a CSS slide transition.",
            "Build an LWC with a named slot for a floating action button — parent places a lightning-button-icon that triggers a modal from the child shell.",
            "Build a Financial Services LWC dashboard shell using four named slots for widget panels — parent configures layout without touching shell code.",
            "Build a Healthcare LWC patient intake wizard shell with three named slots: demographics, insurance, and consent — each filled by a specialist form component.",
            "Build a Retail LWC store locator shell with named slots for search bar, map panel, and results list — parent controls all three sections.",
            "Build an Energy LWC field job shell with named slots for job briefing, parts checklist, and completion sign-off.",
            "Build an Insurance LWC risk assessment shell with named slots for property details, coverage options, and premium calculation result.",
            "Build a Professional Services LWC proposal shell with named slots for executive summary, scope section, and pricing table.",
        ],
    },
    {
        "name": "Wire and Imperative Hybrid",
        "max_tokens": 7000,
        "prompts": [
            "Build an LWC using @wire(getRecord) for Contact display and imperative Apex updateContact on Save, calling refreshApex(this.wiredResult) after success.",
            "Build an LWC with @wire(getListUi) for Account list and imperative Apex bulkUpdate on selected rows, then notifyRecordUpdateAvailable to refresh LDS cache.",
            "Build an LWC with @wire(getPicklistValues) for a filter combobox and imperative Apex fetch for filtered results, with a shared isLoading for both.",
            "Build an LWC with optimistic UI — spread-update the local array on button click, call imperative Apex, and roll back to original data on error with a toast.",
            "Build an LWC using @wire(getRecord) for read display and lightning-record-edit-form for edits, calling notifyRecordUpdateAvailable after onsuccess.",
            "Build an LWC with @wire(Apex) for a dashboard and a date-range combobox that triggers imperative Apex re-fetch, showing a single spinner for both.",
            "Build an LWC with @wire(getRelatedListRecords) for child Opportunities and a manual Refresh button calling refreshApex — with a comment explaining why no polling.",
            "Build an LWC with @wire(getObjectInfo) for field metadata and imperative Apex upsert, using field API names from objectInfo to build the payload dynamically.",
            "Build an LWC with @wire(getListUi) for a paginated list and an imperative Apex search that replaces the wire results temporarily when the user searches.",
            "Build a Financial Services LWC with @wire for Loan_Application__c list and imperative Apex bulk status update, then refreshApex after save.",
            "Build a Healthcare LWC with @wire(getRecord) for Patient__c display and imperative Apex updatePatient on form submit, calling notifyRecordUpdateAvailable after DML.",
            "Build a Manufacturing LWC with @wire(getListUi) for Work_Order__c and imperative Apex bulkComplete on selected rows, then refreshApex to re-fetch the wire.",
            "Build a Retail LWC with @wire(getPicklistValues) for Product category filter and imperative Apex search for filtered Products, with combined isLoading state.",
            "Build a Telecom LWC with optimistic UI — immediately mark Service_Request__c as resolved locally then call imperative Apex, rolling back on failure.",
            "Build an Energy LWC with @wire(getRecord) for Meter__c display and lightning-record-edit-form for edits, calling notifyRecordUpdateAvailable on onsuccess.",
            "Build an Insurance LWC with @wire(Apex) for Claims dashboard metrics and imperative Apex re-fetch when date filter changes, single spinner for both.",
            "Build a Professional Services LWC with @wire(getRelatedListRecords) for Project Milestones and a Refresh button calling refreshApex, with a no-polling comment.",
            "Build a Financial Services LWC with @wire for Portfolio__c and imperative Apex calculateReturns on date range change, shared isLoading.",
            "Build a Healthcare LWC combining @wire(getRecord) for Appointment__c read and lightning-record-edit-form for updates, refreshing wire with notifyRecordUpdateAvailable.",
            "Build a Manufacturing LWC with @wire(getPicklistValues) for asset status filter and imperative Apex bulk asset status update with refreshApex after save.",
            "Build a Retail LWC with @wire(getListUi) for Order__c list and imperative Apex cancelOrders on selected rows, then notifyRecordUpdateAvailable.",
            "Build a Telecom LWC with @wire(Apex) for usage dashboard and imperative Apex re-fetch when the billing period combobox changes.",
            "Build an Energy LWC with @wire(getRelatedListRecords) for related Field_Service_Job__c records and imperative Apex completeJob on button click, then refreshApex.",
            "Build an Insurance LWC with @wire(getRecord) for Policy__c display and imperative Apex renewPolicy on button click, calling notifyRecordUpdateAvailable after success.",
            "Build a Professional Services LWC with @wire(getListUi) for Timesheet__c list and imperative Apex approveTimesheets on selected rows, then refreshApex.",
            "Build an LWC with @wire(getRecord) that tracks wiredResult for refreshApex and an imperative Apex save — both handlers set isLoading correctly.",
            "Build an LWC that uses @wire(Apex) for initial data load and imperative Apex for a 'Sync Now' button, preventing the button from being clicked while either is loading.",
            "Build an LWC with a @wire(getListUi) list and a searchbox that triggers imperative Apex — when search is cleared, wire results are shown again.",
            "Build a Financial Services LWC with @wire(getRelatedListRecords) for KYC_Document__c and imperative Apex verifyDocument on row action, then refreshApex.",
            "Build a Healthcare LWC with @wire(Apex) for Care_Plan__c metrics and imperative Apex updateGoal on inline edit save, calling refreshApex after.",
            "Build a Manufacturing LWC with @wire(getObjectInfo) for Production_Run__c field metadata and imperative Apex createRun using the field API names from objectInfo.",
            "Build a Retail LWC with @wire(getPicklistValues) for Loyalty tier filter and imperative Apex calculatePoints on selected records, refreshing the wire after.",
            "Build a Telecom LWC with @wire(getListUi) for Billing_Account__c and imperative Apex generateInvoice on button click, then notifyRecordUpdateAvailable.",
            "Build an Energy LWC with @wire(getRecord) for Energy_Usage__c display and imperative Apex exportToCsv, returning a download link after generation.",
            "Build an Insurance LWC with @wire(getListUi) for Claim__c and imperative Apex bulkApprove on selected rows, refreshing wire after success.",
            "Build a Professional Services LWC with @wire(getRecord) for Milestone__c display and imperative Apex completeMilestone, calling notifyRecordUpdateAvailable.",
            "Build an LWC with a combined loading state — spinner shown when EITHER the wire is pending OR an imperative call is in-flight — using a counter approach.",
            "Build an LWC where @wire(getListUi) drives the initial list and an imperative Apex call adds a new record, then uses the wire's refresh to show the new record.",
            "Build an LWC with @wire(Apex) for a monthly summary chart and imperative Apex re-fetch with different month parameter when user clicks Previous/Next.",
            "Build a Financial Services LWC with @wire(getRecord) for Financial_Account__c display and imperative Apex transferFunds, with optimistic balance update and rollback.",
        ],
    },
    {
        "name": "LWC Service Components",
        "max_tokens": 7000,
        "prompts": [
            "Build an LWC service component with empty <template> that exposes @api showToast(variant, title, message) method using ShowToastEvent.",
            "Build an LWC service component with empty <template> that exposes @api navigateToRecord(recordId, objectName) using NavigationMixin.",
            "Build an LWC service component that manages a confirmation dialog via @api confirm(title, message) returning a Promise resolved on user action.",
            "Build an LWC service component exposing @api logActivity(recordId, description) that calls Apex to create a Task record imperatively.",
            "Build an LWC service component exposing @api publish(channel, payload) and @api subscribe(channel, handler) wrapping the LMS service.",
            "Build an LWC service component with @api printRecord(recordId) that fetches record fields via Apex and triggers window.print() on a formatted div.",
            "Build an LWC service component exposing @api exportToCsv(data, fileName) that converts a JSON array to CSV and triggers a browser download.",
            "Build an LWC service component exposing @api copyToClipboard(text) using the Clipboard API with a success toast confirmation.",
            "Build an LWC service component that wraps localStorage with @api setItem(key, value), @api getItem(key), and @api removeItem(key) methods.",
            "Build an LWC service component exposing @api debounce(fn, delay) returning a debounced version of a passed function.",
            "Build an LWC service component that wraps empApi subscribe/unsubscribe with @api methods, managing the subscription lifecycle internally.",
            "Build an LWC service component exposing @api formatCurrency(amount, currency) and @api formatDate(dateStr, format) utility methods.",
            "Build an LWC service component with @api trackEvent(category, action, label) that calls Apex to store analytics events imperatively.",
            "Build an LWC service component exposing @api fetchWithCache(cacheKey, apexFn, args) — returns cached result or calls Apex and caches.",
            "Build an LWC service component wrapping NavigationMixin for community page navigation with @api navigateToCommunityPage(pageName, params).",
            "Build a Financial Services LWC service component exposing @api formatLoanAmount(amount) and @api calculateMonthlyPayment(principal, rate, term).",
            "Build a Healthcare LWC service component exposing @api validatePatientAge(dateOfBirth) and @api formatMedicalRecordId(id) utility methods.",
            "Build a Manufacturing LWC service component exposing @api generateWorkOrderNumber() calling Apex and @api formatAssetTag(assetId).",
            "Build a Retail LWC service component exposing @api calculateDiscount(price, pct) and @api formatProductCode(productId) helpers.",
            "Build a Telecom LWC service component exposing @api formatDataUsage(bytes) and @api calculateBillTotal(usageItems) utilities.",
            "Build an Energy LWC service component exposing @api formatMeterReading(reading, unit) and @api calculateConsumption(start, end) helpers.",
            "Build an Insurance LWC service component exposing @api calculatePremium(coverage, riskScore) and @api formatPolicyNumber(id).",
            "Build a Professional Services LWC service component exposing @api calculateHourlyRate(salary, overhead) and @api formatProjectCode(id).",
            "Build an LWC service component that exposes @api openModal(config) where config has title, body, confirmLabel — renders the modal imperatively.",
            "Build an LWC service component exposing @api validateFields(fieldMap) returning an array of validation error objects for each invalid field.",
            "Build a Financial Services LWC toast service component that queues ShowToastEvent notifications with a maximum queue size of 3.",
            "Build a Healthcare LWC service component exposing @api checkPermission(permissionName) calling Apex and caching the result per session.",
            "Build a Manufacturing LWC service component exposing @api batchUpdate(records, chunkSize) that splits records and calls Apex sequentially.",
            "Build a Retail LWC service component exposing @api searchProducts(query) with built-in 300ms debounce and result caching by query.",
            "Build a Telecom LWC service component exposing @api subscribeToEvents(channel, handler) wrapping empApi with automatic cleanup on disconnect.",
            "Build an Energy LWC service component exposing @api getOutageStatus(meterId) with a 60-second TTL cache to avoid repeated Apex calls.",
            "Build an Insurance LWC service component exposing @api validatePolicy(policyData) running client-side business rule checks before Apex save.",
            "Build a Professional Services LWC service component exposing @api trackTimeEntry(projectId, hours, notes) calling Apex imperatively.",
            "Build an LWC service component exposing @api resolveLookup(sobjectType, searchTerm) using Apex SOSL and caching results per term.",
            "Build an LWC service component exposing @api sanitizeInput(value) that strips HTML tags and SOQL special chars before returning safe value.",
            "Build a Financial Services LWC service component that exposes @api generateStatement(accountId) calling Apex and returning a download URL.",
            "Build a Healthcare LWC service component exposing @api scheduleReminder(patientId, message, dateTime) calling Apex to create a reminder Task.",
            "Build a Manufacturing LWC service component exposing @api scanBarcode() wrapping lightning/mobileCapabilities barcode scanner with a Promise.",
            "Build a Retail LWC service component exposing @api applyLoyaltyDiscount(orderId, memberId) calling Apex and returning updated pricing.",
            "Build a Telecom LWC service component exposing @api diagnoseService(accountId) calling Apex to run network diagnostics and return results.",
        ],
    },
    {
        "name": "Lightning Message Service",
        "max_tokens": 7000,
        "prompts": [
            "Build an LWC LMS publisher datatable of Accounts and a subscriber detail panel connected by RecordSelected message channel with APPLICATION_SCOPE.",
            "Build an LWC filter panel that publishes FilterCriteria (search, status, date) via LMS and a results list that re-fetches via Apex when the message arrives.",
            "Build three sibling LWC components: a search bar publishes SearchQuery via LMS, a list subscribes and fetches results, a summary subscribes and shows counts.",
            "Build an LWC LMS subscriber that receives a recordId and triggers notifyRecordUpdateAvailable when a RECORD_SAVED message arrives.",
            "Build an LWC wizard stepper that publishes StepCompleted via LMS and a progress bar component that subscribes to update visual step state.",
            "Build an LWC notification centre subscribing to AlertMessage, RecordUpdated, and TaskAssigned LMS channels routing each to different display sections.",
            "Build an LWC master-detail layout where a list publishes RECORD_SELECTED via LMS and a detail panel subscribes replacing direct @api recordId.",
            "Build an LWC LMS demo showing explicit subscription cleanup: subscribe in connectedCallback, store handle, unsubscribe in disconnectedCallback with comments.",
            "Build a Financial Services LWC publisher showing Loan_Application__c list and subscriber showing Portfolio__c detail connected via LMS RecordSelected.",
            "Build a Healthcare LWC: Patient list publishes PatientSelected via LMS, appointment panel subscribes and loads Appointment__c records for that patient.",
            "Build a Manufacturing LWC: Work Order list publishes WorkOrderSelected via LMS, quality inspection panel subscribes and loads Quality_Inspection__c records.",
            "Build a Retail LWC filter panel publishing ProductFilter (category, price range) via LMS and a product grid subscribing and re-fetching Product__c records.",
            "Build a Telecom LWC: Service Request list publishes RequestSelected via LMS, usage dashboard subscribes and loads Usage_Summary__c for that request.",
            "Build an Energy LWC: Meter list publishes MeterSelected via LMS, outage history panel subscribes and loads Outage_Report__c records for that meter.",
            "Build an Insurance LWC three-component LMS pattern: claim list publisher, claim detail subscriber, and a premium summary subscriber on the same flexipage.",
            "Build a Professional Services LWC: Project list publishes ProjectSelected via LMS, timesheet panel subscribes and loads Timesheet__c records.",
            "Build a Financial Services LWC where saving a KYC_Document__c fires RECORD_SAVED LMS and a portfolio summary panel subscribes and calls refreshApex.",
            "Build a Healthcare LWC care plan editor that publishes PLAN_UPDATED via LMS when saved and a patient summary panel subscribes to refresh its wire.",
            "Build a Manufacturing LWC production run creator that publishes RUN_CREATED via LMS and a dashboard panel subscribes to increment its live count.",
            "Build a Retail LWC order status updater publishing ORDER_STATUS_CHANGED via LMS and a loyalty points panel subscribing to recalculate points.",
            "Build a Telecom LWC billing account editor publishing BILLING_UPDATED via LMS and a network asset panel subscribing to filter assets by account.",
            "Build an Energy LWC field service job completer publishing JOB_COMPLETED via LMS and an outage status board subscribing to mark the outage resolved.",
            "Build an Insurance LWC risk assessment approver publishing ASSESSMENT_APPROVED via LMS and a coverage panel subscribing to update coverage status.",
            "Build a Professional Services LWC milestone completer publishing MILESTONE_DONE via LMS and a project health indicator subscribing to update completion %.",
            "Build a Financial Services LWC with APPLICATION_SCOPE LMS so a portfolio selector in the sidebar communicates to a loan list in the main panel.",
            "Build a Healthcare LWC with APPLICATION_SCOPE LMS so a department selector in the utility bar communicates to a patient list on the record page.",
            "Build an LWC that publishes a REFRESH_REQUEST message via LMS and multiple components subscribe to call refreshApex or notifyRecordUpdateAvailable.",
            "Build an LWC LMS payload validator that subscribes to any channel, validates the incoming message schema, and logs malformed payloads to Apex.",
            "Build an LWC LMS analytics tracker that subscribes to USER_ACTION channel and batches events before sending to Apex for reporting.",
            "Build a Manufacturing LWC quality alert publisher that fires QualityAlert LMS when inspection score drops below threshold, subscribers highlight affected assets.",
            "Build a Retail LWC inventory alert that publishes LOW_STOCK via LMS when quantity drops below reorder point, subscribers refresh their product lists.",
            "Build a Telecom LWC network event publisher that fires NETWORK_EVENT via LMS from a Platform Event CDC subscriber, bridging empApi to LMS.",
            "Build an Energy LWC outage publisher that fires OUTAGE_DECLARED via LMS on form submit and multiple subscriber panels update their status displays.",
            "Build an Insurance LWC claim status publisher that fires CLAIM_STATUS_CHANGED via LMS and a timeline panel subscribes to prepend a new status node.",
            "Build a Professional Services LWC approval publisher that fires APPROVAL_REQUIRED via LMS and a pending approvals panel subscribes to increment its count badge.",
            "Build an LWC LMS hub component with @api publish(channel, payload) and @api subscribe(channel, handler) methods that any sibling can call directly.",
            "Build a Financial Services LWC portfolio rebalancer that publishes REBALANCE_COMPLETE via LMS after Apex finishes, subscribers refresh their allocation charts.",
            "Build a Healthcare LWC appointment booker that publishes APPOINTMENT_BOOKED via LMS on save and a calendar component subscribes to add the new slot.",
            "Build an LWC that uses APPLICATION_SCOPE LMS to synchronize a global date-range filter across three dashboard panels on a flexipage.",
            "Build an LWC LMS subscription manager component that lists all active subscriptions in the org page and shows their handle IDs for debugging.",
        ],
    },
    {
        "name": "Dynamic Components (lwc:is)",
        "max_tokens": 7000,
        "prompts": [
            "Build an LWC dashboard using lwc:is to render c-bar-chart, c-line-chart, or c-pie-chart based on a combobox selection, each receiving the same @api data.",
            "Build an LWC record renderer using lwc:is to load c-account-detail, c-contact-detail, or c-case-detail based on objectApiName passed to the container.",
            "Build an LWC widget container using lwc:is to render c-kpi-tile, c-activity-feed, or c-recent-records based on a JSON layout config array from a design attribute.",
            "Build an LWC form renderer using lwc:is to display c-text-input, c-date-input, c-picklist-input, or c-lookup-input based on field metadata from getObjectInfo.",
            "Build an LWC step wizard using lwc:is to render c-step-details, c-step-address, c-step-review for currentStep integer with @api data passed to each.",
            "Build an LWC notification renderer using lwc:is to render c-alert-card, c-info-card, or c-success-card based on notification.type in a list.",
            "Build an LWC permission-based renderer using lwc:is to show c-admin-view, c-manager-view, or c-read-only-view based on custom permissions checked via Apex.",
            "Build an LWC tab content loader using lwc:is that lazily renders each tab component on first activation, caching the constructor after first load.",
            "Build a Financial Services LWC dashboard using lwc:is to render c-loan-kpi, c-portfolio-kpi, or c-kyc-kpi based on a config array.",
            "Build a Healthcare LWC record renderer using lwc:is to show c-patient-detail, c-appointment-detail, or c-care-plan-detail based on record type.",
            "Build a Manufacturing LWC dashboard using lwc:is to render c-work-order-summary, c-asset-status, or c-quality-report based on active tab.",
            "Build a Retail LWC product renderer using lwc:is to display c-product-card, c-product-list-row, or c-product-compact based on viewMode design attribute.",
            "Build a Telecom LWC service dashboard using lwc:is to render c-usage-chart, c-billing-summary, or c-network-status based on widget config.",
            "Build an Energy LWC field dashboard using lwc:is to show c-meter-detail, c-outage-map, or c-job-list based on field worker current task type.",
            "Build an Insurance LWC claims renderer using lwc:is to display c-claim-form, c-claim-review, or c-claim-summary based on claim status.",
            "Build a Professional Services LWC project dashboard using lwc:is to render c-timeline-view, c-resource-grid, or c-milestone-tracker based on user preference.",
            "Build a Financial Services LWC form renderer using lwc:is to display different input components for Loan_Application__c fields based on data type from getObjectInfo.",
            "Build a Healthcare LWC step wizard using lwc:is rendering c-patient-intake, c-insurance-verify, c-consent-form for each step with @api patient data.",
            "Build a Manufacturing LWC alert renderer using lwc:is to render c-critical-alert, c-warning-alert, or c-info-alert based on Quality_Inspection__c severity.",
            "Build a Retail LWC permission view using lwc:is to show c-store-admin-view, c-store-manager-view, or c-associate-view based on Apex permission check.",
            "Build a Telecom LWC notification list using lwc:is to render different notification card types per event type from Platform Events via empApi.",
            "Build an Energy LWC report renderer using lwc:is to show c-consumption-chart, c-cost-breakdown, or c-outage-history based on combobox selection.",
            "Build an Insurance LWC wizard using lwc:is rendering c-claim-details, c-policy-verify, c-damage-assessment, c-settlement-offer for each step.",
            "Build a Professional Services LWC layout renderer using lwc:is switching between c-kanban-board and c-gantt-chart based on a toggle, preserving data.",
            "Build a Financial Services LWC widget system using lwc:is where admin configures up to 4 widgets from a palette and the layout renders them dynamically.",
            "Build an LWC dynamic form that uses lwc:is to swap between c-simple-form and c-advanced-form based on a toggle, passing current form values between switches.",
            "Build an LWC error boundary pattern using lwc:is to show c-error-view when an @api errorType property is set, or the default content component otherwise.",
            "Build an LWC A/B test renderer using lwc:is to render c-variant-a or c-variant-b based on a random bucket stored in localStorage.",
            "Build an LWC role-based dashboard using lwc:is to render c-exec-dashboard, c-manager-dashboard, or c-rep-dashboard based on user role from Apex.",
            "Build a Manufacturing LWC machine status renderer using lwc:is to show c-running-view, c-idle-view, or c-fault-view based on Asset__c Status__c field.",
            "Build a Retail LWC checkout flow using lwc:is rendering c-cart-review, c-shipping-form, c-payment-form, c-confirmation for each checkout step.",
            "Build a Telecom LWC plan configurator using lwc:is rendering c-basic-plan, c-standard-plan, or c-premium-plan based on combobox selection with live price update.",
            "Build an Energy LWC report type renderer using lwc:is loading the correct report component dynamically based on a @api reportType property.",
            "Build an Insurance LWC underwriting workflow using lwc:is rendering c-initial-review, c-risk-assessment, c-approval-decision, c-policy-issue for each stage.",
            "Build a Professional Services LWC invoice renderer using lwc:is showing c-draft-invoice, c-pending-invoice, or c-paid-invoice based on invoice status.",
            "Build an LWC multi-tenant renderer using lwc:is that loads a different branded shell component based on @api tenantId mapped to constructor in a config object.",
            "Build an LWC search result renderer using lwc:is showing c-account-result, c-contact-result, or c-opportunity-result based on each result's sobjectType.",
            "Build a Financial Services LWC KPI renderer using lwc:is loading the right KPI tile component based on the metric type in a JSON dashboard config.",
            "Build a Healthcare LWC treatment renderer using lwc:is loading c-medication-view, c-therapy-view, or c-surgery-view based on treatment type field.",
            "Build an LWC dynamic layout system using lwc:is where an @api layout property accepts 'grid', 'list', or 'card' and renders the matching container component.",
        ],
    },
    {
        "name": "Rich UI & Styling",
        "max_tokens": 5000,  # lower — CSS-heavy responses truncate at 7000
        "prompts": [
            "Build an LWC profile card with avatar initials, name, role badge, metadata pills — CSS must include :host with custom properties, SLDS tokens, hover box-shadow transition.",
            "Build an LWC skeleton loading component — CSS must have @keyframes shimmer with background-position animation, matching card layout with avatar and line bars.",
            "Build an LWC KPI tiles grid — CSS must have CSS Grid layout, .status-success/.status-warning/.status-error classes with custom properties for threshold colors.",
            "Build an LWC multi-step progress tracker — CSS uses ::before pseudo-elements for the connecting line, filled/pulsing/pending circle states, SLDS design token colors.",
            "Build an LWC status swim-lane board — CSS uses Flexbox columns, scrollable card lanes, distinct left-border accent color per status, card hover elevation.",
            "Build an LWC custom HTML table with sticky header — CSS uses position:sticky, nth-child zebra striping, row hover highlight, sort indicator arrows via ::after.",
            "Build an LWC responsive card grid — CSS uses CSS Grid with auto-fill, @media breakpoints for 1/2/3 columns, card hover translateY and box-shadow transition.",
            "Build an LWC activity timeline — CSS uses ::before for the vertical line and ::after for circular nodes, type-based icon accent colors, expand/collapse transition.",
            "Build a Financial Services LWC portfolio summary card — CSS has :host with design tokens, gradient accent header, pill badges for asset classes, hover elevation.",
            "Build a Healthcare LWC patient intake card — CSS has shimmer skeleton, status indicator dot (green/amber/red), responsive two-column field grid with SLDS tokens.",
            "Build a Manufacturing LWC work order status board — CSS has Flexbox swim lanes, status-based left border colors, @keyframes pulse for overdue items, card shadow.",
            "Build a Retail LWC product catalog grid — CSS has CSS Grid auto-fill, product card with image placeholder shimmer, price badge, hover scale and shadow transition.",
            "Build a Telecom LWC usage dashboard tiles — CSS has CSS Grid KPI tiles, threshold-based color classes, animated progress bar @keyframes width transition.",
            "Build an Energy LWC meter reading card — CSS has :host tokens, gauge-style progress arc using CSS border-radius, status color properties, responsive layout.",
            "Build an Insurance LWC claims timeline — CSS has ::before vertical line, claim-status node colors (filed/reviewing/approved/rejected), slide-in @keyframes.",
            "Build a Professional Services LWC project health card — CSS has CSS Grid for KPI row, RAG status badges (red/amber/green via custom properties), hover elevation.",
            "Build a Financial Services LWC loan application stepper — CSS has ::before horizontal line, step states (completed/active/pending) using custom properties.",
            "Build a Healthcare LWC appointment calendar strip — CSS has horizontal scroll, day-card active state with brand color border, hover lift, today highlight ring.",
            "Build a Manufacturing LWC asset health dashboard — CSS has CSS Grid cards, animated fill bar @keyframes for utilization %, color thresholds via custom props.",
            "Build a Retail LWC order tracking stepper — CSS has ::before connecting line, step icons, completed (filled) and pending (outline) states, SLDS brand tokens.",
            "Build a Telecom LWC network status board — CSS has status dot pulse @keyframes, card grid, severity-based border color classes, sticky header.",
            "Build an Energy LWC field job card — CSS has priority badge (critical/high/normal via custom properties), map pin icon accent, responsive compact/expanded layout.",
            "Build an Insurance LWC policy comparison table — CSS has sticky header, highlighted recommended column, feature row hover, custom checkbox indicators via ::before.",
            "Build a Professional Services LWC resource allocation grid — CSS has CSS Grid, utilization bar fill transition, over-allocated red highlight class, hover tooltip.",
            "Build a Financial Services LWC KPI dashboard — CSS has :host tokens, @keyframes count-up placeholder, 4-column grid, threshold color classes, card hover shadow.",
            "Build an LWC notification card with severity-based left border (error/warning/info/success) using CSS custom properties, dismiss button, and slide-out @keyframes.",
            "Build an LWC data comparison card showing two columns with +/- delta indicators — CSS uses CSS Grid, green/red delta classes, SLDS design tokens for colors.",
            "Build an LWC tag/pill list editor where users add and remove tags — CSS uses Flexbox wrap, pill hover with ×, color variants per category via custom properties.",
            "Build an LWC collapsible section component — CSS uses max-height transition for smooth open/close animation, ::before chevron rotation, SLDS border tokens.",
            "Build an LWC avatar group showing up to 5 user initials overlapping — CSS uses negative margin-left, z-index stacking, border ring per avatar, +N overflow badge.",
            "Build a Financial Services LWC bond yield curve chart shell — CSS has responsive SVG container, tooltip on hover, grid lines via ::before pseudo-elements.",
            "Build a Healthcare LWC vital signs dashboard — CSS has CSS Grid tiles, color-coded normal/warning/critical ranges via custom properties, pulse @keyframes for alerts.",
            "Build a Manufacturing LWC production line status bar — CSS has Flexbox stations, filled/partial/empty fill animation via @keyframes, status-based background colors.",
            "Build a Retail LWC flash sale countdown card — CSS has a digits grid, flipping animation @keyframes, urgent color shift when under 60s via custom properties.",
            "Build a Telecom LWC signal strength indicator — CSS uses CSS Grid bars of increasing height, filled/empty bar classes, @keyframes pulse on active bar.",
            "Build an Energy LWC consumption gauge — CSS uses conic-gradient for the arc fill, custom property for fill percentage, color zones (green/amber/red).",
            "Build an Insurance LWC risk score meter — CSS uses a semicircle gauge with clip-path, pointer needle rotation via CSS custom property, zone color classes.",
            "Build a Professional Services LWC Gantt bar — CSS uses CSS Grid columns for time axis, task bar with fill width as %, milestone diamond via ::before.",
            "Build an LWC drag-and-drop sortable list — CSS uses cursor:grab, dragging opacity, drop zone dashed border highlight, smooth item translate transition.",
            "Build an LWC dark-mode aware card component — CSS uses @media (prefers-color-scheme: dark) overriding :host custom properties for background and text colors.",
        ],
    },
]

# ── Prompt Builder ─────────────────────────────────────────────────────────────
def build_all_prompts():
    """Generate the full prompt list for all 25 categories."""
    all_prompts = []

    for cat_idx, cat in enumerate(TEMPLATE_CATEGORIES):
        # 8 generic prompts
        for p in cat["generic_prompts"]:
            all_prompts.append({"prompt": p, "category": cat["name"],
                                "domain": "Generic", "max_tokens": cat["max_tokens"]})
        # 8 domains × 4 variations = 32 domain prompts
        for domain in DOMAINS:
            for variation in cat["variations"]:
                p = cat["domain_template"].format(
                    domain_name=domain["name"],
                    context=domain["context"],
                    examples=domain["examples"],
                    objects=domain["objects"],
                    variation=variation,
                )
                all_prompts.append({"prompt": p, "category": cat["name"],
                                    "domain": domain["name"], "max_tokens": cat["max_tokens"]})

    for cat in GAP_CATEGORIES:
        for p in cat["prompts"]:
            all_prompts.append({"prompt": p, "category": cat["name"],
                                "domain": "Generic", "max_tokens": cat["max_tokens"]})

    return all_prompts

# ── Response Parser ────────────────────────────────────────────────────────────
def parse_response(raw):
    try:
        instruction = re.search(r'=== INSTRUCTION ===\s*(.*?)\s*=== HTML ===', raw, re.DOTALL)
        html        = re.search(r'=== HTML ===\s*(.*?)\s*=== JS ===',          raw, re.DOTALL)
        js          = re.search(r'=== JS ===\s*(.*?)(?:\s*=== CSS ===|$)',      raw, re.DOTALL)
        css         = re.search(r'=== CSS ===\s*(.*?)$',                        raw, re.DOTALL)
        if not all([instruction, html, js]):
            return None
        instruction_text = instruction.group(1).strip()
        html_text        = html.group(1).strip()
        js_text          = js.group(1).strip()
        css_text         = css.group(1).strip() if css else ''
        if css_text.upper() == 'NONE':
            css_text = ''
        # Strip markdown fences
        for lang in ['html', 'javascript', 'js', 'css', '']:
            html_text = re.sub(rf'^\x60\x60\x60{lang}\s*', '', html_text, flags=re.MULTILINE).strip()
            html_text = re.sub(r'\s*\x60\x60\x60$', '', html_text).strip()
            js_text   = re.sub(rf'^\x60\x60\x60{lang}\s*', '', js_text,   flags=re.MULTILINE).strip()
            js_text   = re.sub(r'\s*\x60\x60\x60$', '', js_text).strip()
            if css_text:
                css_text = re.sub(rf'^\x60\x60\x60{lang}\s*', '', css_text, flags=re.MULTILINE).strip()
                css_text = re.sub(r'\s*\x60\x60\x60$', '', css_text).strip()
        # Derive component name
        name_match = re.search(r'export default class (\w+)', js_text)
        if not name_match:
            name_match = re.search(r"describe\(['\"]c-([\w-]+)", js_text)
            name = name_match.group(1).replace('-', '_').title().replace('_', '') if name_match else 'MyComponent'
        else:
            name = name_match.group(1)
        file_name = name[0].lower() + name[1:]
        combined  = f"<!-- {file_name}.html -->\n{html_text}\n\n// {file_name}.js\n{js_text}"
        if css_text:
            combined += f"\n\n/* {file_name}.css */\n{css_text}"
        return {'instruction': instruction_text, 'output': combined}
    except Exception:
        return None

# ── Inline Fixes ──────────────────────────────────────────────────────────────
_TRACK_PRIM_RE  = re.compile(r'(@track\s+)(\w+\s*=\s*(?:\'[^\']*\'|"[^"]*"|\d+(?:\.\d+)?|true|false|null)\s*;)')
_GETTER_RE      = re.compile(r'\bget\s+isLoading\s*\(')
_FIELD_DECL_RE  = re.compile(r'^(\s{4}isLoading\s*=\s*(?:true|false)\s*;[ \t]*\n)', re.MULTILINE)
_CSS_FENCE_RE   = re.compile(r'(/\*\s*[\w-]+\.css\s*\*/\s*\n)\s*\x60\x60\x60css\s*\n(.*?)\n\x60\x60\x60', re.DOTALL)
_DUP_HEADER_RE  = re.compile(r'^(<!--\s*[\w-]+\.html\s*-->)\s*\n(<!--\s*[\w-]+\.html\s*-->)', re.MULTILINE)
_HAS_TEST_RE    = re.compile(r'\b(?:describe|it|test)\s*\(')

def fix_example(ex):
    out = ex['output']
    out, _ = _TRACK_PRIM_RE.subn(r'\2', out)
    if _GETTER_RE.search(out):
        out, _ = _FIELD_DECL_RE.subn('', out)
    out, _ = _CSS_FENCE_RE.subn(r'\1\2', out)
    out, _ = _DUP_HEADER_RE.subn(r'\2', out)
    ex['output'] = out
    return ex

def is_bad_jest(ex):
    """Remove Jest examples with no actual test code."""
    instr = ex.get('instruction', '').lower()
    is_jest = any(k in instr for k in ['jest', 'unit test', 'test file', 'write test', 'tests for'])
    return is_jest and not _HAS_TEST_RE.search(ex['output'])

# ── API Call ───────────────────────────────────────────────────────────────────
def generate_one(item, n_done, n_total):
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user',   'content': item['prompt'] + FORMAT_REMINDER},
                ],
                temperature=0.5,
                max_tokens=item['max_tokens'],
            )
            raw    = r.choices[0].message.content
            raw    = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
            parsed = parse_response(raw)
            if parsed and len(parsed['output']) > 200:
                return parsed
            print(f'  ↩️  attempt {attempt+1} parse fail...', end=' ', flush=True)
        except Exception as e:
            print(f'  ⚠️  attempt {attempt+1} error: {e}', end=' ', flush=True)
        time.sleep(2)
    return None

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    all_prompts = build_all_prompts()

    # Count prompts per category; trim to TARGET
    by_cat = {}
    for item in all_prompts:
        by_cat.setdefault(item['category'], []).append(item)
    trimmed = []
    for cat, items in by_cat.items():
        trimmed.extend(items[:TARGET])

    # Load checkpoint
    done_prompts = set()
    results = []
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    done_prompts.add(rec['prompt'])
                    results.append(rec['example'])
                except Exception:
                    pass

    work_items = [i for i in trimmed if i['prompt'] not in done_prompts]

    # Print plan
    cats_remaining = Counter(i['category'] for i in work_items)
    cats_done      = Counter(r['category'] for r in results)
    print(f'\n{"─"*60}')
    print(f'  LWC Master Generator — {MODEL}')
    print(f'{"─"*60}')
    print(f'  Total prompts defined : {len(trimmed)}')
    print(f'  Already done          : {len(done_prompts)}')
    print(f'  Remaining             : {len(work_items)}')
    print(f'  Workers               : {WORKERS}')
    print(f'{"─"*60}')
    print(f'  Category status:')
    all_cats = sorted(set(i['category'] for i in trimmed))
    for cat in all_cats:
        done = cats_done.get(cat, 0)
        rem  = cats_remaining.get(cat, 0)
        bar  = '✅' if done >= TARGET else f'{done}/{TARGET}'
        print(f'    {cat:<45} {bar}  (+{rem} remaining)')
    print(f'{"─"*60}\n')

    if not work_items:
        print('Nothing to generate — dataset is complete!')
    else:
        ckpt_lock = threading.Lock()
        counter   = {'n': 0}
        total     = len(work_items)

        def process(item):
            example = generate_one(item, counter['n'], total)
            with ckpt_lock:
                counter['n'] += 1
                n = counter['n']
            if not example:
                print(f'[{n}/{total}] ⚠️  skipped — {item["category"]}', flush=True)
                return None
            example = fix_example(example)
            if is_bad_jest(example):
                print(f'[{n}/{total}] 🗑  removed (no test code) — {item["category"]}', flush=True)
                return None
            example['prompt']   = example.pop('instruction')
            example['completion'] = example.pop('output')
            example['input']    = ''
            example['source']   = f'synthetic_lwc_master/{item["category"].lower().replace(" ","_").replace("(","").replace(")","").replace("/","_")}'
            example['type']     = 'lwc'
            example['category'] = item['category']
            example['domain']   = item.get('domain', 'Generic')
            with ckpt_lock:
                with open(CHECKPOINT, 'a') as f:
                    f.write(json.dumps({'prompt': item['prompt'], 'example': example}) + '\n')
            lines = len(example['completion'].splitlines())
            print(f'[{n}/{total}] ✅ {item["category"]} ({lines} lines)', flush=True)
            return example

        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            futures = {executor.submit(process, item): item for item in work_items}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    with ckpt_lock:
                        results.append(result)

    # Write final output
    with open(OUTPUT, 'w') as f:
        for ex in results:
            f.write(json.dumps(ex) + '\n')

    cats = Counter(ex['category'] for ex in results)
    print(f'\n{"─"*60}')
    print(f'  DONE — {len(results)} examples written to {OUTPUT}')
    print(f'{"─"*60}')
    for cat in sorted(cats):
        n   = cats[cat]
        bar = '✅' if n >= TARGET else f'⚠️  {TARGET-n} short'
        print(f'  {cat:<45} {n:>3}  {bar}')
    print(f'{"─"*60}')


if __name__ == '__main__':
    main()
