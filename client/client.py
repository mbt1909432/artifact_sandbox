import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests


DEFAULT_BASE_URL = os.environ.get("SANDBOX_BASE_URL", "http://localhost:8787")

class Sandbox:
    """单个 sandbox 的视图，实际请求交由 manager 负责。"""

    def __init__(self, sandbox_id: str, manager: "SandboxManager"):
        self.sandbox_id = sandbox_id
        self._manager = manager

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Delegate to manager while注入当前 sandbox id。"""
        return self._manager._request(
            method,
            path,
            params=params,
            json_body=json_body,
            stream=stream,
            sandbox_id=self.sandbox_id,
        )

    def write(self, path: str, content: str) -> requests.Response:
        """Create or overwrite a file at `path` with `content`."""
        return self._request("PUT", "/file", json_body={"path": path, "content": content})

    def read(self, path: str) -> requests.Response:
        """Read a file at `path`."""
        return self._request("GET", "/file", params={"path": path})

    def download(self, path: str) -> requests.Response:
        """Download a file at `path` as bytes (streaming)."""
        return self._request("GET", "/file", params={"path": path, "mode": "download"}, stream=True)

    def delete(self, path: str) -> requests.Response:
        """Delete a file at `path`."""
        return self._request("DELETE", "/file", params={"path": path})

    def run(self, command: str) -> requests.Response:
        """Execute a shell command inside the sandbox container."""
        return self._request("POST", "/run", json_body={"command": command})




class SandboxManager:
    "管理所有sandbox crud"
    def __init__(self,base_url: str = DEFAULT_BASE_URL):
        # 缓存 sandbox_id -> Sandbox 实例，便于复用同一个 handle
        self._sandboxes: Dict[str, Sandbox] = {}
        self.base_url = base_url
        self.session = requests.Session()


    def _append_id(self, sandbox_id: str) -> Sandbox:
        """Ensure a Sandbox instance is cached for the given id and return it."""
        if sandbox_id not in self._sandboxes:
            self._sandboxes[sandbox_id] = Sandbox(sandbox_id, self)
        return self._sandboxes[sandbox_id]

    def _remove_id(self, sandbox_id: str) -> None:
        """Stop tracking a sandbox id and drop its cached Sandbox handle."""
        self._sandboxes.pop(sandbox_id, None)

    def _headers(self, sandbox_id: Optional[str] = None) -> Dict[str, str]:
        if not sandbox_id:
            return {}
        return {"x-sandbox-id": sandbox_id}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        sandbox_id: Optional[str] = None,
    ) -> requests.Response:
        """Low-level request helper that injects headers and base URL."""
        url = f"{self.base_url.rstrip('/')}{path}"
        return self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            stream=stream,
            headers=self._headers(sandbox_id),
        )

    def create_sandbox(
        self, sandbox_id, options: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """Create (or ensure) a sandbox; returns the id."""
        resp = self._request("POST", "/sandbox", json_body={"sandboxId": sandbox_id, "options": options})
        if resp.ok:
            self._append_id(sandbox_id)
        return resp

    def destroy_sandbox(self, sandbox_id) -> requests.Response:
        """Destroy a sandbox by id."""
        resp = self._request("DELETE", "/sandbox", params={"sandbox_id": sandbox_id}, sandbox_id=sandbox_id)
        if resp.ok:
            self._remove_id(sandbox_id)
        return resp

    def get_sandbox(self, sandbox_id: str, ensure: bool = False, options: Optional[Dict[str, Any]] = None) -> Sandbox:
        """
        Return a Sandbox handle bound to `sandbox_id`.

        Set `ensure=True` to call create_sandbox first (idempotent).
        """
        if ensure:
            self.create_sandbox(sandbox_id, options)
        # 复用已缓存的实例，避免重复创建 handle
        return self._append_id(sandbox_id)





def manager_client2() -> None:
    """
    简单演示 manager + Sandbox 组合用法，便于手工验证接口。

    - 创建/确保 sandbox
    - 写/读/删文件
    - 销毁 sandbox
    """
    manager = SandboxManager()
    sandbox_id = "demo-client2"

    # 确保容器存在
    create_resp = manager.create_sandbox(sandbox_id, options={"keepAlive": True})
    print("create_sandbox", create_resp.status_code, create_resp.text)

    sbx = manager.get_sandbox(sandbox_id)
    print("write", sbx.write("/workspace/hello.txt", "hi from client2").status_code)
    print("read", sbx.read("/workspace/hello.txt").status_code, sbx.read("/workspace/hello.txt").text)
    print("run", sbx.run("ls -la /workspace").status_code)
    print("delete", sbx.delete("/workspace/hello.txt").status_code)

    destroy_resp = manager.destroy_sandbox(sandbox_id)
    print("destroy_sandbox", destroy_resp.status_code, destroy_resp.text)




if __name__ == "__main__":
    manager_client2()

