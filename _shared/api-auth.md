# REST API 鉴权约定（单一事实源）

> 所有走 REST API 的 skill（powerelf-monitor / powerelf-early-warning / powerelf-chatbi /
> powerelf-inspection 实时监测模式 / powerelf-data-governance 部分 API）共用本约定。
> 各 skill 的 SKILL.md "API 附录" 仅维护**该 skill 专属端点**，鉴权头一律引用本文件。

## 环境变量

| 变量 | 用途 | 示例 |
|------|------|------|
| `POWERELF_API_BASE` | API 基础地址（含 `/admin-api` 前缀） | `http://localhost:48080/admin-api` |
| `POWERELF_API_TOKEN` | Bearer Token（必填，禁止落盘明文） | 由平台签发 |

## 通用请求头

每个请求必须携带：

```
Authorization: Bearer ${POWERELF_API_TOKEN}
tenant-id: 1
```

- `Authorization`：Bearer 鉴权
- `tenant-id`：多租户头（默认租户 `1`，由 `talent.tenant.enable: true` 启用）

## 常见调用模式

```bash
curl "${POWERELF_API_BASE}/monitor/overview/get" \
  -H "Authorization: Bearer ${POWERELF_API_TOKEN}" \
  -H "tenant-id: 1"
```

趋势类端点通用参数：`stId`（测站）、`eqId`（设备）、`startTime`/`endTime`（时间范围）。

## 注意事项

- Token 过期需重新签发；调用返回 401 先检查 Token 是否失效
- 列表/分页端点遵循 `PageResult<T>` 约定（`list` + `total`）
- 统一响应包装 `CommonResult<T>`：`code=0` 为成功
