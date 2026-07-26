# Dify Brand and Category Normalization Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the existing OFS brand/category normalization service where `difydev.ofs.cn` can reach it and import a read-only Dify custom tool for authorization inspection workflows.

**Architecture:** Keep the deterministic FastAPI service as the single normalization source. Publish only health, brand normalization, and category normalization operations to Dify; exclude both reload operations from the inspection tool. Run the service in the Dify internal network under `http://brand-normalize-service:8000`, with Bearer credentials stored only in the server and Dify credential store.

**Tech Stack:** FastAPI, Python 3.11, Docker Compose, OpenAPI 3.0.3, Dify custom tools, pytest

---

## File Map

Service source:

`C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service`

Files created or changed:

- Create: `dify/authorization-inspection-tool.openapi.json` — read-only Dify tool schema.
- Create: `tests/test_authorization_inspection_tool_schema.py` — guards operation exposure and schema compatibility.
- Create: `scripts/validate_dify_tool.py` — health, brand, category and authentication smoke checks.
- Modify: `README.md` — deployment and Dify import handoff.
- Use unchanged: `app/main.py`, `ofs_brand_core/*` — existing matching algorithms.
- Use unchanged: `Dockerfile`, `docker-compose.yml` — container deployment.

The authorization workbench integration is a separate follow-up plan after the Dify tool has a verified URL and credential.

### Task 1: Produce a read-only Dify OpenAPI schema

**Files:**

- Create: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/tests/test_authorization_inspection_tool_schema.py`
- Create: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/dify/authorization-inspection-tool.openapi.json`

- [ ] **Step 1: Write the failing schema test**

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "dify" / "authorization-inspection-tool.openapi.json"


def test_inspection_schema_exposes_only_read_only_operations():
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert document["openapi"] == "3.0.3"
    assert document["servers"][0]["url"] == "http://brand-normalize-service:8000"
    assert set(document["paths"]) == {
        "/health",
        "/api/brand/normalize",
        "/api/category/normalize",
    }
    operation_ids = {
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
    }
    assert operation_ids == {
        "brandServiceHealth",
        "normalizeBrand",
        "normalizeCategory",
    }
    assert "bearerAuth" in document["components"]["securitySchemes"]


def test_normalize_operations_require_expected_arrays():
    document = json.loads(SCHEMA.read_text(encoding="utf-8"))
    brand = document["paths"]["/api/brand/normalize"]["post"]
    category = document["paths"]["/api/category/normalize"]["post"]
    brand_schema = brand["requestBody"]["content"]["application/json"]["schema"]
    category_schema = category["requestBody"]["content"]["application/json"]["schema"]
    assert set(brand_schema["required"]) == {"attachment_values", "source_values"}
    assert set(category_schema["required"]) == {"product_name", "client_category"}
```

- [ ] **Step 2: Run the test and confirm the schema is missing**

Run:

```powershell
python -m pytest tests/test_authorization_inspection_tool_schema.py -q
```

Expected: failure because `dify/authorization-inspection-tool.openapi.json` does not exist.

- [ ] **Step 3: Create the inspection-only schema**

Start from `dify/brand-normalize-tool.openapi.json`, then make these exact changes:

```json
{
  "servers": [
    {
      "url": "http://brand-normalize-service:8000",
      "description": "OFS Dify internal normalization service"
    }
  ]
}
```

Keep only these paths:

```text
/health
/api/brand/normalize
/api/category/normalize
```

Remove:

```text
/api/brand/reload
/api/category/reload
```

Do not change the request or response schemas of the remaining operations.

- [ ] **Step 4: Run the schema tests**

Run:

```powershell
python -m pytest tests/test_authorization_inspection_tool_schema.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Run the existing service tests**

Run in a clean environment without loading the real `.env`:

```powershell
Remove-Item Env:BRAND_API_TOKEN -ErrorAction SilentlyContinue
python -m pytest tests -q
```

Expected: all existing tests and the two schema tests pass.

- [ ] **Step 6: Commit**

```powershell
git add dify/authorization-inspection-tool.openapi.json tests/test_authorization_inspection_tool_schema.py
git commit -m "feat: add read-only Dify inspection tool schema"
```

### Task 2: Add a deployment smoke validator

**Files:**

- Create: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/tests/test_validate_dify_tool.py`
- Create: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/scripts/validate_dify_tool.py`

- [ ] **Step 1: Write the failing validator test**

```python
from scripts.validate_dify_tool import evaluate_results


def test_evaluate_results_accepts_expected_normalization():
    result = evaluate_results(
        health={"status": "ok", "brand_count": 4249, "category_enabled": True},
        brand={
            "success": True,
            "same_brand": True,
            "matched_standard_brand_id": "BRAND_000621",
        },
        category={
            "success": True,
            "category_matched": True,
            "kind3": "陶瓷杯",
        },
        unauthorized_status=401,
    )
    assert result == {
        "status": "ok",
        "checks": {
            "health": True,
            "brand": True,
            "category": True,
            "authentication": True,
        },
    }
```

- [ ] **Step 2: Run the test and confirm the module is missing**

```powershell
python -m pytest tests/test_validate_dify_tool.py -q
```

Expected: failure because `scripts.validate_dify_tool` does not exist.

- [ ] **Step 3: Implement the validator**

Implement:

```python
def evaluate_results(health, brand, category, unauthorized_status):
    checks = {
        "health": health.get("status") == "ok"
        and int(health.get("brand_count", 0)) > 0
        and health.get("category_enabled") is True,
        "brand": brand.get("success") is True
        and brand.get("same_brand") is True
        and bool(brand.get("matched_standard_brand_id")),
        "category": category.get("success") is True
        and category.get("category_matched") is True
        and category.get("kind3") == "陶瓷杯",
        "authentication": unauthorized_status == 401,
    }
    return {
        "status": "ok" if all(checks.values()) else "failed",
        "checks": checks,
    }
```

The command-line entry point must:

1. Read `DIFY_TOOL_BASE_URL` and `BRAND_API_TOKEN` from environment variables.
2. Call `GET /health`.
3. Call brand normalization with `惠普 HP` and `惠普/HP`.
4. Call category normalization with `client_category=["茶杯"]`.
5. Repeat the brand request without a token and require HTTP 401.
6. Print only the summarized result; never print the token or full authorization header.
7. Exit with code 1 when any check fails.

- [ ] **Step 4: Run the validator unit test**

```powershell
python -m pytest tests/test_validate_dify_tool.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add scripts/validate_dify_tool.py tests/test_validate_dify_tool.py
git commit -m "test: add Dify normalization smoke validator"
```

### Task 3: Build and verify the service image locally

**Files:**

- Use: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/Dockerfile`
- Use: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/docker-compose.yml`

- [ ] **Step 1: Verify the brand database exists**

```powershell
$db = 'C:\Users\Lenovo\.workbuddy\skills\brand-matcher\data\matcher.db'
if (-not (Test-Path -LiteralPath $db)) { throw "matcher.db is missing" }
Get-Item -LiteralPath $db | Select-Object FullName,Length
```

Expected: a non-empty `matcher.db`.

- [ ] **Step 2: Verify Docker is available**

```powershell
docker version
docker compose version
```

Expected: both commands succeed.

- [ ] **Step 3: Create the deployment `.env` locally**

Generate a local token and create `.env` without printing the token:

```powershell
$token = python -c "import secrets; print(secrets.token_urlsafe(48))"
$content = Get-Content -LiteralPath '.env.example' -Raw
$content = $content.Replace('change-me-to-a-strong-token', $token)
Set-Content -LiteralPath '.env' -Value $content -Encoding utf8
Remove-Variable token
```

Do not commit `.env`.

- [ ] **Step 4: Build and start**

```powershell
.\manage.ps1 start
```

Expected: service reaches healthy state on port 8000.

- [ ] **Step 5: Run the smoke validator**

```powershell
$env:DIFY_TOOL_BASE_URL = 'http://127.0.0.1:8000'
$env:BRAND_API_TOKEN = (Get-Content .env |
  Where-Object { $_ -match '^BRAND_API_TOKEN=' } |
  Select-Object -First 1).Substring('BRAND_API_TOKEN='.Length)
python scripts/validate_dify_tool.py
```

Expected:

```json
{"status":"ok","checks":{"health":true,"brand":true,"category":true,"authentication":true}}
```

- [ ] **Step 6: Inspect container status without exposing secrets**

```powershell
docker compose ps
docker compose logs --tail 100 brand-normalize
```

Expected: container is healthy and logs do not contain the Bearer token.

### Task 4: Deploy into the OFS Dify network

This task changes an external server and therefore requires explicit confirmation and Dify infrastructure access before execution.

- [ ] **Step 1: Confirm the target deployment model with the Dify administrator**

Required outcome:

```text
Service name: brand-normalize-service
Container port: 8000
Dify-visible URL: http://brand-normalize-service:8000
Persistent read-only brand DB mount: /data/matcher.db
Persistent read-only SCS secret mount: /secrets
```

- [ ] **Step 2: Place the service on the Dify host**

Use the administrator-approved deployment mechanism to place the service at:

```text
/opt/ofs/brand-normalize-service
```

The deployed directory must contain:

```text
app/
ofs_brand_core/
config/fallback_categories.yaml
Dockerfile
docker-compose.yml
requirements.txt
```

- [ ] **Step 3: Create server-side secrets**

Generate the token on the server and create `/opt/ofs/brand-normalize-service/.env`:

```bash
TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
printf '%s\n' \
  "BRAND_API_TOKEN=$TOKEN" \
  'BRAND_DB_PATH=/opt/ofs/data/matcher.db' \
  'SCS_SECRET_DIR=/opt/ofs/secrets' \
  > /opt/ofs/brand-normalize-service/.env
unset TOKEN
chmod 600 /opt/ofs/brand-normalize-service/.env
```

Set file permissions so only the service administrator can read it.

- [ ] **Step 4: Start the service**

From `/opt/ofs/brand-normalize-service`:

```bash
docker compose up -d --build
docker compose ps
```

Expected: `ofs-brand-normalize` is healthy.

- [ ] **Step 5: Verify reachability from a Dify worker container**

Run from the Dify worker container or equivalent internal diagnostic shell:

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://brand-normalize-service:8000/health').status)"
```

Expected: `200`.

- [ ] **Step 6: Run the remote smoke validator**

From a trusted administrator shell:

```bash
export DIFY_TOOL_BASE_URL=http://brand-normalize-service:8000
export BRAND_API_TOKEN="$(sed -n 's/^BRAND_API_TOKEN=//p' /opt/ofs/brand-normalize-service/.env | head -n1)"
python scripts/validate_dify_tool.py
```

Expected: all four checks are true.

### Task 5: Import and verify the Dify custom tool

This task changes the shared Dify workspace and therefore requires explicit confirmation before execution.

- [ ] **Step 1: Open the custom tool page**

In `https://difydev.ofs.cn`:

```text
Tools → Custom → Create Custom Tool → Import OpenAPI Schema
```

- [ ] **Step 2: Import the read-only schema**

Paste:

```text
dify/authorization-inspection-tool.openapi.json
```

Expected operations:

```text
brandServiceHealth
normalizeBrand
normalizeCategory
```

The two reload operations must not appear.

- [ ] **Step 3: Configure authentication**

Set:

```text
Authentication type: API Key
Header: Authorization
Value: Bearer 加服务器 `.env` 中的 `BRAND_API_TOKEN` 实际值
```

Do not paste the token into the OpenAPI schema, workflow prompt, start-node input or output variables.

- [ ] **Step 4: Test the brand operation**

Use:

```json
{
  "task_type": "brand_standardization",
  "authorization_code": "DIFY-ACCEPT-001",
  "authorization_name": "Dify验收",
  "attachment_values": ["惠普 HP"],
  "source_values": ["惠普/HP"],
  "candidate_values": [],
  "requirements": ["分别标准化附件品牌和数据库品牌"]
}
```

Expected:

```text
success=true
same_brand=true
matched_standard_brand_id is not empty
needs_manual_review=false
```

- [ ] **Step 5: Test the category operation**

Use:

```json
{
  "task_type": "category_standardization",
  "authorization_code": "DIFY-ACCEPT-001",
  "authorization_name": "Dify验收",
  "product_name": [],
  "client_category": ["茶杯"],
  "requirements": ["映射到欧菲斯三级品类"]
}
```

Expected:

```text
success=true
category_matched=true
kind3=陶瓷杯
needs_manual_review=false
```

- [ ] **Step 6: Verify fail-closed authentication**

Temporarily test the tool with an incorrect credential in a private test copy.

Expected: HTTP 401 and no normalization data. Restore the correct credential immediately after the test.

### Task 6: Document the verified Dify tool contract

**Files:**

- Modify: `C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/README.md`

- [ ] **Step 1: Add the verified deployment record**

Document:

```text
Dify base: https://difydev.ofs.cn
Internal tool URL: http://brand-normalize-service:8000
Tool operations: brandServiceHealth, normalizeBrand, normalizeCategory
Reload operations: excluded
Authentication: Dify credential store only
```

Do not record the token.

- [ ] **Step 2: Add the workflow mapping**

Document:

```text
brand attachment_values <- merged attachment brand_raw
brand source_values <- source database brand
attachment category client_category <- attachment category_raw
source category client_category <- source database category
```

- [ ] **Step 3: Run the complete service verification**

```powershell
Remove-Item Env:BRAND_API_TOKEN -ErrorAction SilentlyContinue
python -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```powershell
git add README.md
git commit -m "docs: record verified Dify normalization deployment"
```

## Final Acceptance

- [ ] Dify can call service health over its internal network.
- [ ] Only three read-only operations appear in the Dify custom tool.
- [ ] Brand acceptance case resolves to the same standard brand ID.
- [ ] Category acceptance case resolves to `陶瓷杯`.
- [ ] Incorrect credentials return 401.
- [ ] No API token appears in Git, prompts, outputs or logs.
- [ ] Reload operations are unavailable to the inspection workflow.
- [ ] No automatic database writeback is enabled.
