import base64
import logging
import os
import socket
import uuid
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)
current_dir = os.path.dirname(os.path.abspath(__file__))
from dotenv import load_dotenv
env_path = os.path.join(current_dir, ".env")
if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"[INFO] Loaded .env file from: {env_path}")


DEFAULT_BASE_URL = os.environ.get("SANDBOX_BASE_URL", "http://localhost:8787")
print(f"当前环境为:{DEFAULT_BASE_URL}")
#TODO：明天看这里
#https://dash.cloudflare.com/7ec35f2d4003f9c8aa6fb3707fca7016/r2/default/buckets/test/settings
#https://claude.ai/chat/cd236071-8a53-4461-a6e9-f67244025f75
#https://chat.deepseek.com/a/chat/s/31cce431-6c19-45d6-8792-ef19c121d324


def detect_clash_proxy() -> Optional[Dict[str, str]]:
    """
    自动检测 Clash 代理是否可用。
    
    Clash 默认端口：
    - HTTP 代理：7890
    - SOCKS5 代理：7891
    
    Returns:
        如果检测到可用的代理，返回代理配置字典，否则返回 None
    """
    # 常见的 Clash 代理端口
    proxy_configs = [
        {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"},  # HTTP 代理
        {"http": "socks5://127.0.0.1:7891", "https": "socks5://127.0.0.1:7891"},  # SOCKS5 代理
        {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"},  # 备用 HTTP 端口
    ]
    
    # 首先检查环境变量中的代理设置
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    
    if http_proxy or https_proxy:
        proxy_config = {
            "http": http_proxy or https_proxy,
            "https": https_proxy or http_proxy
        }
        logger.info(f"Using proxy from environment variables: {proxy_config}")
        return proxy_config
    
    # 检测 Clash 代理端口是否开放
    for proxy_config in proxy_configs:
        try:
            # 尝试连接代理端口
            proxy_url = proxy_config["http"].replace("http://", "").replace("socks5://", "").replace("https://", "")
            host, port = proxy_url.split(":")
            port = int(port)
            
            # 快速检查端口是否开放
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:  # 端口开放
                # 进一步测试代理是否可用
                try:
                    test_session = requests.Session()
                    test_session.proxies = proxy_config
                    # 使用一个简单的测试请求验证代理
                    test_response = test_session.get(
                        "http://www.google.com",
                        timeout=3,
                        allow_redirects=False
                    )
                    if test_response.status_code in [200, 301, 302]:
                        logger.info(f"Detected and verified Clash proxy: {proxy_config}")
                        return proxy_config
                except:
                    # 如果测试失败，继续尝试下一个配置
                    continue
        except Exception as e:
            logger.debug(f"Failed to check proxy {proxy_config}: {e}")
            continue
    
    logger.info("No Clash proxy detected")
    return None


def configure_proxy(session: requests.Session, proxy: Optional[Dict[str, str]] = None) -> bool:
    """
    配置 requests session 的代理设置。
    
    Args:
        session: requests.Session 实例
        proxy: 代理配置字典，如果为 None 则自动检测
        
    Returns:
        如果成功配置代理返回 True，否则返回 False
    """
    if proxy is None:
        proxy = detect_clash_proxy()
    
    if proxy:
        session.proxies.update(proxy)
        logger.info(f"Proxy configured: {proxy}")
        return True
    
    return False

class SandboxError(Exception):
    """Exception raised when sandbox operations fail."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ExecutionSession:
    """
    Execution context bound to a specific session.
    Sessions isolate execution state (cwd/env/process). The filesystem is shared
    within the same sandbox; sessionId is used to reuse that session's cwd/env
    when resolving paths or running commands.
    """

    def __init__(self, session_id: str, sandbox: "Sandbox"):
        self.session_id = session_id
        self.sandbox = sandbox

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Delegate to sandbox's request method, injecting session_id."""
        # Create copies to avoid modifying original dictionaries
        final_json_body = dict(json_body) if json_body else {}
        final_params = dict(params) if params else {}
        
        # For POST/PUT requests, add sessionId to body
        if method in ('POST', 'PUT'):
            final_json_body['sessionId'] = self.session_id
        # For GET/DELETE requests, add sessionId to params
        elif method in ('GET', 'DELETE'):
            final_params['sessionId'] = self.session_id
        

        logger.info(
            "[client][session] request",
            extra={
                "sessionId": self.session_id,
                "method": method,
                "path": path,
                "params": final_params,
                "json": final_json_body,
            },
        )

        resp = self.sandbox._request(
            method,
            path,
            params=final_params if final_params else None,
            json_body=final_json_body if final_json_body else None,
            stream=stream,
        )
        logger.info(
            "[client][session] response",
            extra={
                "sessionId": self.session_id,
                "method": method,
                "path": path,
                "status": resp.status_code,
            },
        )

        return resp

    def write(self, path: str, content: str) -> None:
        """Write a file in this session's context."""
        resp = self._request("POST", "/files/write", json_body={"path": path, "content": content})
        if not resp.ok:
            error_msg = f"Failed to write file '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )

    def read(self, path: str) -> str:
        """Read a file in this session's context."""
        resp = self._request("GET", "/files/read", params={"path": path})
        if not resp.ok:
            error_msg = f"Failed to read file '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {content: ...}, message, code}
        if isinstance(result, dict) and 'data' in result:
            return result['data'].get('content', '')
        return result.get('content', '') if isinstance(result, dict) else resp.text

    def download(self, path: str) -> bytes:
        """Download a file in this session's context."""
        # Server doesn't have a separate download endpoint, use read with base64 encoding
        resp = self._request("GET", "/files/read", params={"path": path, "encoding": "base64"})
        if not resp.ok:
            error_msg = f"Failed to download file '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {content: <base64>}, message, code}
        if isinstance(result, dict) and 'data' in result:
            content = result['data'].get('content', '')
        else:
            content = result.get('content', '') if isinstance(result, dict) else ''
        return base64.b64decode(content)

    def delete(self, path: str) -> None:
        """Delete a file in this session's context."""
        resp = self._request("DELETE", "/files/delete", params={"path": path})
        if not resp.ok:
            error_msg = f"Failed to delete file '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )

    def mount_bucket(self, bucket: str, mount_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Mount an S3-compatible bucket at mount_path within this session."""
        payload = {
            "bucket": bucket,
            "mountPath": mount_path,
            "options": options
        }
        resp = self._request("POST", "/mount-bucket", json_body=payload)
        if not resp.ok:
            error_msg = f"Failed to mount bucket '{bucket}' to '{mount_path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def mkdir(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Create a directory in this session."""
        payload = {"path": path, "recursive": recursive}
        resp = self._request("POST", "/files/mkdir", json_body=payload)
        if not resp.ok:
            error_msg = f"Failed to create directory '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists in this session."""
        resp = self._request("GET", "/files/exists", params={"path": path})
        if not resp.ok:
            error_msg = f"Failed to check existence for '{path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {exists: ...}, message, code}
        if isinstance(result, dict) and 'data' in result:
            return bool(result['data'].get("exists", False))
        return bool(result.get("exists", False))

    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename a file or directory in this session."""
        payload = {"oldPath": old_path, "newPath": new_path}
        resp = self._request("POST", "/files/rename", json_body=payload)
        if not resp.ok:
            error_msg = f"Failed to rename '{old_path}' to '{new_path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def move(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Move a file to a different directory in this session."""
        payload = {"sourcePath": source_path, "destPath": destination_path}
        resp = self._request("POST", "/files/move", json_body=payload)
        if not resp.ok:
            error_msg = f"Failed to move '{source_path}' to '{destination_path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def unmount_bucket(self, mount_path: str) -> Dict[str, Any]:
        """Unmount a previously mounted bucket in this session."""
        # Server accepts mountPath in query params for DELETE
        resp = self._request("DELETE", "/unmount-bucket", params={"mountPath": mount_path})
        if not resp.ok:
            error_msg = f"Failed to unmount bucket at '{mount_path}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def run(self, command: str) -> Dict[str, Any]:
        """Execute a command in this session's context."""
        # Use /session/exec for session-based execution
        resp = self._request("POST", "/session/exec", json_body={"command": command})
        if not resp.ok:
            error_msg = f"Failed to run command '{command}' in session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {result: {...}}, message, code}
        if isinstance(result, dict) and 'data' in result:
            return result['data'].get('result', result['data'])
        return result.get('result', result)

    def run_script(
        self,
        script_path_or_content: str,
        interpreter: str = "python3",
        sandbox_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a script in this session's context.
        
        Args:
            script_path_or_content: Local file path or script content string.
            interpreter: The interpreter to use (e.g., 'python3', 'bash', 'node').
            sandbox_path: Optional path in the sandbox where the script should be saved.
        
        Returns:
            A dictionary containing the execution result.
        """
        # Check if script_path_or_content is a valid file path
        script_content: str
        if os.path.isfile(script_path_or_content):
            try:
                with open(script_path_or_content, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            except Exception as e:
                raise SandboxError(
                    f"Failed to read script file '{script_path_or_content}': {str(e)}"
                )
        else:
            script_content = script_path_or_content
        
        # Determine sandbox path if not provided
        if not sandbox_path:
            if os.path.isfile(script_path_or_content):
                local_filename = os.path.basename(script_path_or_content)
                if not local_filename or '.' not in local_filename:
                    ext_map = {
                        'python3': '.py',
                        'python': '.py',
                        'bash': '.sh',
                        'sh': '.sh',
                        'node': '.js',
                        'nodejs': '.js'
                    }
                    ext = ext_map.get(interpreter, '.txt')
                    local_filename = f'script{ext}'
                sandbox_path = f"/workspace/{local_filename}"
            else:
                ext_map = {
                    'python3': '.py',
                    'python': '.py',
                    'bash': '.sh',
                    'sh': '.sh',
                    'node': '.js',
                    'nodejs': '.js'
                }
                ext = ext_map.get(interpreter, '.txt')
                sandbox_path = f"/workspace/script-{uuid.uuid4()}{ext}"
        
        # Upload script to sandbox (in this session's context)
        self.write(sandbox_path, script_content)
        
        # Determine command based on interpreter
        if interpreter in ('python3', 'python'):
            command = f"python3 {sandbox_path}"
        elif interpreter in ('bash', 'sh'):
            command = f"bash {sandbox_path}"
        elif interpreter in ('node', 'nodejs'):
            command = f"node {sandbox_path}"
        else:
            command = f"{interpreter} {sandbox_path}"
        
        # Execute the script
        result = self.run(command)
        
        # Add metadata to result
        result['scriptPath'] = sandbox_path
        result['interpreter'] = interpreter
        result['localPath'] = script_path_or_content if os.path.isfile(script_path_or_content) else None
        result['sessionId'] = self.session_id
        
        return result

    def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """
        Set environment variables for this session.
        
        Args:
            env_vars: Dictionary of environment variable key-value pairs.
        
        Raises:
            SandboxError if the operation fails.
        
        Example:
            session = sandbox.create_session("my-session")
            session.set_env_vars({
                "API_KEY": "secret-key",
                "NODE_ENV": "production"
            })
        """
        if not isinstance(env_vars, dict):
            raise ValueError("env_vars must be a dictionary")
        
        # Validate all values are strings
        for key, value in env_vars.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"env_vars must contain only string key-value pairs, got {type(key).__name__}:{type(value).__name__}")
        
        resp = self._request("POST", "/session/env", json_body={"envVars": env_vars})
        if not resp.ok:
            error_msg = f"Failed to set environment variables for session '{self.session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
        )


class Sandbox:
    """View over a single sandbox; requests are delegated to the manager and operations default to the default session."""

    def __init__(self, sandbox_id: str, manager: "SandboxManager"):
        self.sandbox_id = sandbox_id
        self._manager = manager
        self._default_session: Optional[ExecutionSession] = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """Delegate to manager while injecting the current sandbox id."""
        return self._manager._request(
            method,
            path,
            params=params,
            json_body=json_body,
            stream=stream,
            sandbox_id=self.sandbox_id,
        )

    @property
    def _default(self) -> ExecutionSession:
        """Lazily get the default session."""
        if self._default_session is None:
            self._default_session = ExecutionSession("default", self)
        return self._default_session

    def write(self, path: str, content: str) -> None:
        """
        Create or overwrite a file at `path` with `content` (in default session).
        
        Raises SandboxError if the operation fails.
        """
        self._default.write(path, content)

    def read(self, path: str) -> str:
        """
        Read a file at `path` and return its content as a string (from default session).
        
        Raises SandboxError if the operation fails.
        """
        return self._default.read(path)

    def download(self, path: str) -> bytes:
        """
        Download a file at `path` as bytes (from default session).
        
        Raises SandboxError if the operation fails.
        """
        return self._default.download(path)

    def delete(self, path: str) -> None:
        """
        Delete a file at `path` (in default session).
        
        Raises SandboxError if the operation fails.
        """
        self._default.delete(path)

    def mkdir(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Create a directory at `path` (default session)."""
        return self._default.mkdir(path, recursive)

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists (default session)."""
        return self._default.exists(path)

    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename a file or directory (default session)."""
        return self._default.rename(old_path, new_path)

    def move(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Move a file or directory (default session)."""
        return self._default.move(source_path, destination_path)

    def mount_bucket(self, bucket: str, mount_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mount an S3-compatible bucket to a path within the sandbox (default session).
        
        Args:
            bucket: Bucket name.
            mount_path: Mount point inside the sandbox (e.g., "/data").
            options: Dict including at least "endpoint"; may contain credentials/readOnly/etc.
        """
        return self._default.mount_bucket(bucket, mount_path, options)

    def unmount_bucket(self, mount_path: str) -> Dict[str, Any]:
        """
        Unmount a previously mounted bucket from the sandbox (default session).
        """
        return self._default.unmount_bucket(mount_path)

    def run(self, command: str) -> Dict[str, Any]:
        """
        Execute a shell command inside the sandbox container (in default session).
        
        Returns a dictionary containing the command execution result.
        Raises SandboxError if the operation fails.
        """
        return self._default.run(command)

    def run_script(
        self,
        script_path_or_content: str,
        interpreter: str = "python3",
        sandbox_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a script by uploading it from a local file path and running it with the specified interpreter (in default session).
        
        Args:
            script_path_or_content: Local file path to the script file, or script content as string.
                                   If it's a valid file path, the file will be read and uploaded.
                                   Otherwise, it will be treated as script content.
            interpreter: The interpreter to use (e.g., 'python3', 'bash', 'node'). Defaults to 'python3'.
            sandbox_path: Optional path in the sandbox where the script should be saved. 
                         If not provided, a temporary path will be used.
        
        Returns:
            A dictionary containing the execution result, including:
            - output: stdout content
            - error: stderr content
            - exitCode: exit code
            - success: whether execution succeeded
            - scriptPath: path in sandbox where the script was saved
            - interpreter: interpreter used
        
        Raises:
            SandboxError if the operation fails.
            FileNotFoundError if the local file path doesn't exist.
        
        Example:
            # From local file
            result = sandbox.run_script("./my_script.py", interpreter="python3")
            print(result['output'])
            
            # From script content (backwards compatible)
            result = sandbox.run_script("print('Hello, World!')", interpreter="python3")
            print(result['output'])
        """
        return self._default.run_script(script_path_or_content, interpreter, sandbox_path)

    def _create_session(
        self,
        session_id: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ) -> ExecutionSession:
        """Internal method to create a new isolated execution session."""
        json_body: Dict[str, Any] = {}
        if session_id:
            json_body['id'] = session_id
        if env:
            json_body['env'] = env
        if cwd:
            json_body['cwd'] = cwd
        
        resp = self._request("POST", "/session", json_body=json_body)
        if not resp.ok:
            error_msg = f"Failed to create session"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        
        result = resp.json()
        # Server returns {data: {sessionId: ...}, message, code}
        data = result.get('data', result) if isinstance(result, dict) and 'data' in result else result
        created_session_id = data.get('sessionId') or session_id
        if not created_session_id:
            raise SandboxError("Server did not return sessionId")
        
        return ExecutionSession(created_session_id, self)

    # def _get_session(self, session_id: str) -> ExecutionSession:
    #     """Internal method to retrieve an existing session by ID."""
    #     # Server doesn't have a GET /session endpoint, but sessions are auto-created
    #     # So we can just return the session - it will be created on first use
    #     # Alternatively, try to create it and handle "already exists" error
    #     try:
    #         return self._create_session(session_id=session_id)
    #     except SandboxError as e:
    #         # If session already exists (409), return the session
    #         if e.status_code == 409:
    #             return ExecutionSession(session_id, self)
    #         raise

    def create_or_get_session(
        self,
        session_id: str,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ) -> ExecutionSession:
        """
        Create a session if it doesn't exist, or get it if it does.
        
        Args:
            session_id: ID of the session to create or get.
            env: Environment variables for this session (only used if creating).
            cwd: Working directory (only used if creating).
        
        Returns:
            ExecutionSession bound to the specified session.
        
        Example:
            # Get or create a session
            session = sandbox.create_or_get_session("user-123")
            session.run("npm run build")
            
            # Create a session with custom environment
            session = sandbox.create_or_get_session(
                session_id="prod",
                env={"NODE_ENV": "production"},
                cwd="/workspace/prod"
            )
        """
        try:
                print("create session")
                return self._create_session(session_id=session_id, env=env, cwd=cwd)

        except SandboxError as e:

            raise

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """
        Delete a session and clean up its resources.
        
        Args:
            session_id: ID of the session to delete (cannot be "default").
        
        Returns:
            Dictionary containing success status, sessionId, and timestamp.
        
        Example:
            # Create and clean up a temporary session
            session = sandbox.create_or_get_session(session_id="temp-task")
            try:
                session.run("npm run heavy-task")
            finally:
                sandbox.delete_session("temp-task")
        """
        if session_id == "default":
            raise SandboxError("Cannot delete default session. Use destroy() to terminate the sandbox.")
        
        # Server expects session_id as query parameter for DELETE
        resp = self._request("DELETE", "/session", params={"session_id": session_id})
        if not resp.ok:
            error_msg = f"Failed to delete session '{session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        result = resp.json()
        # Server returns {data: {...}, message, code}
        return result.get('data', result) if isinstance(result, dict) and 'data' in result else result

    def destroy_all_sessions(self, continue_on_error: bool = False) -> Dict[str, Any]:
        """
        Destroy all sessions in this sandbox (except the "default" session).
        
        Args:
            continue_on_error: If True, continue destroying other sessions even if one fails.
                             If False, raise SandboxError on the first failure.
        
        Returns:
            A dictionary with 'destroyed' (list of successfully destroyed IDs) and 
            'failed' (list of tuples: (session_id, error_message)).
        
        Raises:
            SandboxError: If continue_on_error is False and any session destruction fails.
        
        Example:
            # Clean up all sessions
            result = sandbox.destroy_all_sessions()
            print(f"Destroyed {result['success_count']} sessions")
        """
        # Try to get list of all sessions from underlying container API
        session_ids = []
        try:
            # Try to access underlying container API directly
            # This assumes the server proxies requests to the container
            resp = self._request("GET", "/api/session/list")
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict) and 'data' in data:
                    session_ids = data['data']
                elif isinstance(data, list):
                    session_ids = data
        except Exception:
            # If we can't get the list, we'll just try to delete known sessions
            # or return empty result
            pass
        
        # Filter out "default" session
        session_ids = [sid for sid in session_ids if sid != "default"]
        
        destroyed = []
        failed = []
        
        for session_id in session_ids:
            try:
                self.delete_session(session_id)
                destroyed.append(session_id)
            except SandboxError as e:
                error_info = (session_id, str(e))
                failed.append(error_info)
                if not continue_on_error:
                    raise
            except Exception as e:
                error_info = (session_id, f"Unexpected error: {str(e)}")
                failed.append(error_info)
                if not continue_on_error:
                    raise SandboxError(f"Failed to destroy session '{session_id}': {str(e)}")
        
        return {
            "destroyed": destroyed,
            "failed": failed,
            "total": len(session_ids),
            "success_count": len(destroyed),
            "failure_count": len(failed)
        }

    def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """
        Set environment variables in the sandbox (for the default session).
        
        Warning: Call this BEFORE any other sandbox operations to ensure 
        environment variables are available from the start.
        
        Args:
            env_vars: Key-value pairs of environment variables to set.
        
        Example:
            sandbox.set_env_vars({
                "API_KEY": "secret-key",
                "NODE_ENV": "production"
            })
            sandbox.run("python script.py")
        """
        self._default.set_env_vars(env_vars)


class SandboxManager:
    """Manage CRUD operations for all sandboxes."""
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        proxy: Optional[Dict[str, str]] = None,
        auto_detect_proxy: bool = True
    ):
        """
        初始化 SandboxManager。
        
        Args:
            base_url: 服务器基础 URL
            timeout: 请求超时时间（秒）
            proxy: 代理配置字典，格式: {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
            auto_detect_proxy: 是否自动检测 Clash 代理（默认 True）
        """
        # Cache sandbox_id -> Sandbox instance to reuse the same handle
        self._sandboxes: Dict[str, Sandbox] = {}
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        
        # 配置代理
        if proxy:
            self.session.proxies.update(proxy)
            logger.info(f"Using provided proxy: {proxy}")
        elif auto_detect_proxy:
            configure_proxy(self.session)


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
        # Extra console logs (opt-in)

        logger.info(
            "[client][manager] request",
            extra={
                "sandboxId": sandbox_id,
                "method": method,
                "url": url,
                "params": params,
                "json": json_body,
                "stream": stream,
            },
        )

        try:
            resp = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                stream=stream,
                headers=self._headers(sandbox_id),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            logger.error(
                "[client][manager] request timeout",
                extra={
                    "sandboxId": sandbox_id,
                    "method": method,
                    "url": url,
                    "timeout": self.timeout,
                },
            )
            raise SandboxError(
                f"Request to {url} timed out after {self.timeout} seconds. "
                "This might be a network connectivity issue or the server is not responding.",
                status_code=None,
                response_text=str(e)
            )
        except requests.exceptions.ConnectionError as e:
            logger.error(
                "[client][manager] connection error",
                extra={
                    "sandboxId": sandbox_id,
                    "method": method,
                    "url": url,
                },
            )
            raise SandboxError(
                f"Failed to connect to {url}. "
                "Please check your network connection and ensure the server is accessible. "
                "If you're behind a proxy, configure it via environment variables (HTTP_PROXY/HTTPS_PROXY).",
                status_code=None,
                response_text=str(e)
            )
        except requests.exceptions.RequestException as e:
            logger.error(
                "[client][manager] request error",
                extra={
                    "sandboxId": sandbox_id,
                    "method": method,
                    "url": url,
                },
            )
            raise SandboxError(
                f"Request to {url} failed: {str(e)}",
                status_code=None,
                response_text=str(e)
        )
        logger.info(
            "[client][manager] response",
            extra={
                "sandboxId": sandbox_id,
                "method": method,
                "url": url,
                "status": resp.status_code,
            },
        )

        return resp

    def create_or_get_sandbox(
        self, sandbox_id, options: Optional[Dict[str, Any]] = None
    ) -> Sandbox:
        """
        Create (or ensure) a sandbox.
        
        If the sandbox already exists in the local cache, returns it directly.
        Otherwise, creates it on the server and caches it.
        
        Returns a Sandbox instance on success.
        Raises SandboxError if the operation fails.
        
        Example:
            sandbox = manager.create_or_get_sandbox("my-id")
            sandbox.write("/path/to/file", "content")
        """
        # Check if sandbox already exists in local cache
        # if sandbox_id in self._sandboxes:
        #     return self._sandboxes[sandbox_id]
        
        # Server uses /lifecycle endpoint for sandbox creation 备注: 服务端创建sandbox 若有缓存直接返回执行命令
        resp = self._request("POST", "/lifecycle", json_body={"options": options}, sandbox_id=sandbox_id)
        if not resp.ok:
            error_msg = f"Failed to create sandbox '{sandbox_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        return self._append_id(sandbox_id)

    def destroy_sandbox(self, sandbox_id) -> None:
        """
        Destroy a sandbox by id.
        
        If the sandbox is not in the local cache, returns immediately.
        Otherwise, destroys it on the server and removes it from cache.
        
        Raises SandboxError if the operation fails.
        """
        # # Check if sandbox exists in local cache TODO：若客户端断开链接，服务端的sandbox就一直删不了了。。。。
        # if sandbox_id not in self._sandboxes:
        #     return
        
        # Server uses /lifecycle endpoint for sandbox destruction
        resp = self._request("DELETE", "/lifecycle", sandbox_id=sandbox_id)
        if not resp.ok:
            error_msg = f"Failed to destroy sandbox '{sandbox_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        self._remove_id(sandbox_id)

    def destroy_all_sandboxes(self, continue_on_error: bool = False) -> Dict[str, Any]:
        """
        Destroy all sandboxes that are currently tracked by this manager.
        
        Args:
            continue_on_error: If True, continue destroying other sandboxes even if one fails.
                             If False, raise SandboxError on the first failure.
        
        Returns:
            A dictionary with 'destroyed' (list of successfully destroyed IDs) and 
            'failed' (list of tuples: (sandbox_id, error_message)).
        
        Raises:
            SandboxError: If continue_on_error is False and any sandbox destruction fails.
        """
        sandbox_ids = list(self._sandboxes.keys())
        destroyed = []
        failed = []
        
        for sandbox_id in sandbox_ids:
            try:
                self.destroy_sandbox(sandbox_id)
                destroyed.append(sandbox_id)
            except SandboxError as e:
                error_info = (sandbox_id, str(e))
                failed.append(error_info)
                if not continue_on_error:
                    raise
            except Exception as e:
                error_info = (sandbox_id, f"Unexpected error: {str(e)}")
                failed.append(error_info)
                if not continue_on_error:
                    raise SandboxError(f"Failed to destroy sandbox '{sandbox_id}': {str(e)}")
        
        return {
            "destroyed": destroyed,
            "failed": failed,
            "total": len(sandbox_ids),
            "success_count": len(destroyed),
            "failure_count": len(failed)
        }
