# Attachment Field Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only attachment-first field reconstruction and reconciliation flow with evidence-backed review.

**Architecture:** Add a domain result model and deterministic reconciliation engine, then compose OCR/model outputs in the worker. Feed the same result shape into a corrected evidence review page and an expanded independent rules center. External OCR and matching services remain replaceable adapters and writeback stays disabled.

**Tech Stack:** TypeScript, React, Vitest, Fastify, pnpm workspace

---

### Task 1: Define the evidence-backed result contract

**Files:**
- Create: `packages/domain/src/reconciliation.ts`
- Modify: `packages/domain/src/index.ts`
- Test: `packages/domain/src/reconciliation.test.ts`

- [ ] **Step 1: Write failing tests for comparison states, missing attachment evidence, date normalization and chain-dependent level handling.**
- [ ] **Step 2: Run `pnpm test packages/domain/src/reconciliation.test.ts` and confirm missing exports fail.**
- [ ] **Step 3: Implement typed source fields, attachment fields, evidence, comparisons, issues and the deterministic reconciliation function.**
- [ ] **Step 4: Run the focused test and confirm it passes.**

### Task 2: Compose dual parser evidence

**Files:**
- Modify: `packages/integrations/src/parsing/contracts.ts`
- Create: `packages/integrations/src/parsing/composite-parser.ts`
- Test: `packages/integrations/src/parsing/composite-parser.test.ts`
- Modify: `apps/worker/src/process-inspection.ts`
- Test: `apps/worker/src/process-inspection.test.ts`

- [ ] **Step 1: Write failing tests showing matching OCR/model values are confirmed and conflicting values require review.**
- [ ] **Step 2: Run the focused tests and confirm the composite parser is missing.**
- [ ] **Step 3: Implement the composite parser with page and evidence preservation.**
- [ ] **Step 4: Extend the worker job with source fields and save a complete reconciliation result.**
- [ ] **Step 5: Run worker and integration tests and confirm they pass.**

### Task 3: Present real comparison structure in the review page

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/data.ts`
- Rewrite: `apps/web/src/pages/EvidenceReviewPage.tsx`
- Create: `apps/web/src/pages/EvidenceReviewPage.test.tsx`
- Modify: `apps/web/src/styles/global.css`

- [ ] **Step 1: Write a failing page test for Chinese labels, source value, attachment value, evidence page and confidence.**
- [ ] **Step 2: Run the focused test and confirm the current garbled page fails.**
- [ ] **Step 3: Replace demo comparison tuples with the domain-aligned result structure and render evidence-backed comparison cards.**
- [ ] **Step 4: Add responsive styling with a restrained industrial evidence-desk visual direction.**
- [ ] **Step 5: Run the page tests and confirm they pass.**

### Task 4: Expand the independent rules center

**Files:**
- Modify: `apps/web/src/features/rules/rule-catalog.ts`
- Modify: `apps/web/src/features/rules/rule-catalog.test.ts`
- Modify: `apps/web/src/pages/RulesCenterPage.tsx`
- Modify: `apps/web/src/pages/RulesCenterPage.test.tsx`

- [ ] **Step 1: Add failing tests for attachment-first priority, nine comparison states, auto-correction gates and error codes.**
- [ ] **Step 2: Run the focused tests and confirm missing rules fail.**
- [ ] **Step 3: Add the rule groups and render them with plain-language explanations.**
- [ ] **Step 4: Run rules-center tests and confirm they pass.**

### Task 5: Verify the complete workbench

**Files:**
- Modify: `docs/operations/acceptance-checklist.md`

- [ ] **Step 1: Document attachment reconstruction and evidence review acceptance checks.**
- [ ] **Step 2: Run `pnpm test`, `pnpm typecheck`, `pnpm lint`, and `pnpm build`.**
- [ ] **Step 3: Inspect the review and rules pages in the local browser at desktop and narrow widths.**
- [ ] **Step 4: Confirm writeback remains disabled and no credentials or private attachment URLs are committed.**
