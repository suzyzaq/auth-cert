# Rules Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an independent, searchable rules center and a safe external link to the public authorization qualification database.

**Architecture:** Keep rule definitions in a typed frontend data module and filtering in a pure function so behavior can be tested without the page. Render `/rules` through the existing React router and expose the public database as a new-tab link with no internal query parameters.

**Tech Stack:** React 19, React Router, TypeScript, Vitest, Testing Library, existing industrial editorial CSS system.

---

### Task 1: Typed Rule Catalog and Filtering

**Files:**
- Create: `apps/web/src/features/rules/rule-catalog.ts`
- Create: `apps/web/src/features/rules/rule-catalog.test.ts`

- [ ] **Step 1: Write the failing filter test**

```ts
import { describe, expect, it } from "vitest";
import { filterRules, inspectionRules } from "./rule-catalog.js";

describe("rule catalog", () => {
  it("combines category, severity and keyword filters", () => {
    expect(
      filterRules(inspectionRules, {
        category: "FIELD",
        severity: "CRITICAL",
        query: "日期",
      }).map((rule) => rule.id),
    ).toEqual(["date-order"]);
  });
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
pnpm --filter @auth-inspection/web test -- src/features/rules/rule-catalog.test.ts
```

Expected: FAIL because `rule-catalog.ts` does not exist.

- [ ] **Step 3: Implement the typed catalog**

Define `RuleCategory`, `RuleSeverity`, `InspectionRule`, `RuleFilters`,
`inspectionRules`, and `filterRules`. Include representative rules for availability,
freshness, consistency, field completeness, business logic, and evidence continuity.
Filtering must match all active filters and search name, description, fields, and condition.

- [ ] **Step 4: Run the test and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/features/rules
git commit -m "feat: add typed inspection rule catalog"
```

### Task 2: Rules Center Page and Navigation

**Files:**
- Create: `apps/web/src/pages/RulesCenterPage.tsx`
- Create: `apps/web/src/pages/RulesCenterPage.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/components/AppShell.tsx`
- Modify: `apps/web/src/styles/global.css`

- [ ] **Step 1: Write failing page and navigation tests**

```tsx
// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppShell } from "../components/AppShell.js";
import { RulesCenterPage } from "./RulesCenterPage.js";

it("filters rules and shows rule details", async () => {
  render(<MemoryRouter><RulesCenterPage /></MemoryRouter>);
  await userEvent.setup().type(screen.getByLabelText("搜索规则"), "边界分片");
  expect(screen.getByText("边界分片探测")).toBeInTheDocument();
});

it("opens the public database without referrer access", () => {
  render(<MemoryRouter><AppShell><div /></AppShell></MemoryRouter>);
  const link = screen.getByRole("link", { name: "授权资质数据库" });
  expect(link).toHaveAttribute("href", "https://suzyzaq.github.io/auth-cert-db/");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
});
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
pnpm --filter @auth-inspection/web test -- src/pages/RulesCenterPage.test.tsx
```

Expected: FAIL because `RulesCenterPage` and the navigation link do not exist.

- [ ] **Step 3: Implement the page and route**

Add `/rules` to `App.tsx`. Replace the `#rules` anchor with a router link. Add the
public database external link with exact `href`, `target="_blank"`, and
`rel="noopener noreferrer"`. Build metric cards, search, category and severity filters,
rule cards, detail panel, enabled status, fields, condition, hit count, and last run time.

- [ ] **Step 4: Add responsive styles**

Reuse the existing canvas, hard border, offset shadow, acid, blue, green, and orange
tokens. Use a two-column rule list/detail layout above 980px and a single column below.
At widths below 720px, wrap navigation and controls without horizontal overflow.

- [ ] **Step 5: Run page tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src
git commit -m "feat: add independent rules center"
```

### Task 3: Full Verification and Browser Acceptance

**Files:**
- Modify only files required to correct verified defects.

- [ ] **Step 1: Run automated verification**

```powershell
pnpm test
pnpm typecheck
pnpm lint
pnpm build
```

Expected: 0 failed tests, 0 type errors, 0 lint errors, successful production build.

- [ ] **Step 2: Verify the desktop page**

Open `http://127.0.0.1:5173/rules`; confirm six categories are represented, search and
filters update the list, a rule detail is visible, and the browser console contains no errors.

- [ ] **Step 3: Verify the external link**

Inspect the link attributes without navigating away. Confirm the exact URL, new-tab target,
and `noopener noreferrer`; do not transmit internal data.

- [ ] **Step 4: Verify narrow layout**

At a narrow viewport, confirm the page has no horizontal overflow and filters remain usable.

- [ ] **Step 5: Commit verification fixes if needed**

```powershell
git add apps/web/src
git commit -m "fix: refine rules center acceptance"
```

