import logging
import os
import uuid
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = os.environ.get("SANDBOX_BASE_URL", "http://localhost:8787")


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
        resp = self._request("PUT", "/file", json_body={"path": path, "content": content})
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
        resp = self._request("GET", "/file", params={"path": path})
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
        return resp.text

    def download(self, path: str) -> bytes:
        """Download a file in this session's context."""
        resp = self._request("GET", "/file", params={"path": path, "mode": "download"}, stream=True)
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
        return resp.content

    def delete(self, path: str) -> None:
        """Delete a file in this session's context."""
        resp = self._request("DELETE", "/file", params={"path": path})
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
        return resp.json()

    def mkdir(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Create a directory in this session."""
        payload = {"path": path, "recursive": recursive}
        resp = self._request("POST", "/mkdir", json_body=payload)
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
        return resp.json()

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists in this session."""
        resp = self._request("GET", "/exists", params={"path": path})
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
        data = resp.json()
        return bool(data.get("exists"))

    def rename(self, old_path: str, new_path: str) -> Dict[str, Any]:
        """Rename a file or directory in this session."""
        payload = {"oldPath": old_path, "newPath": new_path}
        resp = self._request("POST", "/rename", json_body=payload)
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
        return resp.json()

    def move(self, source_path: str, destination_path: str) -> Dict[str, Any]:
        """Move a file to a different directory in this session."""
        payload = {"sourcePath": source_path, "destinationPath": destination_path}
        resp = self._request("POST", "/move", json_body=payload)
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
        return resp.json()

    def unmount_bucket(self, mount_path: str) -> Dict[str, Any]:
        """Unmount a previously mounted bucket in this session."""
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
        return resp.json()

    def run(self, command: str) -> Dict[str, Any]:
        """Execute a command in this session's context."""
        resp = self._request("POST", "/run", json_body={"command": command})
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
        return resp.json()

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
        """
        # Note: This would require a new endpoint or updating the session
        # For now, we'll raise an error indicating this needs server-side support
        raise NotImplementedError(
            "set_env_vars for individual sessions requires server-side support. "
            "Use sandbox.set_env_vars() to set environment variables for the default session."
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
        created_session_id = result.get('sessionId') or session_id
        if not created_session_id:
            raise SandboxError("Server did not return sessionId")
        
        return ExecutionSession(created_session_id, self)

    def _get_session(self, session_id: str) -> ExecutionSession:
        """Internal method to retrieve an existing session by ID."""
        resp = self._request("GET", "/session", params={"id": session_id})
        if not resp.ok:
            error_msg = f"Failed to get session '{session_id}'"
            try:
                error_detail = resp.text
            except:
                error_detail = None
            raise SandboxError(
                error_msg,
                status_code=resp.status_code,
                response_text=error_detail
            )
        
        return ExecutionSession(session_id, self)

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
            print("get session: server auto-creates, so _get_session should succeed if it exists")
            return self._get_session(session_id)
        except SandboxError as e:
            if e.status_code == 404:
                print("create session")
                return self._create_session(session_id=session_id, env=env, cwd=cwd)
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
        
        resp = self._request("DELETE", "/session", json_body={"sessionId": session_id})
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
        
        return resp.json()

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
    def __init__(self,base_url: str = DEFAULT_BASE_URL):
        # Cache sandbox_id -> Sandbox instance to reuse the same handle
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

        resp = self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            stream=stream,
            headers=self._headers(sandbox_id),
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
        
        Returns a Sandbox instance on success.
        Raises SandboxError if the operation fails.
        
        Example:
            sandbox = manager.create_sandbox("my-id")
            sandbox.write("/path/to/file", "content")
        """
        resp = self._request("POST", "/sandbox", json_body={"sandboxId": sandbox_id, "options": options})
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
        
        Raises SandboxError if the operation fails.
        """
        resp = self._request("DELETE", "/sandbox", params={"sandbox_id": sandbox_id}, sandbox_id=sandbox_id)
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
