import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests


DEFAULT_BASE_URL = os.environ.get("SANDBOX_BASE_URL", "http://localhost:8787")


class SandboxClient:
    """
    Lightweight HTTP wrapper around the Sandbox Worker endpoints.

    - All requests must include an explicit sandbox id via `x-sandbox-id`.
    - `base_url` defaults to the local dev server; override when pointing at
      a deployed Worker.
    """

    def __init__(
        self,
        *,
        sandbox_id,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """
        Create a client tied to a specific sandbox instance.

        Args:
            sandbox_id: Required identifier for the target sandbox (header
                `x-sandbox-id` is set on every request).
            base_url: Worker base URL (e.g. http://localhost:8787 for dev).
        """
        if not sandbox_id:
            raise ValueError("sandbox_id is required (set SANDBOX_ID env var or pass explicitly)")

        self.base_url = base_url.rstrip("/")
        self.sandbox_id = sandbox_id
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        # Sandbox Worker now requires an explicit sandbox id (no default fallback).
        return {"x-sandbox-id": self.sandbox_id}

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Low-level request helper that injects headers and base URL."""
        url = f"{self.base_url.rstrip('/')}{path}"
        return self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            stream=stream,
            headers=self._headers(),
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

    def run_test_suite(self, download_path: str = "demo-downloaded.txt") -> None:
        """Convenience method to exercise typical endpoints for manual testing."""
        def dump(resp: requests.Response, label: str) -> None:
            print(f"\n[{label}] {resp.status_code}")
            try:
                print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
            except ValueError:
                print(resp.text)

        dump(self.write("/workspace/demo.txt", "hello sandbox"), "write")
        dump(self.read("/workspace/demo.txt"), "read-hit")
        dump(self.write("/workspace/demo.txt", "v2"), "write-overwrite")
        dump(self.read("/workspace/demo.txt"), "read-after-overwrite")

        dl_resp = self.download("/workspace/demo.txt")
        Path(download_path).write_bytes(dl_resp.content)
        print(f"\n[download] {dl_resp.status_code} saved {download_path} ({len(dl_resp.content)} bytes)")

        dump(self.run("ls -la /workspace"), "run-ls")
        dump(self.delete("/workspace/demo.txt"), "delete-existing")
        dump(self.delete("/workspace/demo.txt"), "delete-missing")
        dump(self.read("/workspace/missing.txt"), "read-missing")



def test_multiple_sandboxes() -> None:
    """
    IDs are normalized to lowercase to avoid preview URL casing warnings.
    """
    sandbox_ids = ["a","b"]
    if not sandbox_ids:
        raise ValueError("No sandbox ids provided. Set SANDBOX_IDS or edit defaults.")

    for sid in sandbox_ids:
        print(f"\n=== Running suite for sandbox: {sid} ===")
        client = SandboxClient(sandbox_id=sid)
        client.run_test_suite()


if __name__ == "__main__":
    test_multiple_sandboxes()

