import { getSandbox, type Sandbox, type SandboxOptions } from '@cloudflare/sandbox';
import type { DurableObjectNamespace } from '@cloudflare/workers-types';

export { Sandbox } from '@cloudflare/sandbox';
/**
 * env.Sandbox 不是沙箱本身，而是创建沙箱的"工厂"
 * 必须通过 getSandbox(env.Sandbox, id) 来获取实际的沙箱实例
 * 相同的 ID 总是返回相同的沙箱（这是 Durable Objects 的特性）
 * 每个沙箱 ID 对应一个独立的容器环境
 *
 * 类比
 * 可以把它想象成：
 *
 * env.Sandbox = 沙箱管理器（管理所有沙箱）
 * getSandbox(env.Sandbox, "user-123") = 获取用户 123 的专属沙箱
 * sandbox = 实际的沙箱实例（可以执行命令、读写文件等）
 *
 * 这样设计的好处是：同一个用户的多次请求会使用同一个沙箱，保持状态和文件持久化
 * env.Sandbox (Durable Object Namespace)
 *     │
 *     ├─→ getSandbox(env.Sandbox, "user-1")    → Sandbox 实例 1
 *     ├─→ getSandbox(env.Sandbox, "user-2")    → Sandbox 实例 2
 *     ├─→ getSandbox(env.Sandbox, "session-a") → Sandbox 实例 3
 *     └─→ getSandbox(env.Sandbox, "project-x") → Sandbox 实例 4
 */

// Declare Worker bindings to enable TypeScript hints
type Env = {
  Sandbox: DurableObjectNamespace;
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    console.log("-----😀env----")
    console.log(env)
    console.log("----😀request----")
    console.log(request)


    // Sandbox lifecycle management
    if (url.pathname === '/sandbox') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const requestedId = getRequestedId(
          body?.sandboxId ?? body?.id ?? url.searchParams.get('sandbox_id')
        );
        const sandboxId = requestedId ?? crypto.randomUUID();
        const options = getSandboxOptions(body?.options);
        const sandbox = getSandbox(env.Sandbox, sandboxId, options);

        return Response.json({
          sandboxId,
          created: true,
          options
        });
      }

      if (request.method === 'DELETE') {
        const body = await safeJson(request);
        const sandboxId =
          getRequestedId(body?.sandboxId ?? body?.id) ??
          getRequestedId(url.searchParams.get('sandbox_id')) ??
          request.headers.get('x-sandbox-id');

        if (!sandboxId) {
          return Response.json(
            { error: 'DELETE /sandbox requires sandbox_id param, id in body, or x-sandbox-id header' },
            { status: 400 }
          );
        }

        try {
          const sandbox = getSandbox(env.Sandbox, sandboxId);
          
          // Check if sandbox exists before destroying
          // This check happens before destroy() to accurately report if sandbox existed
          const existed = await checkSandboxExists(sandbox);
          
          // Destroy the sandbox (safe to call even if already destroyed or doesn't exist)
          // According to Cloudflare docs, destroy() can be safely called multiple times
          await sandbox.destroy();
          
          return Response.json({ 
            sandboxId, 
            destroyed: true,
            existed: existed // Report whether sandbox existed before destruction
          });
        } catch (err: any) {
          const errorMsg = err?.message || 'Failed to destroy sandbox';
          // Check if error indicates sandbox doesn't exist
          if (errorMsg.includes('not found') || errorMsg.includes('does not exist') || errorMsg.includes('404')) {
            return Response.json(
              { 
                sandboxId, 
                destroyed: false,
                existed: false,
                error: 'Sandbox not found or already destroyed'
              },
              { status: 404 }
            );
          }
          // Other errors
          return Response.json(
            { 
              sandboxId,
              destroyed: false,
              error: errorMsg
            },
            { status: 500 }
          );
        }
      }

      return Response.json({ error: 'Use POST to create or DELETE to destroy a sandbox.' }, { status: 405 });
    }

    // Pick a Sandbox instance for this request:
    // 1) header x-sandbox-id
    // 2) query ?sandbox_id=
    // 3) otherwise reject (no implicit default)
    const sandboxId =
      request.headers.get('x-sandbox-id')// ?? url.searchParams.get('sandbox_id');
    //# GET 请求（请求头传 x-sandbox-id）
    // curl -H "x-sandbox-id: sb-123456" "https://你的域名/接口路径"
    //# POST 请求（同时带请求头和请求体，不影响 sandboxId 获取）
    // curl -X POST \
    //   -H "x-sandbox-id: sb-123456" \
    //   -H "Content-Type: application/json" \
    //   -d '{"key":"value"}' \
    //   "https://你的域名/接口路径"
    //# GET 请求（URL 拼接 sandbox_id）
    // curl "https://你的域名/接口路径?sandbox_id=sb-123456"
    //
    // # POST 请求（URL 参数仍有效，和请求体无关）
    // curl -X POST \
    //   -H "Content-Type: application/json" \
    //   -d '{"key":"value"}' \
    //   "https://你的域名/接口路径?sandbox_id=sb-123456"

    //“先看请求头里有没有 x-sandbox-id，如果有（值不是 null/undefined），就用这个值当 sandboxId；
    // 如果请求头里没有（返回 null），就去 URL 里找 sandbox_id 参数，有就用，没有就最终是 null。”
    // 比如用户输入 0（合法值），不能被替换成 100
    //const count = userInput ?? 100;
    // 如果 userInput 是 0 → count = 0；如果是 null → count = 100

    if (!sandboxId) {
      return Response.json(
        { error: 'Missing sandbox id. Provide x-sandbox-id header' },
        { status: 400 }
      );
    }
    const sandbox = getSandbox(env.Sandbox, sandboxId);//拿到sandbox实例

    // Session management endpoints
    if (url.pathname === '/session') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const sessionId = typeof body?.id === 'string' ? body.id : undefined;
        const env = typeof body?.env === 'object' && body.env !== null ? body.env as Record<string, string> : undefined;
        const cwd = typeof body?.cwd === 'string' ? body.cwd : undefined;

        try {
          // Verify sandbox exists before creating session
          const sandboxExists = await checkSandboxExists(sandbox);
          if (!sandboxExists) {
            return Response.json(
              { error: 'Sandbox not found or not initialized' },
              { status: 404 }
            );
          }

          const session = await sandbox.createSession({
            id: sessionId,
            env,
            cwd
          });

          return Response.json({
            success: true,
            sessionId: session.id,
            timestamp: new Date().toISOString()
          });
        } catch (err: any) {
          const errorMsg = err?.message || '';
          
          // If session already exists, return the existing session instead of error
          if (errorMsg.includes('already exists')) {
            if (sessionId) {
              try {
                const existingSession = await sandbox.getSession(sessionId);
                return Response.json({
                  success: true,
                  sessionId: existingSession.id,
                  message: `Session '${sessionId}' already exists`,
                  timestamp: new Date().toISOString()
                });
              } catch (getErr: any) {
                // If we can't get the session, check if sandbox doesn't exist
                const getErrMsg = getErr?.message || '';
                if (getErrMsg.includes('not found') || getErrMsg.includes('does not exist') || 
                    getErrMsg.includes('Container') && (getErrMsg.includes('not found') || getErrMsg.includes('not initialized'))) {
                  return Response.json(
                    { error: 'Sandbox not found or not initialized' },
                    { status: 404 }
                  );
                }
                // Other errors when getting existing session
                return Response.json(
                  { error: err.message || 'Failed to create session' },
                  { status: 500 }
                );
              }
            }
          }
          
          // Check for sandbox/container related errors (404)
          if (errorMsg.includes('not found') || errorMsg.includes('does not exist') || 
              errorMsg.includes('Container') && (errorMsg.includes('not found') || errorMsg.includes('not initialized') || errorMsg.includes('404'))) {
            return Response.json(
              { error: 'Sandbox not found or not initialized' },
              { status: 404 }
            );
          }
          
          // Check for parameter validation errors (400)
          if (errorMsg.includes('invalid') || errorMsg.includes('Invalid') || 
              errorMsg.includes('path') && errorMsg.includes('invalid') ||
              (cwd && !cwd.startsWith('/'))) {
            return Response.json(
              { error: errorMsg || 'Invalid request parameters' },
              { status: 400 }
            );
          }
          
          // All other errors are treated as internal server errors (500)
          return Response.json(
            { error: errorMsg || 'Failed to create session' },
            { status: 500 }
          );
        }
      }

      if (request.method === 'GET') {
        const sessionId = url.searchParams.get('id') || url.searchParams.get('sessionId');
        if (!sessionId) {
          return Response.json(
            { error: 'GET /session requires ?id= or ?sessionId= parameter' },
            { status: 400 }
          );
        }

        try {
          const session = await sandbox.getSession(sessionId);

          // Extra verification to avoid silently "creating" or ghost sessions:
          // run a no-op command; if the session truly does not exist, SDK will throw
          try {
            await session.exec('echo -n');
          } catch (verifyErr: any) {
            const verifyMsg = verifyErr?.message || '';
            console.warn('[session][get] verify failed', {
              sessionId,
              error: verifyMsg
            });
            if (
              verifyMsg.includes('not found') ||
              verifyMsg.includes('does not exist') ||
              verifyMsg.includes('Container') && (verifyMsg.includes('not found') || verifyMsg.includes('not initialized'))
            ) {
              return Response.json(
                { error: 'Session not found' },
                { status: 404 }
              );
            }
            // For other errors, fall through to a 500
            return Response.json(
              { error: verifyMsg || 'Failed to verify session' },
              { status: 500 }
            );
          }

          console.info('[session][get] ok', { sessionId });
          return Response.json({
            success: true,
            sessionId: session.id,
            timestamp: new Date().toISOString()
          });
        } catch (err: any) {
          return Response.json(
            { error: err.message || 'Session not found' },
            { status: 404 }
          );
        }
      }

      if (request.method === 'DELETE') {
        const body = await safeJson(request);
        const sessionId = typeof body?.sessionId === 'string' 
          ? body.sessionId 
          : url.searchParams.get('id') || url.searchParams.get('sessionId');

        if (!sessionId) {
          return Response.json(
            { error: 'DELETE /session requires sessionId in body or ?id= parameter' },
            { status: 400 }
          );
        }

        try {
          const result = await sandbox.deleteSession(sessionId);
          return Response.json({
            success: result.success,
            sessionId: result.sessionId,
            timestamp: result.timestamp
          });
        } catch (err: any) {
          const errorMsg = err?.message || '';
          
          // Check for session/sandbox not found errors (404)
          if (errorMsg.includes('not found') || errorMsg.includes('does not exist') || 
              errorMsg.includes('Session') && (errorMsg.includes('not found') || errorMsg.includes('does not exist')) ||
              errorMsg.includes('Container') && (errorMsg.includes('not found') || errorMsg.includes('not initialized') || errorMsg.includes('404'))) {
            return Response.json(
              { error: 'Session or sandbox not found' },
              { status: 404 }
            );
          }
          
          // Check for parameter validation errors (400)
          if (errorMsg.includes('invalid') || errorMsg.includes('Invalid')) {
            return Response.json(
              { error: errorMsg || 'Invalid request parameters' },
              { status: 400 }
            );
          }
          
          // All other errors are treated as internal server errors (500)
          return Response.json(
            { error: errorMsg || 'Failed to delete session' },
            { status: 500 }
          );
        }
      }

      return Response.json(
        { error: 'Use POST to create, GET to retrieve, or DELETE to remove a session.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/run') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const command =
          typeof body?.command === 'string' && body.command.trim().length > 0
            ? body.command
            : undefined;

        if (!command) {
          return Response.json(
            { error: 'POST /run expects JSON body { "command": "..." }' },
            { status: 400 }
          );
        }

        // Verify sandbox exists before executing command
        try {
          const sandboxExists = await checkSandboxExists(sandbox);
          if (!sandboxExists) {
            return Response.json(
              { error: 'Sandbox not found or not initialized' },
              { status: 404 }
            );
          }
        } catch (err: any) {
          const errorMsg = err?.message || '';
          if (errorMsg.includes('not found') || errorMsg.includes('does not exist') || 
              errorMsg.includes('Container') && (errorMsg.includes('not found') || errorMsg.includes('not initialized'))) {
            return Response.json(
              { error: 'Sandbox not found or not initialized' },
              { status: 404 }
            );
          }
          // Re-throw other errors
          throw err;
        }

        // Support optional sessionId for session-scoped execution
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
        let result;
        if (sessionId) {
          const session = await sandbox.getSession(sessionId);
          result = await session.exec(command);
        } else {
          result = await sandbox.exec(command);
        }
        return Response.json(formatExecResult(result));
      }

      // Backwards-compatible demo when called via GET
      // Verify sandbox exists before executing
      try {
        const sandboxExists = await checkSandboxExists(sandbox);
        if (!sandboxExists) {
          return Response.json(
            { error: 'Sandbox not found or not initialized' },
            { status: 404 }
          );
        }
      } catch (err: any) {
        const errorMsg = err?.message || '';
        if (errorMsg.includes('not found') || errorMsg.includes('does not exist') || 
            errorMsg.includes('Container') && (errorMsg.includes('not found') || errorMsg.includes('not initialized'))) {
          return Response.json(
            { error: 'Sandbox not found or not initialized' },
            { status: 404 }
          );
        }
        throw err;
      }

      const sessionId = url.searchParams.get('sessionId');
      let result;
      if (sessionId) {
        const session = await sandbox.getSession(sessionId);
        result = await session.exec('python3 -c "print(2 + 2)"');
      } else {
        result = await sandbox.exec('python3 -c "print(2 + 2)"');
      }
      return Response.json(formatExecResult(result));
    }

    if (url.pathname === '/run-script') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const script = typeof body?.script === 'string' ? body.script : undefined;
        const interpreter = typeof body?.interpreter === 'string' ? body.interpreter : 'python3';
        const path = typeof body?.path === 'string' ? getRequestedPath(body.path) : undefined;

        if (!script || script.trim().length === 0) {
          return Response.json(
            { error: 'POST /run-script expects JSON body { "script": "...", "interpreter": "python3" (optional), "path": "/path/to/file" (optional) }' },
            { status: 400 }
          );
        }

        // Use provided path or generate a temporary path
        const scriptPath = path ?? `/workspace/script-${crypto.randomUUID()}.py`;
        
        // Support optional sessionId
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
        
        // Write script to file (with session context if provided)
        if (sessionId) {
          const session = await sandbox.getSession(sessionId);
          await session.writeFile(scriptPath, script);
        } else {
          await sandbox.writeFile(scriptPath, script);
        }

        // Determine command based on interpreter
        let command: string;
        if (interpreter === 'python3' || interpreter === 'python') {
          command = `python3 ${scriptPath}`;
        } else if (interpreter === 'bash' || interpreter === 'sh') {
          command = `bash ${scriptPath}`;
        } else if (interpreter === 'node' || interpreter === 'nodejs') {
          command = `node ${scriptPath}`;
        } else {
          // Generic: use interpreter directly
          command = `${interpreter} ${scriptPath}`;
        }

        // Execute the script (with session context if provided)
        let result;
        if (sessionId) {
          const session = await sandbox.getSession(sessionId);
          result = await session.exec(command);
        } else {
          result = await sandbox.exec(command);
        }

        // Optionally clean up temporary file (if path was auto-generated)
        if (!path) {
          try {
            if (sessionId) {
              const session = await sandbox.getSession(sessionId);
              await session.deleteFile(scriptPath);
            } else {
              await sandbox.deleteFile(scriptPath);
            }
          } catch {
            // Ignore cleanup errors
          }
        }

        return Response.json({
          ...formatExecResult(result),
          scriptPath,
          interpreter
        });
      }

      return Response.json(
        { error: 'Use POST to run a script.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/mount-bucket') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const bucket = typeof body?.bucket === 'string' ? body.bucket.trim() : '';
        const mountPath = getRequestedPath(body?.mountPath ?? body?.path);
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
        const rawOptions = body?.options;

        if (!bucket || !mountPath) {
          return Response.json(
            { error: 'POST /mount-bucket expects JSON body { "bucket": "...", "mountPath": "/data", "options": { "endpoint": "..." } }' },
            { status: 400 }
          );
        }

        // Build mount options; endpoint is required by SDK
        let mountOptions: Record<string, unknown> | undefined;
        if (rawOptions && typeof rawOptions === 'object') {
          const optionsObj = rawOptions as Record<string, unknown>;
          if (typeof optionsObj.endpoint === 'string' && optionsObj.endpoint.trim()) {
            mountOptions = {
              endpoint: optionsObj.endpoint,
              provider: optionsObj.provider,
              credentials: optionsObj.credentials,
              readOnly: optionsObj.readOnly,
              s3fsOptions: optionsObj.s3fsOptions
            };
          } else {
            return Response.json(
              { error: 'options.endpoint is required for /mount-bucket' },
              { status: 400 }
            );
          }
        } else {
          return Response.json(
            { error: 'options.endpoint is required for /mount-bucket' },
            { status: 400 }
          );
        }

        try {
          const target = sessionId ? await sandbox.getSession(sessionId) : sandbox;
          await target.mountBucket(bucket, mountPath, mountOptions as any);
          return Response.json({
            success: true,
            bucket,
            mountPath,
            options: mountOptions
          });
        } catch (err: any) {
          const message = err?.message || 'Failed to mount bucket';

          // Not found errors (sandbox/session)
          if (
            message.includes('not found') ||
            message.includes('does not exist') ||
            message.includes('Container') && (message.includes('not found') || message.includes('not initialized'))
          ) {
            return Response.json({ error: 'Sandbox or session not found' }, { status: 404 });
          }

          // Validation errors
          if (
            message.includes('invalid') ||
            message.includes('Invalid') ||
            message.includes('MissingCredentialsError') ||
            message.includes('InvalidMountConfigError')
          ) {
            return Response.json({ error: message }, { status: 400 });
          }

          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use POST to mount a bucket.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/unmount-bucket') {
      if (request.method === 'DELETE') {
        const body = await safeJson(request);
        const mountPath = getRequestedPath(
          body?.mountPath ?? body?.path ?? url.searchParams.get('mountPath') ?? url.searchParams.get('path')
        );
        const sessionId = typeof body?.sessionId === 'string'
          ? body.sessionId
          : url.searchParams.get('sessionId') ?? undefined;

        if (!mountPath) {
          return Response.json(
            { error: 'DELETE /unmount-bucket expects mountPath in body or ?mountPath=' },
            { status: 400 }
          );
        }

        try {
          const target = sessionId ? await sandbox.getSession(sessionId) : sandbox;
          await target.unmountBucket(mountPath);
          return Response.json({ success: true, mountPath });
        } catch (err: any) {
          const message = err?.message || 'Failed to unmount bucket';

          if (
            message.includes('not found') ||
            message.includes('does not exist') ||
            message.includes('Container') && (message.includes('not found') || message.includes('not initialized'))
          ) {
            return Response.json({ error: 'Sandbox or session not found' }, { status: 404 });
          }

          if (message.includes('Invalid') || message.includes('invalid')) {
            return Response.json({ error: message }, { status: 400 });
          }

          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use DELETE to unmount a bucket.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/file') {
      if (request.method === 'PUT') {
        const body = await safeJson(request);
        const path = getRequestedPath(body?.path);
        if (!path) {
          return Response.json(
            { error: 'PUT /file expects JSON body { "path": "...", "content": "..." }' },
            { status: 400 }
          );
        }
        const content = typeof body?.content === 'string' ? body.content : '';
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
        
        try {
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            await session.writeFile(path, content);
          } else {
            await sandbox.writeFile(path, content);
          }
          return Response.json({ path, length: content.length });
        } catch (error: unknown) {
          // Extract error message and status code from SandboxError
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          // SandboxError has httpStatus getter from errorResponse
          const sandboxError = error as { httpStatus?: number };
          const statusCode = sandboxError.httpStatus || 500;
          
          return Response.json(
            { error: errorMessage },
            { status: statusCode }
          );
        }
      }

      if (request.method === 'GET') {
        const pathParam = url.searchParams.get('path');
        if (!pathParam) {
          await sandbox.writeFile('/workspace/hello.txt', 'Hello, Sandbox!');
          const file = await sandbox.readFile('/workspace/hello.txt');
          return Response.json({
            content: file.content
          });
        }

        const path = getRequestedPath(pathParam);
        if (!path) {
          return Response.json(
            { error: 'Provide a non-empty ?path=/your/file.txt value.' },
            { status: 400 }
          );
        }

        try {
          const sessionId = url.searchParams.get('sessionId');
          let file;
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            file = await session.readFile(path);
          } else {
            file = await sandbox.readFile(path);
          }
          
          if (url.searchParams.get('mode') === 'download') {
            const filename = path.split('/').filter(Boolean).pop() ?? 'sandbox-file';
            return new Response(file.content ?? '', {
              headers: {
                'content-type': 'text/plain; charset=utf-8',
                'content-disposition': `attachment; filename="${filename}"`
              }
            });
          }

          return Response.json({ path, content: file.content });
        } catch (err) {
          if (isNotFoundError(err)) {
            return Response.json(
              { error: `File not found: ${path}` },
              { status: 404 }
            );
          }
          throw err;
        }
      }

      if (request.method === 'DELETE') {
        const path = getRequestedPath(url.searchParams.get('path'));
        if (!path) {
          return Response.json(
            { error: 'DELETE /file requires ?path=/your/file.txt' },
            { status: 400 }
          );
        }
        try {
          const sessionId = url.searchParams.get('sessionId');
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            await session.deleteFile(path);
          } else {
            await sandbox.deleteFile(path);
          }
          return Response.json({ path, deleted: true });
        } catch (err) {
          // Gracefully handle deleting a non-existent file to avoid 500s
          if (isNotFoundError(err)) {
            return Response.json(
              { error: `File not found: ${path}` },
              { status: 404 }
            );
          }
          throw err;
        }
      }

      return Response.json(
        { error: 'Use PUT/GET/DELETE to write/read/delete files.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/mkdir') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const path = getRequestedPath(body?.path);
        const recursive = body?.recursive === true;
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;

        if (!path) {
          return Response.json(
            { error: 'POST /mkdir expects JSON body { "path": "/workspace/dir", "recursive": true|false }' },
            { status: 400 }
          );
        }

        try {
          console.log('[mkdir] incoming', {
            path,
            recursive,
            sessionId,
            timestamp: new Date().toISOString(),
          });
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            await session.mkdir(path, { recursive });
          } else {
            await sandbox.mkdir(path, { recursive });
          }
          console.log('[mkdir] success', {
            path,
            recursive,
            sessionId,
            timestamp: new Date().toISOString(),
          });
          return Response.json({ success: true, path, recursive, sessionId });
        } catch (err: any) {
          const message = err?.message || 'Failed to create directory';
          console.error('[mkdir] error', {
            path,
            recursive,
            sessionId,
            error: message,
            stack: err?.stack,
            timestamp: new Date().toISOString(),
          });
          if (message.includes('not found') || message.includes('does not exist')) {
            return Response.json({ error: 'Sandbox or session not found' }, { status: 404 });
          }
          if (message.toLowerCase().includes('invalid')) {
            return Response.json({ error: message }, { status: 400 });
          }
          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use POST to create directories.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/exists') {
      if (request.method === 'GET') {
        const path = getRequestedPath(url.searchParams.get('path'));
        const sessionId = url.searchParams.get('sessionId') ?? undefined;

        if (!path) {
          return Response.json(
            { error: 'GET /exists requires ?path=/workspace/file.txt' },
            { status: 400 }
          );
        }

        try {
          const existsResult = sessionId
            ? await (await sandbox.getSession(sessionId)).exists(path)
            : await sandbox.exists(path);
          return Response.json(existsResult);
        } catch (err: any) {
          const message = err?.message || 'Failed to check existence';
          if (message.includes('not found') || message.includes('does not exist')) {
            return Response.json({ error: 'Sandbox or session not found' }, { status: 404 });
          }
          if (message.toLowerCase().includes('invalid')) {
            return Response.json({ error: message }, { status: 400 });
          }
          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use GET to check file existence.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/rename') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const oldPath = getRequestedPath(body?.oldPath ?? body?.from);
        const newPath = getRequestedPath(body?.newPath ?? body?.to);
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;

        if (!oldPath || !newPath) {
          return Response.json(
            { error: 'POST /rename expects JSON body { "oldPath": "/a.txt", "newPath": "/b.txt" }' },
            { status: 400 }
          );
        }

        try {
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            await session.renameFile(oldPath, newPath);
          } else {
            await sandbox.renameFile(oldPath, newPath);
          }
          return Response.json({ success: true, from: oldPath, to: newPath });
        } catch (err: any) {
          const message = err?.message || 'Failed to rename file';
          if (message.includes('not found') || message.includes('does not exist')) {
            return Response.json({ error: 'File or sandbox not found' }, { status: 404 });
          }
          if (message.toLowerCase().includes('invalid')) {
            return Response.json({ error: message }, { status: 400 });
          }
          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use POST to rename files.' },
        { status: 405 }
      );
    }

    if (url.pathname === '/move') {
      if (request.method === 'POST') {
        const body = await safeJson(request);
        const sourcePath = getRequestedPath(body?.sourcePath ?? body?.from);
        const destinationPath = getRequestedPath(body?.destinationPath ?? body?.to);
        const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;

        if (!sourcePath || !destinationPath) {
          return Response.json(
            { error: 'POST /move expects JSON body { "sourcePath": "/a.txt", "destinationPath": "/dir/a.txt" }' },
            { status: 400 }
          );
        }

        try {
          if (sessionId) {
            const session = await sandbox.getSession(sessionId);
            await session.moveFile(sourcePath, destinationPath);
          } else {
            await sandbox.moveFile(sourcePath, destinationPath);
          }
          return Response.json({ success: true, from: sourcePath, to: destinationPath });
        } catch (err: any) {
          const message = err?.message || 'Failed to move file';
          if (message.includes('not found') || message.includes('does not exist')) {
            return Response.json({ error: 'File or sandbox not found' }, { status: 404 });
          }
          if (message.toLowerCase().includes('invalid')) {
            return Response.json({ error: message }, { status: 400 });
          }
          return Response.json({ error: message }, { status: 500 });
        }
      }

      return Response.json(
        { error: 'Use POST to move files.' },
        { status: 405 }
      );
    }

    return new Response('Try /run or /file');
  }
};

async function safeJson(request: Request): Promise<Record<string, unknown> | null> {
  try {
    return (await request.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function getRequestedPath(path: unknown): string | null {
  if (typeof path !== 'string') {
    return null;
  }

  const trimmed = path.trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return normalized.replace(/\/{2,}/g, '/');
}

function getRequestedId(id: unknown): string | null {
  if (typeof id !== 'string') {
    return null;
  }
  const trimmed = id.trim();
  return trimmed || null;
}

function getSandboxOptions(options: unknown): SandboxOptions | undefined {
  if (!options || typeof options !== 'object') {
    return undefined;
  }

  const maybeOptions = options as Record<string, unknown>;
  const result: SandboxOptions = {};

  if (typeof maybeOptions.sleepAfter === 'string') {
    result.sleepAfter = maybeOptions.sleepAfter;
  }
  if (typeof maybeOptions.keepAlive === 'boolean') {
    result.keepAlive = maybeOptions.keepAlive;
  }
  if (typeof maybeOptions.normalizeId === 'boolean') {
    result.normalizeId = maybeOptions.normalizeId;
  }
  if (maybeOptions.containerTimeouts && typeof maybeOptions.containerTimeouts === 'object') {
    result.containerTimeouts = maybeOptions.containerTimeouts as SandboxOptions['containerTimeouts'];
  }

  return Object.keys(result).length ? result : undefined;
}

type SimpleExecResult = {
  stdout?: string;
  stderr?: string;
  exitCode: number;
  success: boolean;
};

function formatExecResult(result: SimpleExecResult) {
  return {
    output: result.stdout,
    error: result.stderr,
    exitCode: result.exitCode,
    success: result.success
  };
}

function isNotFoundError(err: unknown): boolean {
  if (!err || typeof err !== 'object') {
    return false;
  }

  const anyErr = err as { name?: string; message?: string };
  return (
    anyErr.name === 'FileNotFoundError' ||
    typeof anyErr.message === 'string' &&
      anyErr.message.includes('File not found')
  );
}

/**
 * Check if a sandbox exists and is initialized by attempting a lightweight operation
 * @param sandbox The sandbox instance to check
 * @returns true if sandbox exists and is accessible, false otherwise
 */
async function checkSandboxExists(sandbox: Sandbox): Promise<boolean> {
  try {
    // Execute a lightweight command to check if container is accessible
    // This will fail if container doesn't exist or hasn't been initialized
    await sandbox.exec('echo -n');
    return true; // If exec succeeds, sandbox exists
  } catch (err: any) {
    // If exec fails, check the error type
    const errorMsg = err?.message || '';
    // Container-related errors suggest sandbox doesn't exist or isn't initialized
    if (
      errorMsg.includes('Container') && 
      (errorMsg.includes('not found') || errorMsg.includes('not initialized') || errorMsg.includes('404'))
    ) {
      return false;
    }
    // Check for other "not found" patterns
    if (
      errorMsg.includes('not found') || 
      errorMsg.includes('does not exist') ||
      errorMsg.includes('404')
    ) {
      return false;
    }
    // Other errors might indicate sandbox exists but command failed
    // In this case, we assume it exists (conservative approach)
    return true;
  }
}
