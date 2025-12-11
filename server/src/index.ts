import { getSandbox, type Sandbox, type SandboxOptions, type ExecOptions, type MountBucketOptions } from '@cloudflare/sandbox';
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
 *
 * 会话（session）API 见官方文档：https://developers.cloudflare.com/sandbox/api/sessions/
 */

// Declare Worker bindings to enable TypeScript hints
type Env = {
  Sandbox: DurableObjectNamespace;
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    // console.log("-----😀env----")
    // console.log(env)
    // console.log("----😀request----")
    // console.log(request)
    const requestedId = request.headers.get('x-sandbox-id');
    if (!requestedId) {
      return respond({ error: 'Missing sandbox id. Provide x-sandbox-id header' }, 400, 'Missing sandbox id. Provide x-sandbox-id header');
    }


    // Sandbox exec (non-session)
    if (url.pathname === '/exec') {
      return handleExec(request, env, requestedId);
    }

    // Session demo: create / get / delete session within a sandbox
    if (url.pathname === '/session/exec') {
      return handleSessionExec(request, env, requestedId, url);
    }
    if (url.pathname === '/session/env') {
      return handleSessionEnv(request, env, requestedId, url);
    }
    if (url.pathname === '/session') {
      return handleSession(request, env, requestedId, url);
    }

    // Lifecycle demo: create / destroy sandbox
    if (url.pathname === '/lifecycle') {
      return handleLifecycle(request, env, requestedId);
    }

    // File operations
    if (url.pathname === '/files/write') {
      return handleWriteFile(request, env, requestedId);
    }
    if (url.pathname === '/files/read') {
      return handleReadFile(request, env, requestedId);
    }
    if (url.pathname === '/files/mkdir') {
      return handleMkdir(request, env, requestedId);
    }
    if (url.pathname === '/files/rename') {
      return handleRenameFile(request, env, requestedId);
    }
    if (url.pathname === '/files/move') {
      return handleMoveFile(request, env, requestedId);
    }
    if (url.pathname === '/files/delete') {
      return handleDeleteFile(request, env, requestedId);
    }
    if (url.pathname === '/files/exists') {
      return handleExists(request, env, requestedId);
    }

    // Bucket mounting operations
    if (url.pathname === '/mount-bucket') {
      return handleMountBucket(request, env, requestedId);
    }
    if (url.pathname === '/unmount-bucket') {
      return handleUnmountBucket(request, env, requestedId);
    }

    // Pick a Sandbox instance for this request:
    // 仅允许从 header x-sandbox-id 获取 sandboxId
    // const sandboxId = request.headers.get('x-sandbox-id');
    //# GET/POST 请求（请求头传 x-sandbox-id）
    // curl -H "x-sandbox-id: sb-123456" "https://你的域名/接口路径"
    // curl -X POST -H "x-sandbox-id: sb-123456" -H "Content-Type: application/json" -d '{"k":"v"}' "https://你的域名/接口路径"

    //“先看请求头里有没有 x-sandbox-id，如果有（值不是 null/undefined），就用这个值当 sandboxId；
    // 如果请求头里没有（返回 null），就去 URL 里找 sandbox_id 参数，有就用，没有就最终是 null。”
    // 比如用户输入 0（合法值），不能被替换成 100
    //const count = userInput ?? 100;
    // 如果 userInput 是 0 → count = 0；如果是 null → count = 100

    // if (!sandboxId) {
    //   return respond({ error: 'Missing sandbox id. Provide x-sandbox-id header' }, 400, 'Missing sandbox id. Provide x-sandbox-id header');
    // }
    // const sandbox = getSandbox(env.Sandbox, sandboxId);//拿到sandbox实例 自己就会创建！！！
    // console.log("😀create")
    /*
    ✅ 返回一个 sandbox 对象引用
❌ 容器还没有启动
❌ 没有消耗 CPU/内存资源
    * ✅ 懒加载（实际方式）:
getSandbox()  →  立即返回 sandbox 对象（<1ms）
     ↓
只有真正需要时才启动容器
     ↓
sandbox.exec()  →  [启动容器 2-3秒]  →  执行命令
    * */

    return respond({ ok: true, sandboxId: requestedId }, 200, 'ok');
          }
};

async function safeJson(request: Request): Promise<Record<string, any> | null> {
  try {
    return (await request.json()) as Record<string, any>;
  } catch {
    return null;
  }
}

function getSandboxOptions(options: unknown): SandboxOptions | undefined {
  if (!options || typeof options !== 'object') return undefined;
  const raw = options as Record<string, unknown>;
  const result: SandboxOptions = {};
  if (typeof raw.sleepAfter === 'string') result.sleepAfter = raw.sleepAfter;
  if (typeof raw.keepAlive === 'boolean') result.keepAlive = raw.keepAlive;
  if (typeof raw.normalizeId === 'boolean') result.normalizeId = raw.normalizeId;
  if (raw.containerTimeouts && typeof raw.containerTimeouts === 'object') {
    result.containerTimeouts = raw.containerTimeouts as SandboxOptions['containerTimeouts'];
  }
  return Object.keys(result).length ? result : undefined;
}

function respond(data: any, status = 200, message = 'ok') {
  return Response.json({ data, message, code: status }, { status });
}

async function handleLifecycle(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase(); // 得到 POST 或 DELETE
  console.log(method);
  const body = await safeJson(request); // 尝试把请求体 JSON 化；如果体不是合法 JSON，返回 null。

  if (method === 'POST') {
    const options = getSandboxOptions(body?.options);
    // getSandbox 只返回引用，容器在首次 exec/write 时才会懒加载启动
    const sandbox = getSandbox(env.Sandbox, sandboxId, options);

    // 立刻执行一个极轻量命令，强制拉起容器并校验可用性
    try {
      const init = await sandbox.exec('echo ready');
      return respond({ sandboxId, created: true, initialized: true, init, options }, 200, 'ok');
    } catch (err: any) {
      const message = err?.message || 'init failed';
      return respond({ sandboxId, created: false, initialized: false, error: message, options }, 500, message);
    }
  }

  if (method === 'DELETE') {
    // 无论怎么样都会返回 200 即使容器不存在已经被销毁 但是被销毁的肯定不存在了
    const sandbox = getSandbox(env.Sandbox, sandboxId);
    try {
      await sandbox.destroy();
      return respond({ sandboxId, destroyed: true }, 200, 'ok');
        } catch (err: any) {
      const message = err?.message || 'destroy failed';
      return respond({ sandboxId, destroyed: false, error: message }, 500, message);
    }
  }

  return respond({ error: 'Use POST to create or DELETE to destroy a sandbox.' }, 405, 'Method Not Allowed');
}

async function handleExec(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /exec' }, 405, 'Method Not Allowed');
  }

        const body = await safeJson(request);
        const command =
    typeof body?.command === 'string' && body.command.trim().length > 0 ? body.command.trim() : undefined;
        if (!command) {
    return respond(
      { error: 'Missing command. Provide command in JSON body' },
      400,
      'Missing command. Provide command in JSON body'
    );
  }

  const execOptions = getExecOptions(body?.options ?? body);
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const result = await sandbox.exec(command, execOptions);
    
    // 区分两种情况：
    // 1. 命令执行失败（非零退出码）：result.success === false
    // 2. 命令执行成功（零退出码）：result.success === true
    if (!result.success) {
      // 命令运行但失败（非零退出码）
      return respond(
        {
          sandboxId,
          command,
          result,
          error: `Command failed with exit code ${result.exitCode}`,
          exitCode: result.exitCode
        },
        200, // 仍然返回 200，因为这是业务层面的失败，不是 HTTP 错误
        `Command failed with exit code ${result.exitCode}`
      );
    }
    
    // 命令执行成功
    return respond({ sandboxId, command, result }, 200, 'ok');
  } catch (err: any) {
    // 命令无法启动（执行错误，抛出异常）
    const message = err?.message || 'exec failed';
    return respond(
      { sandboxId, command, error: message, type: 'execution_error' },
      500,
      message
    );
  }
}

async function handleSession(
  request: Request,
  env: Env,
  sandboxId: string,
  url: URL
): Promise<Response> {
  const method = request.method.toUpperCase(); // POST / GET / DELETE
        const body = await safeJson(request);
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  // 仅使用 query 参数传递 session_id
  const sessionId = url.searchParams.get('session_id') ?? undefined;

  if (method === 'POST') {
    const options = getSessionOptions(body?.session || body);
    // 允许 query.session_id 作为 session.id 的来源（body 优先）
    const resolvedIdFromInput = options?.id ?? sessionId;
    if (!resolvedIdFromInput) {
      return respond(
        { error: 'Missing session id. Provide session.id in body or session_id in query' },
        400,
        'Missing session id. Provide session.id in body or session_id in query'
      );
    }
    const mergedOptions = { ...(options || {}), id: resolvedIdFromInput };



    try {
      const session = await sandbox.createSession(mergedOptions); // sandbox 不存在就会创建
      const resolvedId = resolvedIdFromInput ?? (session as any)?.id ?? 'default';
      return respond({ sandboxId, sessionId: resolvedId, created: true, options: mergedOptions }, 200, 'ok');
        } catch (err: any) {
      const message = err?.message || 'create session failed';
      // 已存在的会话，返回 409 避免抛 500
      if (typeof message === 'string' && message.toLowerCase().includes('already exists')) {
        return respond(
          { sandboxId, sessionId: resolvedIdFromInput, created: false, exists: true, error: 'Session already exists' },
          409,
          'Session already exists'
        );
      }
      return respond({ sandboxId, sessionId: resolvedIdFromInput, created: false, error: message }, 500, message);
    }
  }

  if (method === 'DELETE') {
    if (!sessionId) {
      return respond(
        { error: 'Missing session id. Provide session_id query param' },
        400,
        'Missing session id. Provide session_id query param'
      );
    }
    try {
      const result = await sandbox.deleteSession(sessionId);
      return respond({ sandboxId, ...result }, 200, 'ok');
        } catch (err: any) {
      const message = err?.message || 'delete session failed';
      // 不存在的会话，返回 404 而不是 500
      if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
        return respond(
          { sandboxId, sessionId, deleted: false, exists: false, error: 'Session not found' },
          404,
          'Session not found'
        );
      }
      return respond({ sandboxId, sessionId, deleted: false, error: message }, 500, message);
    }
  }

  return respond({ error: 'Use POST/GET/DELETE on /session' }, 405, 'Method Not Allowed');
}

async function handleSessionExec(
  request: Request,
  env: Env,
  sandboxId: string,
  url: URL
): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /session/exec' }, 405, 'Method Not Allowed');
  }

        const body = await safeJson(request);
  const command =
    typeof body?.command === 'string' && body.command.trim().length > 0 ? body.command.trim() : undefined;
  const sessionId =
    (typeof body?.sessionId === 'string' && body.sessionId) ||
    (typeof body?.session_id === 'string' && body.session_id) ||
    url.searchParams.get('session_id') ||
    undefined;

  if (!sessionId) {
    return respond(
      { error: 'Missing session id. Provide session_id in query or sessionId/session_id in body' },
      400,
      'Missing session id. Provide session_id in query or sessionId/session_id in body'
    );
  }

  if (!command) {
    return respond(
      { error: 'Missing command. Provide command in JSON body' },
      400,
      'Missing command. Provide command in JSON body'
    );
  }

  const execOptions = getExecOptions(body?.options ?? body);
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const session = await sandbox.getSession(sessionId);
    const result = await session.exec(command, execOptions);
    
    // 区分两种情况：
    // 1. 命令执行失败（非零退出码）：result.success === false
    // 2. 命令执行成功（零退出码）：result.success === true
    if (!result.success) {
      // 命令运行但失败（非零退出码）
      return respond(
        {
          sandboxId,
          sessionId,
          command,
          result,
          error: `Command failed with exit code ${result.exitCode}`,
          exitCode: result.exitCode
        },
        200, // 仍然返回 200，因为这是业务层面的失败，不是 HTTP 错误
        `Command failed with exit code ${result.exitCode}`
      );
    }
    
    // 命令执行成功
    return respond({ sandboxId, sessionId, command, result }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'session exec failed';
    // 会话不存在
    if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
      return respond({ sandboxId, sessionId, command, error: 'Session not found' }, 404, 'Session not found');
    }
    // 命令无法启动（执行错误，抛出异常）
    return respond(
      { sandboxId, sessionId, command, error: message, type: 'execution_error' },
      500,
      message
    );
  }
}

async function handleSessionEnv(
  request: Request,
  env: Env,
  sandboxId: string,
  url: URL
): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /session/env' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const envVars = body?.envVars || body?.env_vars || body?.env;
  const sessionId =
    (typeof body?.sessionId === 'string' && body.sessionId) ||
    (typeof body?.session_id === 'string' && body.session_id) ||
    url.searchParams.get('session_id') ||
    'default'; // Default to 'default' session if not specified

  if (!envVars || typeof envVars !== 'object') {
    return respond(
      { error: 'Missing envVars. Provide envVars in JSON body' },
      400,
      'Missing envVars. Provide envVars in JSON body'
    );
  }

  // Validate envVars is a record of string to string
  const envVarsRecord: Record<string, string> = {};
  for (const [key, value] of Object.entries(envVars)) {
    if (typeof key === 'string' && typeof value === 'string') {
      envVarsRecord[key] = value;
    } else {
      return respond(
        { error: 'envVars must be a record of string to string' },
        400,
        'Invalid envVars format'
      );
    }
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    // Get or create the session
    let session;
    try {
      session = await sandbox.getSession(sessionId);
    } catch {
      // If session doesn't exist, create it with the env vars
      session = await sandbox.createSession({ id: sessionId, env: envVarsRecord });
      return respond(
        { sandboxId, sessionId, envVars: envVarsRecord, set: true, sessionCreated: true },
        200,
        'ok'
      );
    }

    // Set environment variables on the existing session
    await session.setEnvVars(envVarsRecord);
    return respond({ sandboxId, sessionId, envVars: envVarsRecord, set: true }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'set env vars failed';
    return respond({ sandboxId, sessionId, error: message }, 500, message);
  }
}

function getSessionOptions(options: unknown) {
  if (!options || typeof options !== 'object') return undefined;
  const raw = options as Record<string, unknown>;
  const result: Record<string, any> = {};
  if (typeof raw.id === 'string') result.id = raw.id;
  if (raw.env && typeof raw.env === 'object') result.env = raw.env as Record<string, string>;
  if (typeof raw.cwd === 'string') result.cwd = raw.cwd;
  return Object.keys(result).length ? result : undefined;
}

function getExecOptions(options: unknown): ExecOptions | undefined {
  if (!options || typeof options !== 'object') return undefined;
  const raw = options as Record<string, unknown>;
  const result: ExecOptions = {};
  if (typeof raw.cwd === 'string') result.cwd = raw.cwd;
  if (raw.env && typeof raw.env === 'object') result.env = raw.env as Record<string, string>;
  if (typeof raw.timeout === 'number') result.timeout = raw.timeout;
  return Object.keys(result).length ? result : undefined;
}

// File operations handlers

async function handleWriteFile(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /files/write' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const path = typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined;
  const content = body?.content !== undefined ? body.content : undefined;

  if (!path) {
    return respond({ error: 'Missing path. Provide path in JSON body' }, 400, 'Missing path');
  }
  if (content === undefined) {
    return respond({ error: 'Missing content. Provide content in JSON body' }, 400, 'Missing content');
  }

  const encoding = typeof body?.encoding === 'string' ? body.encoding : undefined;
  const options = encoding ? { encoding: encoding as 'base64' | 'utf-8' } : undefined;

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    await sandbox.writeFile(path, content, options);
    return respond({ sandboxId, path, written: true, encoding }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'write file failed';
    return respond({ sandboxId, path, written: false, error: message }, 500, message);
  }
}

async function handleReadFile(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'GET' && method !== 'POST') {
    return respond({ error: 'Use GET or POST on /files/read' }, 405, 'Method Not Allowed');
  }

  const url = new URL(request.url);
  let path: string | undefined;
  let encoding: string | undefined;

  if (method === 'GET') {
    path = url.searchParams.get('path') || undefined;
    encoding = url.searchParams.get('encoding') || undefined;
  } else {
    const body = await safeJson(request);
    path = typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined;
    encoding = typeof body?.encoding === 'string' ? body.encoding : undefined;
  }

  if (!path) {
    return respond({ error: 'Missing path. Provide path in query (GET) or body (POST)' }, 400, 'Missing path');
  }

  const options = encoding ? { encoding: encoding as 'base64' | 'utf-8' } : undefined;
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const file = await sandbox.readFile(path, options);
    return respond({ sandboxId, path, content: file.content, encoding }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'read file failed';
    // 文件不存在
    if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
      return respond({ sandboxId, path, exists: false, error: 'File not found' }, 404, 'File not found');
    }
    return respond({ sandboxId, path, error: message }, 500, message);
  }
}

async function handleMkdir(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /files/mkdir' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const path = typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined;

  if (!path) {
    return respond({ error: 'Missing path. Provide path in JSON body' }, 400, 'Missing path');
  }

  const recursive = typeof body?.recursive === 'boolean' ? body.recursive : false;
  const options = { recursive };
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    await sandbox.mkdir(path, options);
    return respond({ sandboxId, path, created: true, recursive }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'mkdir failed';
    return respond({ sandboxId, path, created: false, error: message }, 500, message);
  }
}

async function handleRenameFile(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /files/rename' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const oldPath = typeof body?.oldPath === 'string' && body.oldPath.trim().length > 0 ? body.oldPath.trim() : undefined;
  const newPath = typeof body?.newPath === 'string' && body.newPath.trim().length > 0 ? body.newPath.trim() : undefined;

  if (!oldPath) {
    return respond({ error: 'Missing oldPath. Provide oldPath in JSON body' }, 400, 'Missing oldPath');
  }
  if (!newPath) {
    return respond({ error: 'Missing newPath. Provide newPath in JSON body' }, 400, 'Missing newPath');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    await sandbox.renameFile(oldPath, newPath);
    return respond({ sandboxId, oldPath, newPath, renamed: true }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'rename file failed';
    // 文件不存在
    if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
      return respond({ sandboxId, oldPath, newPath, renamed: false, error: 'File not found' }, 404, 'File not found');
    }
    return respond({ sandboxId, oldPath, newPath, renamed: false, error: message }, 500, message);
  }
}

async function handleMoveFile(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /files/move' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const sourcePath = typeof body?.sourcePath === 'string' && body.sourcePath.trim().length > 0 ? body.sourcePath.trim() : undefined;
  const destPath = typeof body?.destPath === 'string' && body.destPath.trim().length > 0 ? body.destPath.trim() : undefined;

  if (!sourcePath) {
    return respond({ error: 'Missing sourcePath. Provide sourcePath in JSON body' }, 400, 'Missing sourcePath');
  }
  if (!destPath) {
    return respond({ error: 'Missing destPath. Provide destPath in JSON body' }, 400, 'Missing destPath');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    await sandbox.moveFile(sourcePath, destPath);
    return respond({ sandboxId, sourcePath, destPath, moved: true }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'move file failed';
    // 文件不存在
    if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
      return respond({ sandboxId, sourcePath, destPath, moved: false, error: 'File not found' }, 404, 'File not found');
    }
    return respond({ sandboxId, sourcePath, destPath, moved: false, error: message }, 500, message);
  }
}

async function handleDeleteFile(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'DELETE' && method !== 'POST') {
    return respond({ error: 'Use DELETE or POST on /files/delete' }, 405, 'Method Not Allowed');
  }

  const url = new URL(request.url);
  let path: string | undefined;

  if (method === 'DELETE') {
    path = url.searchParams.get('path') || undefined;
  } else {
    const body = await safeJson(request);
    path = typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined;
  }

  if (!path) {
    return respond({ error: 'Missing path. Provide path in query (DELETE) or body (POST)' }, 400, 'Missing path');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    await sandbox.deleteFile(path);
    return respond({ sandboxId, path, deleted: true }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'delete file failed';
    // 文件不存在
    if (typeof message === 'string' && message.toLowerCase().includes('not found')) {
      return respond({ sandboxId, path, deleted: false, exists: false, error: 'File not found' }, 404, 'File not found');
    }
    return respond({ sandboxId, path, deleted: false, error: message }, 500, message);
  }
}

async function handleExists(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'GET' && method !== 'POST') {
    return respond({ error: 'Use GET or POST on /files/exists' }, 405, 'Method Not Allowed');
  }

  const url = new URL(request.url);
  let path: string | undefined;

  if (method === 'GET') {
    path = url.searchParams.get('path') || undefined;
  } else {
    const body = await safeJson(request);
    path = typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined;
  }

  if (!path) {
    return respond({ error: 'Missing path. Provide path in query (GET) or body (POST)' }, 400, 'Missing path');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const result = await sandbox.exists(path);
    return respond({ sandboxId, path, exists: result.exists }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'exists check failed';
    return respond({ sandboxId, path, error: message }, 500, message);
  }
}

// Bucket mounting handlers

async function handleMountBucket(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'POST') {
    return respond({ error: 'Use POST on /mount-bucket' }, 405, 'Method Not Allowed');
  }

  const body = await safeJson(request);
  const bucket = typeof body?.bucket === 'string' && body.bucket.trim().length > 0 ? body.bucket.trim() : undefined;
  const mountPath = typeof body?.mountPath === 'string' && body.mountPath.trim().length > 0 ? body.mountPath.trim() : undefined;
  const sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
  const rawOptions = body?.options;

  if (!bucket) {
    return respond({ error: 'Missing bucket. Provide bucket in JSON body' }, 400, 'Missing bucket');
  }
  if (!mountPath) {
    return respond({ error: 'Missing mountPath. Provide mountPath in JSON body' }, 400, 'Missing mountPath');
  }

  // Build mount options; endpoint is required
  let mountOptions: MountBucketOptions | undefined;
  if (rawOptions && typeof rawOptions === 'object') {
    const optionsObj = rawOptions as Record<string, unknown>;
    if (typeof optionsObj.endpoint === 'string' && optionsObj.endpoint.trim()) {
      mountOptions = {
        endpoint: optionsObj.endpoint.trim(),
        provider: optionsObj.provider as 'r2' | 's3' | 'gcs' | undefined,
        credentials: optionsObj.credentials as { accessKeyId: string; secretAccessKey: string } | undefined,
        readOnly: typeof optionsObj.readOnly === 'boolean' ? optionsObj.readOnly : undefined,
        s3fsOptions: Array.isArray(optionsObj.s3fsOptions) ? optionsObj.s3fsOptions as string[] : undefined,
      };
    } else {
      return respond({ error: 'options.endpoint is required for /mount-bucket' }, 400, 'Missing endpoint');
    }
  } else {
    return respond({ error: 'options.endpoint is required for /mount-bucket' }, 400, 'Missing options');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const target = sessionId ? await sandbox.getSession(sessionId) : sandbox;
    await target.mountBucket(bucket, mountPath, mountOptions);
    return respond({
      sandboxId,
      sessionId: sessionId || null,
      bucket,
      mountPath,
      mounted: true,
      options: mountOptions,
    }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'mount bucket failed';

    // Not found errors (sandbox/session)
    if (
      typeof message === 'string' && (
        message.toLowerCase().includes('not found') ||
        message.toLowerCase().includes('does not exist') ||
        (message.includes('Container') && (message.toLowerCase().includes('not found') || message.toLowerCase().includes('not initialized')))
      )
    ) {
      return respond({ sandboxId, sessionId, bucket, mountPath, error: 'Sandbox or session not found' }, 404, 'Sandbox or session not found');
    }

    // Validation errors
    if (
      typeof message === 'string' && (
        message.includes('invalid') ||
        message.includes('Invalid') ||
        message.includes('MissingCredentialsError') ||
        message.includes('InvalidMountConfigError')
      )
    ) {
      return respond({ sandboxId, sessionId, bucket, mountPath, error: message }, 400, message);
    }

    return respond({ sandboxId, sessionId, bucket, mountPath, error: message }, 500, message);
  }
}

async function handleUnmountBucket(request: Request, env: Env, sandboxId: string): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== 'DELETE' && method !== 'POST') {
    return respond({ error: 'Use DELETE or POST on /unmount-bucket' }, 405, 'Method Not Allowed');
  }

  const url = new URL(request.url);
  let mountPath: string | undefined;
  let sessionId: string | undefined;

  if (method === 'DELETE') {
    mountPath = url.searchParams.get('mountPath') || url.searchParams.get('path') || undefined;
    sessionId = url.searchParams.get('sessionId') || undefined;
  } else {
    const body = await safeJson(request);
    mountPath = typeof body?.mountPath === 'string' && body.mountPath.trim().length > 0
      ? body.mountPath.trim()
      : (typeof body?.path === 'string' && body.path.trim().length > 0 ? body.path.trim() : undefined);
    sessionId = typeof body?.sessionId === 'string' ? body.sessionId : undefined;
  }

  if (!mountPath) {
    return respond({ error: 'Missing mountPath. Provide mountPath in query (DELETE) or body (POST)' }, 400, 'Missing mountPath');
  }

  const sandbox = getSandbox(env.Sandbox, sandboxId);

  try {
    const target = sessionId ? await sandbox.getSession(sessionId) : sandbox;
    await target.unmountBucket(mountPath);
    return respond({
      sandboxId,
      sessionId: sessionId || null,
      mountPath,
      unmounted: true,
    }, 200, 'ok');
  } catch (err: any) {
    const message = err?.message || 'unmount bucket failed';

    // Not found errors (sandbox/session/mount)
    if (
      typeof message === 'string' && (
        message.toLowerCase().includes('not found') ||
        message.toLowerCase().includes('does not exist') ||
        (message.includes('Container') && (message.toLowerCase().includes('not found') || message.toLowerCase().includes('not initialized')))
      )
    ) {
      return respond({ sandboxId, sessionId, mountPath, error: 'Sandbox, session, or mount not found' }, 404, 'Not found');
    }

    // Validation errors
    if (
      typeof message === 'string' && (
        message.includes('invalid') ||
        message.includes('Invalid') ||
        message.includes('InvalidMountConfigError')
      )
    ) {
      return respond({ sandboxId, sessionId, mountPath, error: message }, 400, message);
    }

    return respond({ sandboxId, sessionId, mountPath, error: message }, 500, message);
  }
}
