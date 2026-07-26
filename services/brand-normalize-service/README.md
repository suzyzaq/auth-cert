# OFS 品牌标准化服务 (brand-normalize-service)

将现有 **brand-recognition / brand-matcher** 两个 Skill 的确定性品牌逻辑封装为可被
Dify HTTP 请求节点调用的品牌标准化 API。**不新建品牌逻辑，全部复用欧菲斯品牌主库。**

## 架构与复用关系

```
Dify 授权审核工作流
   │ POST /api/brand/normalize (Bearer Token)
   ▼
FastAPI (app/)                     ←─ 新增
   ▼
ofs_brand_core/ 核心模块            ←─ 新增（确定性逻辑提取层，Skill/CLI/API 共用）
   ├─ normalize.py     ←─ 复用 brand-matcher app/matching/normalize.py (NFKC/comparison_key)
   ├─ matcher.py       ←─ 复用 brand-recognition scripts/retriever.py (黑名单/别名/模糊召回)
   ├─ repository.py    ←─ 只读访问 brand-matcher data/matcher.db
   │                       · brands 表 (active 版本 122,849 行 → 122,393 个标准品牌)
   │                       · brand_alias 正式别名表
   │                       · brand_versions 数据版本
   └─ category_core.py ←─ 复用 brand-matcher app/matching/category.py (品类匹配)
                           · 只读 matcher.db rules 表 (active 版本, kind3_name 非空 → 品类规则)
                           · config/fallback_categories.yaml (兜底规则, 从 brand-matcher 同步)
```

> **品牌与品类两层完全隔离**：`repository.py`/`matcher.py`（品牌）与 `category_core.py`（品类）
> 各自独立的内存索引、独立锁、独立 reload、独立异常边界。一个加载失败不影响另一个，
> 一个接口 5xx 不会拖垮另一类标准化结果（满足「避免一个接口失败导致两类结果同时不可用」）。

原有 Skill 与 CLI 的调用方式**零改动**，本服务只读 matcher.db，不写回。

## 匹配流水线（严格顺序）

1. NFKC 清洗（首尾空格/全角半角）→ 2. comparison_key 大写归一（含 `/` 、括号消除）
→ 3. 精确匹配标准品牌全名 (`exact`) → 4. 匹配登记品牌名 (`normalized`)
→ 5. 匹配正式别名 (`alias`) → 6. 匹配标准名中/英文变体 (`en_cn`)
→ 7. 模糊召回仅作候选 (`fuzzy_candidate`，永不自动确认)
→ 8. **SCS 在线品牌库回退**（本地未命中时查询，仅启用品牌，只作候选 `scs_candidate`）
→ 9. **两侧标准品牌 ID 集合一致才判 same_brand=true**

标准品牌 ID：同一 standard_brand 的多条记录归并，取最小 brand_code，
格式 `BRAND_{code:0>6}`（如 惠普/HP → BRAND_000621），可追溯回欧菲斯品牌编码。

## 启动

```bash
# 本地（Windows）
cd brand-normalize-service
set BRAND_API_TOKEN=your-strong-token
C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Docker
docker build -t ofs-brand-normalize .
docker run -d -p 8000:8000 \
  -e BRAND_API_TOKEN=your-strong-token \
  -v /path/to/matcher.db:/data/matcher.db:ro \
  ofs-brand-normalize
```

环境变量见 `.env.example`：`BRAND_API_TOKEN`（必填，fail-closed）、
`BRAND_DATA_PATH`、`HOST`、`PORT`。

## 端点

| 端点 | 鉴权 | 说明 |
|---|---|---|
| `POST /api/brand/normalize` | Bearer | 品牌标准化 + 同品牌判定 |
| `POST /api/brand/reload` | Bearer | 品牌库热更新（重建内存索引） |
| `POST /api/category/normalize` | Bearer | **品类标准化**（与品牌接口隔离）：(商品名,甲方类目)→欧菲斯三级品类 |
| `POST /api/category/reload` | Bearer | 品类库热更新（重建品类索引） |
| `GET /health` | 无 | `{status, brand_count, alias_count, data_version, scs_enabled, category_enabled, category_rule_count, category_fallback_count, category_data_version}`，不泄露路径 |

## 请求示例

```bash
curl -X POST http://HOST:8000/api/brand/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-strong-token" \
  -d '{"task_type":"brand_standardization","authorization_code":"26060345263220",
       "authorization_name":"惠普/HP授权书","attachment_values":["HP"],
       "source_values":["惠普/HP"],"candidate_values":["HP","惠普/HP"],
       "requirements":["附件品牌与数据库品牌分别标准化"]}'
```

输入兼容：空数组 / 单字符串 / JSON 字符串数组 / 中英文逗号、顿号分隔 / 重复值 /
大小写、空格、斜杠差异 / 多品牌授权。

## 品类标准化接口（独立部署）

将 brand-matcher 的品类匹配逻辑封装为 `POST /api/category/normalize`。输入
`(product_name, client_category)`，输出欧菲斯统一三级品类 `kind1/kind2/kind3`。
与品牌接口**同进程、异端点、互不影响**：独立索引、独立 reload、独立异常边界。

匹配优先级（与 brand-matcher 完全一致）：
`product_name`（关键词/同义词 exact → fuzzy）→ `client_category`（层级 exact → exact/fuzzy）
→ `fallback`（fallback_categories.yaml 兜底规则）→ legacy 评分兜底。

### 请求 / 响应

```jsonc
// 请求
{
  "task_type": "category_standardization",
  "authorization_code": "26060345263220",
  "product_name": "热敷肩颈按摩仪",     // 单串/数组/JSON串/分隔串
  "client_category": "健康护理电器",     // 甲方类目
  "requirements": ["附件类目与欧菲斯品类主数据映射"]
}
// 响应
{
  "success": true, "kind1": "", "kind2": "", "kind3": "理疗仪",
  "category_matched": true, "category_source": "fallback",
  "category_match_kind": "fallback", "confidence": 1.0,
  "matched_term": "健康护理电器 + 热敷肩颈按摩仪",
  "status": "matched", "needs_manual_review": false,
  "details": [ /* 批量时逐条配对明细 */ ]
}
```

### 调用示例

```bash
curl -X POST http://HOST:8000/api/category/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-strong-token" \
  -d '{"task_type":"category_standardization","client_category":"茶杯"}'
# -> kind3=陶瓷杯, category_source=fallback, confidence=1.0

curl -X POST http://HOST:8000/api/category/normalize \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-strong-token" \
  -d '{"task_type":"category_standardization","product_name":"热敷肩颈按摩仪","client_category":"健康护理电器"}'
# -> kind3=理疗仪 (双源兜底命中)
```

> **Dify 接入**：品牌与品类建议做成**两个独立 HTTP 节点**。任一节点失败只影响自身，
> 不会拖垮另一类结果。节点配置 / Body 模板 / 变量提取 / 条件分支见
> `dify/dify-http-node.md`（品类章节）与 `dify/brand-normalize-tool.openapi.json`（v1.2.0）。

### 兜底规则同步

`config/fallback_categories.yaml` 从 `brand-matcher/config/fallback_categories.yaml`
**同步而来**，运行时本地化（不依赖 Skill 内部路径）。brand-matcher 更新兜底规则后，
重新复制该文件即可；服务按 db mtime + 显式 `/api/category/reload` 生效。
当前内置 95 条兜底规则（茶杯→陶瓷杯、墨盒→兼容墨盒、炒锅→锅碗瓢盆及配件等）。


## SCS 在线品牌库回退（本地未命中时）

本地 matcher.db 未命中且非黑名单（型号/规格/单位）时，自动查询 SCS 品牌库
（`https://scs.officemate.cn` `getBrandSapList`，**status=1 仅启用品牌**）。

规则边界：
- SCS 结果**只作候选**（`match_type=scs_candidate`），绝不自动确认同品牌；
- 命中候选时 `needs_manual_review=true`，明细中带 `scs_candidates`
  （`scs_firm_code` / `scs_firm_name` / `scs_status`）；
- SCS 不可用 / Token 过期 / 超时 → 静默降级为本地结果，主流程不受影响（5 分钟熔断）；
- 查询结果内存缓存 1 小时（`SCS_CACHE_TTL`），防止高频穿透。

凭证供给（无会话绑定，每周拉取）：
- Token 文件：`C:/Users/Lenovo/.workbuddy/secrets/scs-token.json`
  （JSON: `Authorization` 完整 Bearer JWT + `X-XSRF-TOKEN`）；
- 每周刷新：`scripts/refresh_scs_token.py` 通过 Kimi WebBridge 复用浏览器
  SCS 登录态抓取最新请求头写入 Token 文件；已配置每周一 09:10 自动化任务
  （刷 Token + 热重载，连续 3 周失败后钉钉告警）；
- 服务按 Token 文件 mtime **自动热加载**，刷新后无需重启；
- JWT 有效期约 7 天，若自动刷新失败需在浏览器重新登录 SCS 后手动跑一次脚本。

环境变量：`SCS_ENABLED`（默认 1）、`SCS_TOKEN_FILE`、`SCS_ENDPOINT`、
`SCS_TIMEOUT`、`SCS_CACHE_TTL`，见 `.env.example`。

## 测试

```bash
python -m pytest tests/ -q          # 69 项单元 + 接口 + SCS 回退测试（品牌 54 + 品类 15）
python tests/smoke_client.py        # 真实服务 7 案例冒烟
python cli.py compare --att "HP,Canon" --src "惠普/HP"   # CLI
```

## 品牌库同步

- brand-matcher 跑 `scripts/import_full_brand_library.py` 更新 matcher.db 后，
  调用 `POST /api/brand/reload`（带 Token）即可热加载，无需重启服务。
- 服务按 db 文件 mtime 校验，reload 幂等安全。
- 别名沉淀：brand_alias 表新转正的正式别名在 reload 后自动生效。

## SCS 候选回流闭环（人工确认 → 写回 matcher.db）

SCS 回退命中结果默认只作候选（`scs_candidate`），需人工确认「确为同品牌」后，
才把该品牌沉淀进本地 matcher.db，使后续请求直接命中本地库、不再每次查询 SCS，
逐步自增长品牌主数据。

### 回写规则
- `standard_brand` 已存在于 `brands` → 写 `brand_alias`（作为已有标准品牌的别名），
  复用其标准品牌 ID（`BRAND_xxxxxx`），不触碰 `brands` 的 `UNIQUE(version_id, brand_code)`；
- `standard_brand` 不存在 / 未填 → 写 `brands` 新建标准品牌，`brand_code` 本地自增生成。

### 操作流程
```bash
# 0) 准备确认清单（人工审核 SCS 候选后产出）
#    字段: firm_code(SCS厂商编码,仅追溯) / firm_name(必填,要识别的品牌名) / standard_brand(可选)
#    示例见 scripts/scs_confirmed_brands.example.json
[
  {"firm_code": 182805, "firm_name": "洁佳人",  "standard_brand": "洁佳人"},
  {"firm_code": 7563,   "firm_name": "惠普企业版", "standard_brand": "惠普/HP"}
]

# 1) 先 dry-run 核对计划（默认不写库）
python scripts/scs_backfill.py --db C:/Users/Lenovo/.workbuddy/skills/brand-matcher/data/matcher.db \
       --input scripts/scs_confirmed_brands.example.json

# 2) 确认无误后写库 + 自动热重载（manage.sh reload 触发容器内 /api/brand/reload）
python scripts/scs_backfill.py --db C:/Users/Lenovo/.workbuddy/skills/brand-matcher/data/matcher.db \
       --input scripts/scs_confirmed_brands.example.json --apply \
       --reload-cmd "bash C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service/manage.sh reload"
```
- 脚本**幂等**：已存在的 `firm_name`（在 `brands` 或 `brand_alias`）自动跳过，重复执行安全；
- 写库后必须 reload 才生效（生产 matcher.db 由 Docker 以 `:ro` 挂载，host 写后靠 mtime 触发 reload）；
- ⚠️ 直接写入生产 matcher.db 属高风险操作，建议先在测试副本上 `--apply` 验证，再对生产执行；
  测试副本可用 `copy matcher.db test.db` 后 `--db test.db` 验证。

### 校验回流结果
```python
from ofs_brand_core.repository import BrandRepository
from ofs_brand_core.normalize import comparison_key
repo = BrandRepository("C:/.../matcher.db"); repo.load()
print(repo.lookup_name(comparison_key("洁佳人")))        # -> {'BRAND_177725'}（新建）
print(repo.lookup_alias(comparison_key("惠普企业版")))    # -> {'BRAND_000621'}（别名映射）
```

### 自动触发（Dify 复核 → 宿主机 Webhook）

把上一步的人工流程升级为闭环：Dify 复核节点确认 SCS 候选后，由「请求」节点
POST 确认清单到**宿主机**常驻的 `backfill_webhook`，自动写库 + 热重载。

> **为什么是宿主机**：容器内 matcher.db 是 `:ro` 只读挂载，不能在容器内写；
> 云端 Dify 也无法直接 exec 宿主机脚本。Webhook 跑在宿主机，写的是宿主机的真实
> matcher.db 路径，写后再调容器内 `/api/brand/reload` 热重载。

**交付物**
- `scripts/backfill_webhook.py`：宿主机常驻 HTTP 接收器（stdlib，无额外依赖）。
  `POST /backfill`（Bearer 鉴权，复用 `BRAND_API_TOKEN`）→ 调 `scs_backfill.py --apply`
  → 调容器 `/api/brand/reload`；`GET /health` 免鉴权。每次调用落盘留痕 `.scs_backfill_log/`。
- `dify/brand-backfill-dify.md`：Dify 复核工作流节点设计（6 节点 + 字段映射 + 触发约束）。
- `dify/scs-confirm.schema.json`：确认清单 JSON Schema（与 `scs_backfill.py` 输入严格对齐）。
- `dify/brand-backfill-flow.html`：单文件交互式闭环视图（节点/字段映射/API/约束，可搜索折叠复制）。

**宿主启动**
```bash
cd brand-normalize-service
# 默认 127.0.0.1:8900（仅本机）；云端 Dify 需 --host 0.0.0.0 + 内网穿透
python scripts/backfill_webhook.py
# 显式指定（DB 取 .env 的 BRAND_DB_PATH / Token 取 BRAND_API_TOKEN）
python scripts/backfill_webhook.py --host 0.0.0.0 --port 8900 \
  --db C:/Users/Lenovo/.workbuddy/skills/brand-matcher/data/matcher.db \
  --token <BRAND_API_TOKEN>
```

**Dify 调用**
```
POST http://<宿主机>:8900/backfill
Authorization: Bearer <BRAND_API_TOKEN>
Content-Type: application/json
Body: [{"firm_code":182805,"firm_name":"洁佳人","standard_brand":"洁佳人"},
       {"firm_code":7563,"firm_name":"惠普企业版","standard_brand":"惠普/HP"}]
# 或 {"items":[...],"dry_run":false,"reload":true}
```
响应：`{"ok":true,"applied":2,"skipped":0,"reload_done":true,"reload_ok":true,...}`

**约束**：写库在宿主机（绕开 `:ro`）；云端 Dify 需穿透/同网才能访问 `:8900`；
Webhook 默认仅监听 `127.0.0.1`，暴露公网务必在穿透层加来源/二次鉴权。
**备选**：若不想暴露端口，可走钉钉 AI 表格中转（Dify 写「SCS回流待处理」表 → 宿主机 WorkBuddy 定时轮询 → backfill → 回写状态）。

