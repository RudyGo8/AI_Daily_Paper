"""GitHub Contents API persistence on a dedicated branch, one file per topic."""
from __future__ import annotations

import base64
import binascii
import copy
import json
import re
from urllib.parse import quote

import requests

from src.storage.history import history_timestamp, validate_history_state


class GitHubStateStore:
    def __init__(self, repository: str, token: str, branch: str, topic: str, timeout: int = 15) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("Invalid GitHub history repository")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", topic):
            raise ValueError("Invalid GitHub history topic")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or any(
                segment in ("", ".", "..") or segment.endswith(".lock") for segment in branch.split("/")) or ".." in branch:
            raise ValueError("Invalid GitHub history branch")
        self.repository = repository
        self.branch = branch
        self.topic = topic
        self.timeout = timeout
        self._baseline: dict | None = None
        self._base = f"https://api.github.com/repos/{repository}"
        self._contents = f"/contents/history/{topic}.json"
        self._ref = "/git/ref/heads/" + quote(branch, safe="/")
        self._headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-daily-paper/2",
                         "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _request(self, method: str, path: str, *, allowed: tuple[int, ...] = (), **kwargs) -> requests.Response:
        try:
            response = requests.request(method, self._base + path, headers=self._headers,
                                        timeout=self.timeout, **kwargs)
        except requests.RequestException:
            raise RuntimeError("GitHub history request failed") from None
        if response.status_code not in (200, 201, *allowed):
            raise RuntimeError(f"GitHub history request failed (HTTP {response.status_code})")
        return response

    @staticmethod
    def _json(response: requests.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            raise ValueError("Invalid GitHub history API response") from None
        if not isinstance(body, dict):
            raise ValueError("Invalid GitHub history API response")
        return body

    def _read_file(self) -> tuple[dict | None, str | None]:
        response = self._request("GET", self._contents, allowed=(404,), params={"ref": self.branch})
        if response.status_code == 404:
            return None, None
        body = self._json(response)
        if (body.get("type") != "file" or body.get("encoding") != "base64"
                or not isinstance(body.get("sha"), str) or not body["sha"]
                or not isinstance(body.get("content"), str)):
            raise ValueError("Invalid GitHub history file metadata")
        try:
            encoded = "".join(body["content"].split())
            state = json.loads(base64.b64decode(encoded, validate=True).decode("utf-8"))
        except (KeyError, AttributeError, ValueError, UnicodeError, binascii.Error):
            raise ValueError("Invalid GitHub history file content") from None
        return validate_history_state(state), body["sha"]

    def load(self) -> dict | None:
        state, _ = self._read_file()
        if state is None:
            # A contents 404 can also hide an inaccessible repository. Check access
            # before treating a missing file/branch as a normal first run.
            self._request("GET", "")
            self._request("GET", self._ref, allowed=(404,))
        self._baseline = copy.deepcopy(state) if state is not None else {"version": 1, "sent": {}, "stars": {}}
        return state

    def _ensure_branch(self) -> None:
        reference = self._request("GET", self._ref, allowed=(404,))
        repository = self._json(self._request("GET", ""))
        default = repository.get("default_branch")
        if not isinstance(default, str) or not default:
            raise ValueError("Invalid GitHub history default branch")
        if self.branch == default:
            raise ValueError("GitHub history cannot overwrite the repository default branch")
        if reference.status_code != 404:
            return
        head = self._json(self._request("GET", "/git/ref/heads/" + quote(default, safe="/")))
        sha = head.get("object", {}).get("sha") if isinstance(head.get("object"), dict) else None
        if not isinstance(sha, str) or not sha:
            raise ValueError("Invalid GitHub history branch head")
        result = self._request("POST", "/git/refs", allowed=(422,),
                               json={"ref": "refs/heads/" + self.branch, "sha": sha})
        if result.status_code == 422:
            # Another topic may have created the same branch. Only accept this
            # validation response when the branch is now readable.
            self._request("GET", self._ref)

    @staticmethod
    def _merge_changes(ours: dict, current: dict, baseline: dict) -> dict:
        """Preserve concurrent additions without resurrecting pruned baseline data."""
        merged = copy.deepcopy(ours)
        for kind in ("sent", "stars"):
            for key, value in current[kind].items():
                if value == baseline[kind].get(key):
                    continue
                own_value = merged[kind].get(key)
                current_at = value if kind == "sent" else value["at"]
                own_at = own_value if kind == "sent" else own_value["at"] if own_value is not None else None
                if own_at is None or history_timestamp(current_at) > history_timestamp(own_at):
                    merged[kind][key] = copy.deepcopy(value)
        return merged

    def save(self, state: dict) -> None:
        desired = validate_history_state(state)
        self._ensure_branch()
        baseline = self._baseline
        for _ in range(3):
            current, sha = self._read_file()
            current = current or {"version": 1, "sent": {}, "stars": {}}
            if baseline is None:
                baseline = current
            else:
                desired = self._merge_changes(desired, current, baseline)
            encoded = base64.b64encode((json.dumps(desired, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")).decode("ascii")
            body = {"message": f"Update {self.topic} history [skip ci]", "branch": self.branch, "content": encoded}
            if sha is not None:
                body["sha"] = sha
            response = self._request("PUT", self._contents, allowed=(409, 422), json=body)
            if response.status_code in (200, 201):
                self._baseline = copy.deepcopy(desired)
                return
        raise RuntimeError("GitHub history update conflict after 3 attempts")
