# Google AI Studio Estate Inventory — ICT Control Edition

Status: SOURCE-DISCOVERED / PROVIDER-INVENTORY-PENDING / PUBLIC-SAFE
Owner and Final Authority: Kim Kagiso Mosiane
Parent estate: Kim Dataverse

## Purpose

This register gives ICT a controlled map of Google AI Studio as part of the Kim Dataverse resource pool. It separates founder-confirmed resource membership, Drive-discovered supporting artefacts and provider-native facts that still require direct readback from Google AI Studio or Google Cloud.

## Estate role

Google AI Studio is an authorised experimentation and prototyping surface for:

- Gemini prompt and model experimentation;
- multimodal prototype design;
- candidate application generation;
- evaluation and comparison of prompts, models and parameters;
- pre-production workflow design;
- export of governed prototypes into Google Cloud, GitHub or another controlled runtime.

Google AI Studio is not the canonical store for mission state, evidence, authority, secrets, production runtime state or final release receipts.

## Source-discovered supporting assets

The Drive estate contains multiple AI Studio-related control and implementation artefacts, including:

- a dedicated `Google AI Studio` folder;
- `MODISA AI Studio Automation Blueprint`;
- `MODISA AI Studio Automation — Deployable Source Package`;
- `MODISA AI Studio Automation Registry`;
- `NX10 AI Studio App Extraction`;
- `Google AI Studio Automation Layer - Master Template Extension`;
- `Master Google Surfaces Capability Matrix`;
- `Master Google Surfaces - Improvement Backlog and Execution Router`;
- related direct-runtime command, proof and recovery ledgers.

These artefacts prove that Google AI Studio has been actively incorporated into the wider estate design. They do not by themselves prove the current provider-side inventory of projects, prompts, models, API keys, files, apps, ownership or deployment bindings.

## ICT inventory domains

### Projects and workspaces

Record for each project or workspace:

- stable project ID or public-safe alias;
- owner and collaborators;
- creation and last-use timestamps;
- business purpose and parent mission;
- linked Google Cloud project;
- linked GitHub repository or branch;
- data classification;
- retention and closure state.

### Models and configurations

Record:

- model family and exact version;
- modality;
- temperature, top-p, top-k and token settings;
- safety configuration;
- grounding, tools or function-calling settings;
- evaluation status;
- deprecation or replacement risk.

### Prompts and system instructions

Record:

- prompt ID and version;
- source mission and owner;
- system instruction hash;
- input and output schema;
- sample fixtures;
- evaluation evidence;
- approved use boundary;
- export target;
- supersession state.

### Files and source data

Record:

- file alias and source-system pointer;
- data owner;
- classification and sensitivity;
- whether raw evidence was uploaded;
- residency and retention requirements;
- permitted reuse;
- destruction state.

Raw confidential evidence must not be uploaded merely for convenience. In-place processing and minimum necessary data remain preferred.

### Generated applications and exports

Record:

- generated app or code package;
- export timestamp and destination;
- commit or artefact hash;
- dependencies;
- security review;
- test result;
- production target;
- deployment and readback receipt.

An AI Studio prototype is not production until exported, versioned, tested, secured, deployed and read back through an authorised runtime.

### Credentials and access

Record metadata only:

- credential reference name;
- owning Google Cloud project;
- intended runtime consumer;
- storage location in Secret Manager or equivalent vault;
- creation, rotation and revocation state;
- least-privilege binding;
- audit evidence.

Never place raw API keys in GitHub, Drive registers, Dataverse records or chat output.

## Trust boundaries

| Boundary | Required control |
|---|---|
| Founder to AI Studio | exact mission and approved experimentation scope |
| AI Studio to source data | minimum necessary data and classification review |
| AI Studio to Google Cloud | verified project binding and credential isolation |
| AI Studio to GitHub | export, hash, review, CI and provenance |
| AI Studio prototype to production | tests, security, deployment, readback and receipt |
| Public estate map to private project details | aliases only; private pointer bridge retains identifiers |

## Current verified state

| Control | State |
|---|---|
| Resource-pool membership | FOUNDER CONFIRMED |
| Supporting Drive artefacts | DISCOVERED |
| Dedicated Drive folder | DISCOVERED |
| Provider project inventory | UNVERIFIED |
| Model and prompt inventory | UNVERIFIED |
| Collaborator and access inventory | UNVERIFIED |
| File and data inventory | UNVERIFIED |
| Google Cloud bindings | UNVERIFIED |
| Credential lifecycle | UNVERIFIED |
| Production deployments | UNVERIFIED |

## Required provider-native readback

A complete estate binding requires direct readback of:

1. project and workspace list;
2. owners and collaborators;
3. prompts, models and configurations;
4. uploaded files and data classification;
5. generated apps and export destinations;
6. linked Google Cloud projects;
7. API and credential references without secret values;
8. deployment bindings and receipts;
9. audit and last-use metadata;
10. inactive, duplicate and abandoned resources.

## Maturity

`GOOGLE_AI_STUDIO_RESOURCE_CONFIRMED / DRIVE_SUPPORT_ASSETS_DISCOVERED / PROVIDER_NATIVE_INVENTORY_PENDING`
