# Dify 品牌与品类标准化工具接入设计

## 目标

将现有 `brand-normalize-service` 作为欧菲斯自部署 Dify 的自定义工具，为授权附件巡检提供确定性的品牌和品类标准化能力。标准化结果保留附件原值、数据库原值、欧菲斯标准值、编码、匹配方式、置信度及人工复核状态。

本设计不修改品牌或品类匹配算法，不允许标准化结果绕过人工确认直接回写线上授权数据库。

## 现有能力

服务规范实现位于：

`C:/Users/Lenovo/WorkBuddy/2026-07-23-18-30-28/brand-normalize-service`

已提供：

- `POST /api/brand/normalize`
- `POST /api/category/normalize`
- `GET /health`
- Bearer Token 鉴权
- Dify OpenAPI 文件 `dify/brand-normalize-tool.openapi.json`
- 品牌与品类独立索引、独立异常边界

## 部署架构

标准化服务部署到 `difydev.ofs.cn` 所在服务器可访问的固定内网地址。优先使用容器服务名或内网域名，不使用 `localhost`，因为 Dify 容器中的 `localhost` 指向 Dify 容器自身。

推荐形式：

```text
http://brand-normalize-service:8000
```

如服务与 Dify 不在同一容器网络，则使用固定内网地址：

```text
http://<内网IP>:8000
```

Dify 自定义工具通过 Bearer Token 调用服务。Token 只保存在 Dify 凭据和服务端环境变量，不进入提示词、前端代码、工作流输出或运行日志。

## Dify 自定义工具

导入 `dify/brand-normalize-tool.openapi.json`，将 `servers[0].url` 替换为实际服务地址。

巡检工作流只使用：

- `normalizeBrand`
- `normalizeCategory`
- `brandServiceHealth`（仅用于诊断）

`reloadBrandLibrary` 与 `reloadCategoryLibrary` 不加入普通巡检工作流，防止巡检任务触发主数据重载。

## 数据流

### 品牌

品牌工具一次接收附件品牌和数据库品牌，分别标准化后比较标准品牌 ID：

```text
附件品牌原文 + 数据库品牌原文
→ normalizeBrand
→ 双侧标准品牌名称/ID
→ same_brand / confidence / needs_manual_review
```

只有双方命中同一标准品牌 ID 时才能认定一致。

### 品类

品类服务负责标准化，不负责附件与数据库的最终一致性判断。因此必须独立调用两次：

```text
附件品类原文 → normalizeCategory → attachment_kind1/2/3
数据库品类原文 → normalizeCategory → source_kind1/2/3
两侧 kind3 比较 → 字段巡检状态
```

附件授权品类放入 `client_category`。当附件同时列出具体商品或型号时，具体商品放入 `product_name`。

不得把附件品类与数据库品类放在同一次请求中一一配对后直接认定一致。

## 巡检状态

- 双侧标准品牌 ID 或品类 `kind3` 一致：`CONSISTENT`
- 数据库为空、附件有明确标准值：`SOURCE_FIELD_MISSING`
- 双侧标准值不同：`SOURCE_FIELD_ERROR`
- 品牌或品类服务要求人工复核：`SKILL_MATCH_UNCERTAIN`
- 附件为具体小类、数据库为全品类：`CATEGORY_SCOPE_OVERSTATED`
- 服务不可达、超时或返回非法结构：`MANUAL_REVIEW_REQUIRED`

## 故障处理

品牌与品类工具节点独立运行、独立捕获错误。任何一个节点失败时：

- 保留另一节点的有效结果；
- 失败字段不得自动修正；
- 保存 HTTP 状态、错误摘要和任务编号；
- 将对应字段转人工复核；
- 不把接口错误误判为附件字段缺失。

## 验收标准

1. Dify 能调用 `/health` 并看到品牌、品类均已启用。
2. `惠普 HP` 与 `惠普/HP` 返回同一标准品牌 ID。
3. `茶杯` 能返回欧菲斯三级品类 `陶瓷杯` 及置信度。
4. 品牌接口失败时，品类结果仍可输出；反向亦然。
5. 低置信度、候选或歧义结果进入人工复核。
6. API Token 不出现在工作流输入、输出和日志正文。
7. 巡检流程不调用品牌库或品类库重载接口。
8. 所有自动建议值保留原始输入、标准值和匹配依据。

