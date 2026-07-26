# Dify 接入配置 —— 品牌标准化 Skill

两种接入方式，任选其一（推荐方式二：HTTP 请求节点，工作流内可控性最强）。

## 方式一：自定义工具（Agent / 工具调用场景）

1. Dify 控制台 → 工具 → 自定义 → 创建自定义工具
2. Schema 粘贴 `brand-normalize-tool.openapi.json` 全文
3. 把 `servers[0].url` 改为实际部署地址（如 `http://10.x.x.x:8000`）
4. 鉴权方式：`API Key` → Header 名 `Authorization` → 值 `Bearer <BRAND_API_TOKEN>`
5. 测试 `normalizeBrand`，入参示例：
   `attachment_values=["HP"]`, `source_values=["惠普/HP"]`

## 方式二：工作流 HTTP 请求节点（授权审核工作流推荐）

### 节点配置

| 配置项 | 值 |
|---|---|
| 请求方法 | POST |
| URL | `http://YOUR_HOST:8000/api/brand/normalize` |
| Header 1 | `Content-Type: application/json` |
| Header 2 | `Authorization: Bearer {{#env.BRAND_API_TOKEN#}}`（Token 放 Dify 环境变量，勿硬编码） |
| 超时 | 连接 5s / 读取 15s（含 SCS 回退最坏情况） |
| 重试 | 1 次 |

### Body（JSON 模板，替换为你工作流的变量引用）

```json
{
  "task_type": "brand_standardization",
  "authorization_code": "{{#start.authorization_code#}}",
  "authorization_name": "{{#start.authorization_name#}}",
  "attachment_values": {{#attachment_extract.brands#}},
  "source_values": {{#db_query.brands#}},
  "candidate_values": [],
  "requirements": ["附件品牌与数据库品牌分别标准化"]
}
```

> `attachment_values` / `source_values` 兼容：数组、单字符串、JSON 字符串数组、
> 逗号/顿号分隔字符串 —— 上游节点输出是哪种都能吃。

### 输出变量提取（代码节点或直接引用）

HTTP 节点输出 `body` 为 JSON 字符串时，接一个「代码节点」解析：

```python
import json

def main(body: str) -> dict:
    d = json.loads(body)
    return {
        "same_brand": d.get("same_brand", False),
        "needs_manual_review": d.get("needs_manual_review", True),
        "matched_standard_brand": d.get("matched_standard_brand", ""),
        "matched_standard_brand_id": d.get("matched_standard_brand_id", ""),
        "match_type": d.get("match_type", "unmatched"),
        "confidence": d.get("confidence", 0),
        "match_basis": d.get("match_basis", ""),
        "attachment_unmatched": d.get("attachment_unmatched_values", []),
        "scs_hit": any(
            det.get("scs_candidates")
            for det in d.get("attachment_details", []) + d.get("source_details", [])
        ),
    }
```

### 条件分支（IF/ELSE 节点）

```
same_brand == true  AND needs_manual_review == false
    → 品牌一致，审核链路继续（自动通过品牌项）
match_type == "conflict"
    → 品牌冲突，直接判定不一致（附件与数据库命中不同标准品牌）
needs_manual_review == true
    → 转人工复核（写入钉钉AI表格复核队列，带 match_basis + scs_candidates）
```

### 人工复核回流建议（下一阶段）

- `scs_hit == true` 的记录：人工确认后把该品牌沉淀进本地 matcher.db
  （brand-matcher 别名沉淀机制），下次直接本地命中，SCS 依赖越来越少。
- 复核结果回写钉钉 AI 表格 → 定期批量导入品牌主库 → `POST /api/brand/reload` 热生效。

## 快速验通（curl）

```bash
curl -X POST http://YOUR_HOST:8000/api/brand/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <BRAND_API_TOKEN>" \
  -d '{"task_type":"brand_standardization","attachment_values":["HP"],"source_values":["惠普/HP"]}'
# 期望: same_brand=true, matched_standard_brand_id=BRAND_000621
```

---

# 品类标准化节点（与品牌节点完全独立）

> 设计要点：品牌接口与品类接口**分开部署为两个独立 HTTP 节点**。
> 任一节点失败（超时 / 5xx / 网络）只影响自身，不会拖垮另一类结果——
> 满足「避免一个接口失败导致两类标准化结果同时不可用」的硬要求。

## 方式一：自定义工具

在同一个自定义工具里追加 `normalizeCategory` / `reloadCategoryLibrary` 两个 operation
（Schema 已含在 `brand-normalize-tool.openapi.json` v1.2.0），或新建一个独立工具都行。
鉴权复用同一个 `BRAND_API_TOKEN`。

## 方式二：工作流独立 HTTP 节点

### 节点配置

| 配置项 | 值 |
|---|---|
| 请求方法 | POST |
| URL | `http://YOUR_HOST:8000/api/category/normalize` |
| Header 1 | `Content-Type: application/json` |
| Header 2 | `Authorization: Bearer {{#env.BRAND_API_TOKEN#}}` |
| 超时 | 连接 5s / 读取 10s |
| 重试 | 1 次 |

### Body（JSON 模板）

```json
{
  "task_type": "category_standardization",
  "authorization_code": "{{#start.authorization_code#}}",
  "product_name": "{{#attachment_extract.product_name#}}",
  "client_category": "{{#db_query.client_category#}}",
  "requirements": ["附件类目与欧菲斯品类主数据映射"]
}
```

> `product_name` / `client_category` 兼容：数组、单字符串、JSON 字符串数组、
> 逗号/顿号分隔字符串。批量时按首个非空元素一一配对，完整结果在 `details` 数组。

### 输出变量提取（代码节点）

```python
import json

def main(body: str) -> dict:
    d = json.loads(body)
    primary = d  # 主结果即首条配对；批量请遍历 d["details"]
    return {
        "kind1": primary.get("kind1", ""),
        "kind2": primary.get("kind2", ""),
        "kind3": primary.get("kind3", ""),          # 欧菲斯小类，主数据落点
        "category_matched": primary.get("category_matched", False),
        "category_source": primary.get("category_source", ""),
        "category_match_kind": primary.get("category_match_kind", ""),
        "confidence": primary.get("confidence", 0),
        "needs_manual_review": primary.get("needs_manual_review", True),
        "suggestion": primary.get("suggestion", ""),
    }
```

### 条件分支（IF/ELSE 节点）

```
category_matched == true  AND needs_manual_review == false
    → 品类一致，审核链路继续（自动通过品类项）
category_source == "fallback"
    → 命中兜底规则（如 茶杯→陶瓷杯），可自动通过但建议沉淀为正式规则
needs_manual_review == true
    → 转人工复核（写入钉钉AI表格复核队列，带 suggestion）
```

## 快速验通（curl）

```bash
curl -X POST http://YOUR_HOST:8000/api/category/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <BRAND_API_TOKEN>" \
  -d '{"task_type":"category_standardization","client_category":"茶杯"}'
# 期望: kind3=陶瓷杯, category_source=fallback, category_matched=true, confidence=1.0

curl -X POST http://YOUR_HOST:8000/api/category/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <BRAND_API_TOKEN>" \
  -d '{"task_type":"category_standardization","product_name":"热敷肩颈按摩仪","client_category":"健康护理电器"}'
# 期望: kind3=理疗仪 (双源兜底命中)
```
