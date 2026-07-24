# MinerU 精准解析 API 部署说明

## 使用模式

工作台使用 MinerU 精准解析 API 的 URL 单文件异步流程：

1. `POST /api/v4/extract/task` 创建任务；
2. `GET /api/v4/extract/task/{task_id}` 轮询状态；
3. 完成后下载 `full_zip_url`；
4. 从 `*_content_list.json` 读取页面、正文和表格内容；
5. 转换为工作台统一的页码、原文和置信度证据。

固定解析参数：

- `model_version=vlm`
- `is_ocr=true`
- `language=ch`
- `enable_table=true`
- `enable_formula=false`

授权资料不需要公式识别，关闭后可减少无关计算。附件 URL 只允许来自配置的可信域名，结果压缩包只允许从 MinerU 官方 CDN 下载。

## 发布配置

在 MinerU 的 API 管理页面创建 Token。Token 只保存到 ACK Secret：

```text
PARSER_ADAPTER=mineru
MINERU_API_TOKEN=<由发布管理员注入>
MINERU_ALLOWED_SOURCE_HOSTS=supply-auto-project.oss-cn-hangzhou.aliyuncs.com
WRITEBACK_ENABLED=false
```

不得把 Token 写入 `.env.example`、部署清单、日志、截图或 GitHub。

## 验收顺序

1. 使用一份脱敏 PDF 验证任务提交；
2. 确认轮询状态能从 `pending/running` 进入 `done`；
3. 确认结果包包含 `content_list.json`；
4. 确认中文正文、页码和表格内容进入巡检证据；
5. 使用损坏文件验证 `failed` 状态进入人工复核；
6. 使用非白名单 URL 验证请求被本地拒绝；
7. 保持数据库回写关闭。

## 故障处理

- Token 错误或过期：更新 ACK Secret，禁止在日志输出 Token。
- 队列繁忙或服务暂不可用：由任务队列按指数退避重试。
- 文件超过 200 MB 或 200 页：进入人工复核，不自动拆分授权文件。
- MinerU 超时、结果包缺失或解析失败：记录任务号和错误信息，转人工复核。
- MinerU 服务不可用：保留原附件，不生成确定字段，后续可切换本地 PaddleOCR 备用通道。

## 数据安全

精准解析 API 会让 MinerU 服务读取附件 URL。正式启用前，应由业务负责人确认附件允许发送至第三方解析服务，并核对 MinerU 的用户协议和隐私政策。敏感授权书若不允许外发，应改用本地部署的 MinerU 或 PaddleOCR。
