import { getSandbox, type Sandbox, type SandboxOptions } from '@cloudflare/sandbox';
import type { DurableObjectNamespace } from '@cloudflare/workers-types';

export { Sandbox } from '@cloudflare/sandbox';

// Declare Worker bindings to enable TypeScript hints
type Env = {
  Sandbox: DurableObjectNamespace;
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

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

        const sandbox = getSandbox(env.Sandbox, sandboxId);
        await sandbox.destroy();
        return Response.json({ sandboxId, destroyed: true });
      }

      return Response.json({ error: 'Use POST to create or DELETE to destroy a sandbox.' }, { status: 405 });
    }

    // Pick a Sandbox instance for this request:
    // 1) header x-sandbox-id
    // 2) query ?sandbox_id=
    // 3) otherwise reject (no implicit default)
    const sandboxId =
      request.headers.get('x-sandbox-id') ??
      url.searchParams.get('sandbox_id');

    if (!sandboxId) {
      return Response.json(
        { error: 'Missing sandbox id. Provide x-sandbox-id header or ?sandbox_id=' },
        { status: 400 }
      );
    }

    const sandbox = getSandbox(env.Sandbox, sandboxId);

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

        const result = await sandbox.exec(command);
        return Response.json(formatExecResult(result));
      }

      // Backwards-compatible demo when called via GET
      const result = await sandbox.exec('python3 -c "print(2 + 2)"');
      return Response.json(formatExecResult(result));
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
        await sandbox.writeFile(path, content);
        return Response.json({ path, length: content.length });
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
          const file = await sandbox.readFile(path);
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
          await sandbox.deleteFile(path);
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
