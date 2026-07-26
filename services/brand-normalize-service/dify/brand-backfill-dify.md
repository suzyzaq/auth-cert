# SCS 候选回流 · Dify 复核闭环

把 `POST /api/brand/normalize` 返回的 **SCS 候选**（`match_type=scs_candidate`、
`needs_manual_review=true`）经 Dify 人工复核确认后，自动回流写回本地 matcher.db，
使后续请求直接命中本地库、不再每次查 SCS，逐步沉淀品牌主数据。

## 整体闭环

```
Dify 复核工作流
   │ ① HTTP 请求: POST /api/brand/normalize (Bearer)
   ▼
   │ ② 代码节点/IF: needs_manual_review==true && match_type==scs_candidate
   ▼
   │ ③ 人工复核节点: 确认「确为同品牌」+ 指定 standard_brand
   ▼
   │ ④ 代码节点: 拼装确认清单 (对齐 scs-confirm.schema.json)
   ▼
   │ ⑤ HTTP 请求: POST http://<宿主机>:8900/backfill (Bearer)
   ▼
宿主机 backfill_webhook (scripts/backfill_webhook.py, 常驻)
   │ ⑥ 调 scripts/scs_backfill.py --apply  (写宿主机 matcher.db, 可写)
   │ ⑦ 调容器 /api/brand/reload              (热重载内存索引)
   ▼
返回 {applied, skipped, reload_ok} → Dify ⑥结束/钉钉记录
```

## 触发约束（关键）

- **写库必须在宿主机**：容器内 matcher.db 是 `:ro` 只读挂载，不能在容器内写。
  `backfill_webhook` 跑在**宿主机**，写的是宿主机的真实 matcher.db 路径。
- **云端 Dify 无法直接 exec 宿主机脚本**：必须让 Dify 能访问宿主机 `8900` 端口：
  - 同内网/私有化 Dify → 用宿主机内网 IP:8900；
  - 云端 Dify → 需内网穿透（frp / ngrok / Cloudflare Tunnel）把 8900 暴露出去；
  - Dify 也跑在 Docker（同宿主机）→ `http://host.docker.internal:8900`。
- **鉴权**：webhook 用 `Bearer <BRAND_API_TOKEN>`（与 normalize 同一 Token）。
- **安全**：webhook 默认只监听 `127.0.0.1`；暴露到公网时务必在穿透层加来源限制/二次鉴权。

## Dify 节点设计

| # | 节点 | 类型 | 配置要点 |
|---|---|---|---|
| ① | 品牌标准化 | HTTP 请求 | `POST http://<host>:8000/api/brand/normalize`；Header `Authorization: Bearer <token>`；Body 含 `attachment_values`/`source_values` |
| ② | 是否 SCS 候选 | 代码/IF 分支 | 取响应 `needs_manual_review` 与 `match_type`；为候选 → 走人工复核，否则直接出结论 |
| ③ | 人工复核确认 | 人工复核/表单 | 展示 `attachment_details[].scs_candidates`（firm_code/firm_name）；确认是否同品牌 + 填 `standard_brand` |
| ④ | 拼装确认清单 | 代码节点 | 把确认结果转成 `[{firm_code, firm_name, standard_brand}]`，对齐 `scs-confirm.schema.json` |
| ⑤ | 触发回流 | HTTP 请求 | `POST http://<host>:8900/backfill`；Header `Authorization: Bearer <token>`；Body = 确认清单（数组，或 `{"items":[...],"dry_run":false,"reload":true}`） |
| ⑥ | 回流结果 | 结束/钉钉 | 读取响应 `applied`/`skipped`/`reload_ok`；失败则钉钉告警 |

## 字段映射（normalize 输出 → 确认清单）

| normalize 响应字段 | 确认清单字段 | 说明 |
|---|---|---|
| `attachment_details[].scs_candidates[].scs_firm_code` | `firm_code` | SCS 厂商编码，仅追溯 |
| `attachment_details[].scs_candidates[].scs_firm_name` | `firm_name` | 必填，要回流的品牌名 |
| （人工复核指定） | `standard_brand` | 可选；映射到已有标准品牌或新建 |

## 确认清单 Body 示例

```json
[
  {"firm_code": 182805, "firm_name": "洁佳人",   "standard_brand": "洁佳人"},
  {"firm_code": 7563,   "firm_name": "惠普企业版", "standard_brand": "惠普/HP"}
]
```
或直接数组；也支持包一层 `{"items":[...],"dry_run":false,"reload":true}`。

## webhook 响应

```json
{
  "ok": true,
  "applied": 2,
  "skipped": 0,
  "dry_run": false,
  "reload_done": true,
  "reload_ok": true,
  "log_file": ".../.scs_backfill_log/backfill-20260726-220133.json",
  "detail": "[APPLIED] 已写入 2 条，跳过 0 条。"
}
```

## 宿主机启动 webhook

```bash
cd brand-normalize-service
# 默认 127.0.0.1:8900（仅本机）；Dify 云端访问需 --host 0.0.0.0 + 穿透
python scripts/backfill_webhook.py
# 或显式指定
python scripts/backfill_webhook.py --host 0.0.0.0 --port 8900 \
  --db C:/Users/Lenovo/.workbuddy/skills/brand-matcher/data/matcher.db \
  --token <BRAND_API_TOKEN>
```
- 每次调用落盘留痕：`.scs_backfill_log/backfill-<ts>.json`（入参 + 结果），便于追溯。
- `dry_run:true` 只返回计划不写库，适合先验证 Dify→webhook 链路。

## 备选触发（钉钉 AI 表格中转）

若不想暴露宿主机端口，可走用户默认技术路线：Dify 复核确认后把记录写入
**钉钉 AI 表格·SCS回流待处理**（字段：firm_code/firm_name/standard_brand/审核单号/status），
再由**宿主机 WorkBuddy 定时轮询**该表 → 生成 JSON → 跑 `scs_backfill.py --apply` → reload →
回写 `status=已回流`。该路径本机可达性无忧，适合生产长期运行。
