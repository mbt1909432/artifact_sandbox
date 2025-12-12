# Sandbox Server API 文档

## 概述

Sandbox Server 是一个基于 Cloudflare Workers 和 Sandbox SDK 的 HTTP API 服务，提供沙箱容器的生命周期管理、会话管理、命令执行和文件操作功能。

## 架构

- **运行时**: Cloudflare Workers (Edge Runtime)
- **持久化**: Durable Objects (Sandbox 实例)
- **容器**: Docker 容器（基于 `cloudflare/sandbox` 镜像）
- **协议**: HTTP REST API

## 认证与标识

所有请求（除了 `/sandbox` 的 POST 创建操作）都需要提供 Sandbox ID，可以通过以下方式之一：

1. **请求头**: `x-sandbox-id: <sandbox-id>`
2. **查询参数**: `?sandbox_id=<sandbox-id>`

如果未提供 Sandbox ID，将返回 `400 Bad Request`。

---

## API 端点

### 1. Sandbox 生命周期管理

#### 1.1 创建 Sandbox

**端点**: `POST /sandbox`

**描述**: 创建或获取一个 Sandbox 实例。如果提供了 `sandboxId`，将使用该 ID；否则自动生成 UUID。

**请求参数**:

- **查询参数** (可选):
  - `sandbox_id`: 指定的 Sandbox ID

- **请求体** (JSON, 可选):
  ```json
  {
    "sandboxId": "string",  // 或 "id"
    "options": {
      "sleepAfter": "string",           // 容器空闲后休眠时间
      "keepAlive": boolean,             // 是否保持容器存活
      "normalizeId": boolean,           // 是否规范化 ID
      "containerTimeouts": {            // 容器超时配置
        "start": number,
        "stop": number
      }
    }
  }
  ```

**响应** (200 OK):
```json
{
  "sandboxId": "uuid-string",
  "created": true,
  "options": { ... }
}
```

**示例**:
```bash
# 自动生成 ID
curl -X POST "http://localhost:8787/sandbox" \
  -H "Content-Type: application/json"

# 指定 ID
curl -X POST "http://localhost:8787/sandbox" \
  -H "Content-Type: application/json" \
  -d '{"sandboxId": "my-sandbox-123"}'
```


curl -X POST "https://server.435669237.workers.dev" \
  -H "Content-Type: application/json" \
  -d '{"sandboxId": "my-sandbox-123"}'
这个请求不行 {"error":"Missing sandbox id. Provide x-sandbox-id header or ?sandbox_id="}

这个可以
curl -X POST "https://server.435669237.workers.dev" \
  -H "Content-Type: application/json" \
  -H "x-sandbox-id: my-sandbox-123" \
  -d '{"sandboxId": "my-sandbox-123"}'


#### 1.2 销毁 Sandbox

**端点**: `DELETE /sandbox`

**描述**: 销毁指定的 Sandbox 实例及其所有资源。根据 [Cloudflare Sandbox SDK 文档](https://developers.cloudflare.com/sandbox/api/lifecycle/)，`destroy()` 方法可以安全地多次调用，即使 Sandbox 已经不存在也不会抛出错误。

**Sandbox ID 来源** (按优先级):
1. 请求体中的 `sandboxId` 或 `id`
2. 查询参数 `?sandbox_id=`
3. 请求头 `x-sandbox-id`

**请求体** (JSON, 可选):
```json
{
  "sandboxId": "string",  // 或 "id"
}
```

**响应** (200 OK):
```json
{
  "sandboxId": "uuid-string",
  "destroyed": true,
  "existed": true  // 指示 Sandbox 在销毁前是否存在
}
```

**响应字段说明**:
- `sandboxId`: 用户传入的 Sandbox ID（来自请求体、查询参数或请求头），用于确认请求的 Sandbox
- `destroyed`: 始终为 `true`（表示销毁操作已执行）
- `existed`: `boolean`，指示 Sandbox 在销毁前是否存在
  - `true`: Sandbox 存在且已成功销毁
  - `false`: Sandbox 不存在或已被销毁（但销毁操作仍会执行，不会报错）

**错误响应** (404):
当检测到 Sandbox 不存在时：
```json
{
  "sandboxId": "uuid-string",  // 用户传入的 sandboxId（用于确认请求的 Sandbox）
  "destroyed": false,
  "existed": false,
  "error": "Sandbox not found or already destroyed"
}
```

**注意**: 响应中的 `sandboxId` 就是用户传入的值（来自请求体、查询参数或请求头），用于确认请求的是哪个 Sandbox。

**检测 Sandbox 是否存在**:

API 会自动检测 Sandbox 是否存在：
1. 在销毁前，会尝试执行一个轻量级命令（`echo -n`）来检测容器是否可访问
2. 如果命令成功，说明 Sandbox 存在
3. 如果命令失败且错误信息表明容器不存在，则 `existed` 为 `false`
4. 无论 Sandbox 是否存在，`destroy()` 都会安全执行

**示例**:
```bash
# 销毁存在的 Sandbox
curl -X DELETE "http://localhost:8787/sandbox?sandbox_id=my-sandbox-123"
# 响应: { "sandboxId": "my-sandbox-123", "destroyed": true, "existed": true }

# 销毁不存在的 Sandbox（不会报错）
curl -X DELETE "http://localhost:8787/sandbox?sandbox_id=non-existent-id"
# 响应: { "sandboxId": "non-existent-id", "destroyed": true, "existed": false }
```

curl -X DELETE "https://server.435669237.workers.dev/sandbox?sandbox_id=my-sandbox-123"

执行删除沙箱两次仍然报ok？？但实际不存在了？？？？

**注意事项**:
- `destroy()` 方法可以安全地多次调用，即使 Sandbox 已经不存在
- 根据 Cloudflare 文档，销毁操作会立即终止容器并永久删除所有状态（文件、进程、会话等）
- `existed` 字段可以帮助区分"成功销毁"和"Sandbox 本来就不存在"两种情况

---

### 2. Session 管理

Session 用于隔离执行环境，每个 Session 拥有独立的工作目录和环境变量。

#### 2.1 创建 Session

**端点**: `POST /session`

**描述**: 在指定的 Sandbox 中创建一个新的执行会话。如果 Session ID 已存在，将返回现有 Session 信息。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "id": "session-id",           // 可选，不提供则自动生成
  "env": {                      // 可选，环境变量
    "KEY": "value"
  },
  "cwd": "/workspace/project"   // 可选，工作目录
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "sessionId": "session-id",
  "timestamp": "2024-01-01T00:00:00.000Z",
  "message": "Session 'session-id' already exists"  // 仅当 Session 已存在时
}
```

**错误响应**:

根据不同错误类型返回不同的状态码：

**400 Bad Request** - 请求参数错误：
```json
{
  "error": "Invalid request parameters"
}
```
例如：`cwd` 路径格式错误（不以 `/` 开头）、`env` 格式不正确等。

**404 Not Found** - Sandbox 不存在或未初始化：
```json
{
  "error": "Sandbox not found or not initialized"
}
```

**500 Internal Server Error** - 服务器内部错误：
```json
{
  "error": "Failed to create session"
}
```
仅在发生不可预期的服务器错误时返回。

**示例**:
```bash
curl -X POST "http://localhost:8787/session" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-session",
    "env": {"PYTHONPATH": "/workspace"},
    "cwd": "/workspace/project"
  }'
```

#### 2.2 获取 Session

**端点**: `GET /session`

**描述**: 获取指定 Session 的信息。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**查询参数**:
- `id` 或 `sessionId`: Session ID (必需)

**响应** (200 OK):
```json
{
  "success": true,
  "sessionId": "session-id",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

**错误响应** (404):
```json
{
  "error": "Session not found"
}
```

**示例**:
```bash
curl "http://localhost:8787/session?id=my-session" \
  -H "x-sandbox-id: my-sandbox-123"
```

#### 2.3 删除 Session

**端点**: `DELETE /session`

**描述**: 删除指定的 Session。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**Session ID 来源** (按优先级):
1. 请求体中的 `sessionId`
2. 查询参数 `?id=` 或 `?sessionId=`

**请求体** (JSON, 可选):
```json
{
  "sessionId": "session-id"
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "sessionId": "session-id",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

**重要说明**:
- `DELETE /session` 仅删除会话的执行状态（环境变量、工作目录指针、进程等），不会清理该会话期间写入的文件或目录。再次 `createSession`/`getSession` 同名 ID 会重新创建/返回会话，之前的文件仍在，容易让人误以为会话“还存在”。
- 如需彻底清理文件，请主动删除路径，例如 `DELETE /file?path=/workspace/prod` 或对应的 SDK 方法 `sandbox.delete("/workspace/prod")`。
- 如需清空整个 Sandbox（包含所有会话和文件），请调用生命周期接口 `DELETE /sandbox`（对应 SDK 的 `destroy_sandbox()`），而不仅是删除会话。
- 默认 Session 不能删除，行为与 Cloudflare 官方文档一致，参考 Cloudflare Sandbox Sessions 文档：https://developers.cloudflare.com/sandbox/api/sessions/
- 同一 Sandbox 内各 Session 共享同一份容器文件系统（如 `/workspace`），差异仅在会话的 shell 状态（env/cwd/进程）。指定 `cwd` 仅影响相对路径解析，实际文件仍写入共享 FS；因此清理文件需要显式删除或销毁 Sandbox。

**错误响应**:

根据不同错误类型返回不同的状态码：

**400 Bad Request** - 请求参数错误：
```json
{
  "error": "Invalid request parameters"
}
```
例如：`sessionId` 格式错误、参数验证失败等。

**404 Not Found** - Session 或 Sandbox 不存在：
```json
{
  "error": "Session or sandbox not found"
}
```

**500 Internal Server Error** - 服务器内部错误：
```json
{
  "error": "Failed to delete session"
}
```
仅在发生不可预期的服务器错误时返回。

**示例**:
```bash
curl -X DELETE "http://localhost:8787/session?id=my-session" \
  -H "x-sandbox-id: my-sandbox-123"
```

---

### 3. 命令执行

#### 3.1 执行命令

**端点**: `POST /run`

**描述**: 在 Sandbox 中执行命令。可以指定 Session ID 以在特定会话中执行。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "command": "python3 -c \"print(2+2)\"",
  "sessionId": "session-id"  // 可选：指定 Session ID。如果不提供，将在默认 Session 中执行
}
```

**字段说明**:
- `command` (必需): 要执行的命令字符串
- `sessionId` (可选): Session ID。如果提供，命令将在指定的 Session 中执行；如果不提供，命令将在默认 Session 中执行

**响应** (200 OK):
```json
{
  "output": "4\n",
  "error": "",
  "exitCode": 0,
  "success": true
}
```

**示例**:
```bash
# 在默认 Session 中执行
curl -X POST "http://localhost:8787/run" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{"command": "python3 -c \"print(2+2)\""}'

# 在指定 Session 中执行
curl -X POST "http://localhost:8787/run" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "pwd",
    "sessionId": "my-session"
  }'
```

#### 3.2 演示命令 (GET)

**端点**: `GET /run`

**描述**: 执行演示命令 `python3 -c "print(2 + 2)"`，用于连通性检查。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**查询参数**:
- `sessionId`: 可选，指定 Session

**响应**: 同 `POST /run`

**示例**:
```bash
curl "http://localhost:8787/run?sandbox_id=my-sandbox-123"
```

#### 3.3 执行脚本

**端点**: `POST /run-script`

**描述**: 将脚本内容写入文件并执行。支持多种解释器（Python、Bash、Node.js 等）。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "script": "print('Hello, World!')",
  "interpreter": "python3",           // 可选，默认 "python3"
  "path": "/workspace/script.py",     // 可选，不提供则自动生成临时路径
  "sessionId": "session-id"           // 可选，指定 Session
}
```

**支持的解释器**:
- `python3` / `python`
- `bash` / `sh`
- `node` / `nodejs`
- 其他任意解释器命令

**响应** (200 OK):
```json
{
  "output": "Hello, World!\n",
  "error": "",
  "exitCode": 0,
  "success": true,
  "scriptPath": "/workspace/script-xxx.py",
  "interpreter": "python3"
}
```

**注意**: 如果未提供 `path`，脚本将写入临时文件，执行后自动删除。

**示例**:
```bash
curl -X POST "http://localhost:8787/run-script" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{
    "script": "print(\"Hello, World!\")",
    "interpreter": "python3",
    "sessionId": "my-session"
  }'
```

---

### 4. 文件操作

> 文件 API 作用于同一 Sandbox 的共享文件系统（如 `/workspace`）。传入 `sessionId` 仅用于复用该 Session 的 cwd/env（相对路径解析、环境变量），并不会提供文件级隔离；如需清理文件请显式删除或销毁整个 Sandbox。

#### 4.1 写入文件

**端点**: `PUT /file`

**描述**: 在 Sandbox 中创建或覆盖文件。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "path": "/workspace/file.txt",
  "content": "file content",
  "sessionId": "session-id"  // 可选，指定 Session
}
```

**路径规则**:
- 必须以 `/` 开头
- 自动规范化（去除多余斜杠）
- 相对路径会自动添加前导 `/`

**响应** (200 OK):
```json
{
  "path": "/workspace/file.txt",
  "length": 11
}
```

**错误响应**:
- `400`: 缺少 `path` 参数
- `500`: 写入失败（可能包含 `httpStatus` 字段）

**示例**:
```bash
curl -X PUT "http://localhost:8787/file" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/workspace/hello.txt",
    "content": "Hello, World!"
  }'
```

#### 4.2 读取文件

**端点**: `GET /file`

**描述**: 读取文件内容。可以下载文件或返回 JSON。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**查询参数**:
- `path`: 文件路径 (可选，不提供则返回演示文件)
- `sessionId`: 可选，指定 Session
- `mode`: 可选，设置为 `download` 时下载文件

**响应** (200 OK):

JSON 模式:
```json
{
  "path": "/workspace/file.txt",
  "content": "file content"
}
```

下载模式 (`mode=download`):
- Content-Type: `text/plain; charset=utf-8`
- Content-Disposition: `attachment; filename="file.txt"`
- 响应体: 文件内容

**错误响应** (404):
```json
{
  "error": "File not found: /workspace/file.txt"
}
```

**示例**:
```bash
# 读取文件 (JSON)
curl "http://localhost:8787/file?path=/workspace/hello.txt" \
  -H "x-sandbox-id: my-sandbox-123"

# 下载文件
curl "http://localhost:8787/file?path=/workspace/hello.txt&mode=download" \
  -H "x-sandbox-id: my-sandbox-123" \
  -o hello.txt
```

#### 4.3 删除文件

**端点**: `DELETE /file`

**描述**: 删除指定文件。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**查询参数**:
- `path`: 文件路径 (必需)
- `sessionId`: 可选，指定 Session

**响应** (200 OK):
```json
{
  "path": "/workspace/file.txt",
  "deleted": true
}
```

**错误响应** (404):
```json
{
  "error": "File not found: /workspace/file.txt"
}
```

**示例**:
```bash
curl -X DELETE "http://localhost:8787/file?path=/workspace/hello.txt" \
  -H "x-sandbox-id: my-sandbox-123"
```

---

#### 4.4 创建目录

**端点**: `POST /mkdir`

**描述**: 创建目录，支持递归创建父级目录。支持 Session 隔离。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "path": "/workspace/data",
  "recursive": true,
  "sessionId": "session-id"  // 可选，指定 Session
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "path": "/workspace/data",
  "recursive": true
}
```

**错误响应**:
- `400`: 路径无效等参数错误
- `404`: Sandbox 或 Session 不存在
- `500`: 服务器内部错误

---

#### 4.5 判断文件/目录是否存在

**端点**: `GET /exists`

**描述**: 判断文件或目录是否存在。支持 Session 隔离。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**查询参数**:
- `path`: 目标路径 (必需)
- `sessionId`: 可选，指定 Session

**响应** (200 OK):
```json
{
  "exists": true
}
```

**错误响应**:
- `400`: 缺少 `path` 或参数错误
- `404`: Sandbox 或 Session 不存在
- `500`: 服务器内部错误

---

#### 4.6 重命名文件

**端点**: `POST /rename`

**描述**: 重命名文件或目录。支持 Session 隔离。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "oldPath": "/workspace/a.txt",
  "newPath": "/workspace/b.txt",
  "sessionId": "session-id"  // 可选，指定 Session
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "from": "/workspace/a.txt",
  "to": "/workspace/b.txt"
}
```

**错误响应**:
- `400`: 参数错误
- `404`: 文件、Sandbox 或 Session 不存在
- `500`: 服务器内部错误

---

#### 4.7 移动文件

**端点**: `POST /move`

**描述**: 移动文件或目录到新的路径。支持 Session 隔离。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "sourcePath": "/workspace/a.txt",
  "destinationPath": "/workspace/archive/a.txt",
  "sessionId": "session-id"  // 可选，指定 Session
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "from": "/workspace/a.txt",
  "to": "/workspace/archive/a.txt"
}
```

**错误响应**:
- `400`: 参数错误
- `404`: 文件、Sandbox 或 Session 不存在
- `500`: 服务器内部错误

> 以上文件能力对应 Cloudflare Sandbox Files API，详见官方文档：https://developers.cloudflare.com/sandbox/api/files/

---

### 5. 存储挂载（R2/S3 兼容）

> 仅生产环境可用；`wrangler dev` 不支持 FUSE 挂载。参考官方文档 [Storage · Cloudflare Sandbox SDK docs](https://developers.cloudflare.com/sandbox/api/storage/)。

#### 5.1 挂载 Bucket

**端点**: `POST /mount-bucket`

**描述**: 将 S3 兼容存储桶挂载到 Sandbox 文件系统；挂载对同一 Sandbox 的所有 Session 可见。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**请求体** (JSON):
```json
{
  "bucket": "my-r2-bucket",
  "mountPath": "/data",
  "options": {
    "endpoint": "https://<ACCOUNT>.r2.cloudflarestorage.com",  // 必填
    "provider": "r2",                // 可选: r2|s3|gcs
    "credentials": {                 // 可选，未提供则自动从环境变量检测
      "accessKeyId": "AKIA...",
      "secretAccessKey": "..."
    },
    "readOnly": false,               // 可选
    "s3fsOptions": { "use_cache": "/tmp/cache" } // 可选
  },
  "sessionId": "session-id"          // 可选：在指定 session 上挂载
}
```

**响应** (200 OK):
```json
{
  "success": true,
  "bucket": "my-r2-bucket",
  "mountPath": "/data",
  "options": { "endpoint": "..." }
}
```

**错误响应**:
- `400`: 缺少必需参数或配置错误（如缺少 `options.endpoint` / 凭证无效）
- `404`: Sandbox 或 Session 不存在
- `500`: 挂载失败（网络/权限/存储端错误）

**示例**:
```bash
curl -X POST "http://localhost:8787/mount-bucket" \
  -H "x-sandbox-id: my-sandbox-123" \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "my-r2-bucket",
    "mountPath": "/data",
    "options": {
      "endpoint": "https://<ACCOUNT>.r2.cloudflarestorage.com",
      "readOnly": false
    }
  }'
```

#### 5.2 卸载 Bucket

**端点**: `DELETE /unmount-bucket`

**描述**: 卸载指定挂载路径。

**请求头**:
- `x-sandbox-id`: Sandbox ID (必需)

**参数**:
- `mountPath` (必需): 可在 body 传 `{ "mountPath": "/data" }` 或查询参数 `?mountPath=/data`
- `sessionId` (可选): 指定 Session 卸载

**响应** (200 OK):
```json
{
  "success": true,
  "mountPath": "/data"
}
```

**错误响应**:
- `400`: 缺少 mountPath 或参数格式错误
- `404`: Sandbox / Session 不存在
- `500`: 卸载失败

**示例**:
```bash
curl -X DELETE "http://localhost:8787/unmount-bucket?mountPath=/data" \
  -H "x-sandbox-id: my-sandbox-123"
```

---

## 错误处理

### HTTP 状态码

- `200 OK`: 请求成功
- `400 Bad Request`: 请求参数错误（缺少必需参数、格式错误等）
- `404 Not Found`: 资源不存在（Session、文件等）
- `405 Method Not Allowed`: HTTP 方法不支持
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式

```json
{
  "error": "Error message description"
}
```

### 常见错误

1. **缺少 Sandbox ID**:
   ```json
   {
     "error": "Missing sandbox id. Provide x-sandbox-id header or ?sandbox_id="
   }
   ```

2. **缺少必需参数**:
   ```json
   {
     "error": "POST /run expects JSON body { \"command\": \"...\" }"
   }
   ```

3. **资源不存在**:
   ```json
   {
     "error": "Session not found"
   }
   ```

---

## 使用流程示例

### 完整工作流

```bash
# 1. 创建 Sandbox
SANDBOX_ID=$(curl -X POST "http://localhost:8787/sandbox" \
  -H "Content-Type: application/json" | jq -r '.sandboxId')

# 2. 创建 Session
SESSION_ID=$(curl -X POST "http://localhost:8787/session" \
  -H "x-sandbox-id: $SANDBOX_ID" \
  -H "Content-Type: application/json" \
  -d '{"id": "my-session", "cwd": "/workspace/project"}' \
  | jq -r '.sessionId')

# 3. 写入文件
curl -X PUT "http://localhost:8787/file" \
  -H "x-sandbox-id: $SANDBOX_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"path\": \"/workspace/project/main.py\",
    \"content\": \"print('Hello, World!')\",
    \"sessionId\": \"$SESSION_ID\"
  }"

# 4. 执行脚本
curl -X POST "http://localhost:8787/run-script" \
  -H "x-sandbox-id: $SANDBOX_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"script\": \"print('Hello, World!')\",
    \"interpreter\": \"python3\",
    \"sessionId\": \"$SESSION_ID\"
  }"

# 5. 读取结果
curl "http://localhost:8787/file?path=/workspace/project/main.py" \
  -H "x-sandbox-id: $SANDBOX_ID" \
  | jq -r '.content'

# 6. 清理资源
curl -X DELETE "http://localhost:8787/session?id=$SESSION_ID" \
  -H "x-sandbox-id: $SANDBOX_ID"

curl -X DELETE "http://localhost:8787/sandbox?sandbox_id=$SANDBOX_ID"
```

---

## 注意事项

### Session 隔离

- 每个 Session 拥有独立的工作目录 (`cwd`) 和环境变量 (`env`)
- 文件操作在指定 Session 中执行时，路径相对于 Session 的工作目录，但底层文件系统在同一 Sandbox 内是共享的

### 路径规范

- 所有路径必须以 `/` 开头
- 相对路径会自动转换为绝对路径
- 多余的斜杠会被规范化（`//` → `/`）

### 临时文件

- `/run-script` 端点如果未提供 `path`，会创建临时文件（格式: `/workspace/script-{uuid}.py`）
- 临时文件在执行后会自动删除
- 如果提供了 `path`，文件不会被自动删除

### Sandbox ID 传递

- 除了创建 Sandbox (`POST /sandbox`) 外，所有请求都需要 Sandbox ID
- 优先使用请求头 `x-sandbox-id`，查询参数 `?sandbox_id=` 作为备选
- 未提供 Sandbox ID 将返回 `400 Bad Request`

### 错误处理

- 文件不存在时会返回 `404 Not Found`
- Session 不存在时，`GET /session` 可能返回 `404`（取决于底层实现）
- 所有错误响应都包含 `error` 字段

### 性能考虑

- Sandbox 实例是 Durable Objects，具有持久化状态
- 容器启动可能需要几秒钟
- 使用 `keepAlive` 选项可以保持容器运行，避免重复启动

---

## 开发与部署

### 本地开发

```bash
cd artifact_sandbox/server
npm install
npm run dev
```

### 部署到 Cloudflare

```bash
npm run deploy
```

### 配置

编辑 `wrangler.jsonc` 以调整 Worker 配置和 Docker 镜像设置。

---

## 版本信息

- **SDK**: `@cloudflare/sandbox`
- **运行时**: Cloudflare Workers
- **容器镜像**: `docker.io/cloudflare/sandbox:0.6.0-python`

---

## 相关文档

- [Sandbox SDK 文档](../packages/sandbox/README.md)
- [Cloudflare Workers 文档](https://developers.cloudflare.com/workers/)
- [Durable Objects 文档](https://developers.cloudflare.com/durable-objects/)

