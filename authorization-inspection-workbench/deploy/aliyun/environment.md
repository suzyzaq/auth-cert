# 阿里云运行配置

部署模板面向 ACK、ACR、RDS PostgreSQL、Redis 与 OSS。所有敏感值仅通过
ACK Secret `auth-inspection-runtime` 注入，不得提交到仓库。

Secret 需要由管理员在发布环境配置：

- `DATABASE_URL`
- `REDIS_URL`
- `DINGTALK_CLIENT_ID`
- `DINGTALK_CLIENT_SECRET`
- `OSS_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET`
- `OSS_BUCKET`
- `MODEL_API_KEY`
- `SESSION_SECRET`

上线前保持 `WRITEBACK_ENABLED=false`。完成验收并由管理员确认目标数据库、
权限范围与变更摘要后，才可在发布平台单独开启。

