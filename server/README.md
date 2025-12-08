# Artifact Sandbox Server

基于 Cloudflare Workers + Sandbox SDK 的最小示例，提供两个辅助接口：在 Sandbox 容器内运行命令，以及读写文件（包含下载）。

## 先决条件
- Node.js 18+ 与 `npm`
- Wrangler（`npm install -g wrangler`，或使用本地 `npm run dev`）
- Docker（本地重建 Sandbox 容器时需要）

## 安装
```bash
cd artifact_sandbox/server
npm install
```

## 本地开发
Wrangler 会启动 Worker 并构建 `Dockerfile` 指定的 Sandbox 容器，自动创建 Sandbox Durable Object，命令行会输出生成的 Sandbox ID。调用接口时必须携带该 ID。
```bash
npm run dev
# 或
wrangler dev
```

## API 速查
所有请求必须提供 Sandbox ID：请求头 `x-sandbox-id` 或查询参数 `?sandbox_id=<ID>`。

- `POST /run`：执行命令
  ```bash
  curl -X POST "http://127.0.0.1:8787/run?sandbox_id=<ID>" \
    -H "content-type: application/json" \
    -d '{"command":"python3 -c \"print(2+2)\""}'
  ```
  返回 JSON，包含 `output`、`error`、`exitCode`、`success`。

- `GET /run`：演示命令（返回 4），用于连通性检查。

- `PUT /file`：写入文件
  ```bash
  curl -X PUT "http://127.0.0.1:8787/file?sandbox_id=<ID>" \
    -H "content-type: application/json" \
    -d '{"path":"/workspace/hello.txt","content":"hi"}'
  ```

- `GET /file?path=/workspace/hello.txt`：读取文件，追加 `&mode=download` 可下载。
- `DELETE /file?path=/workspace/hello.txt`：删除文件。

异常会返回 4xx 并附带错误信息。

## Docker 镜像
Sandbox 容器基于 `docker.io/cloudflare/sandbox:0.6.0-python`，已包含 `python3`/`pip3`。若需安装额外 Python 依赖，可在 `Dockerfile` 中追加 `pip3 install -r requirements.txt` 后用 Wrangler 重建。

## 部署
- 如调整入口或镜像路径，请同步更新 `wrangler.jsonc`。
- 部署到 Cloudflare：
  ```bash
  npm run deploy
  ```

