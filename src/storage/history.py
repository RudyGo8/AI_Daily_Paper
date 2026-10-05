"""Version-aware, per-topic history with atomic local JSON persistence."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

from src.models.schemas import NewsItem


def history_timestamp(value: object) -> datetime:
    """Parse stored timestamps strictly; corrupt history must never become empty."""
    if not isinstance(value, str):
        raise ValueError("Invalid history timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid history timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError("Invalid history timestamp: timezone required")
    return parsed.astimezone(timezone.utc)


def validate_history_state(state: object) -> dict:
    """Return a defensive copy of a supported, fully validated state."""
    if not isinstance(state, dict) or set(state) != {"version", "sent", "stars"}:
        raise ValueError("Invalid history state structure")
    if type(state["version"]) is not int or state["version"] != 1:
        raise ValueError("Unsupported history version")
    if not isinstance(state["sent"], dict) or not isinstance(state["stars"], dict):
        raise ValueError("Invalid history records")
    for key, timestamp in state["sent"].items():
        if not isinstance(key, str) or not key:
            raise ValueError("Invalid history fingerprint")
        history_timestamp(timestamp)
    for repository, snapshot in state["stars"].items():
        if not isinstance(repository, str) or not repository or not isinstance(snapshot, dict):
            raise ValueError("Invalid history star snapshot")
        if type(snapshot.get("stars")) is not int or snapshot["stars"] < 0:
            raise ValueError("Invalid history star count")
        history_timestamp(snapshot.get("at"))
    return copy.deepcopy(state)


def _text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def _title(value: str) -> str:
    return re.sub(r"[^\w]+", "", _text(value))


def _link(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if "://" in raw else "https://" + raw)
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port and port not in (80, 443):
        host += f":{port}"
    query = [(key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "mc_cid", "mc_eid"}]
    suffix = "?" + urlencode(sorted(query)) if query else ""
    return host + parsed.path.rstrip("/") + suffix


def _digest(parts: list[str]) -> str:
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _fingerprints(item: NewsItem, topic: str) -> set[str]:
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("History topic must be nonempty")
    links = {_link(link) for link in [item.link, *item.merged_links] if link.strip()}
    titles = {_title(title) for title in [item.title, *item.merged_titles] if title.strip()}
    if item.source_type == "github":
        links = {link.casefold() for link in links}
        version = []
        for key in ("release_tag", "release_at", "pushed_at"):
            value = item.metadata.get(key)
            if value and key.endswith("_at"):
                value = history_timestamp(value.isoformat() if isinstance(value, datetime) else value).isoformat()
            version.append(str(value or ""))
        versions = {_digest(version)}
    else:
        versions = {_digest([title, _text(item.summary), _text(item.content)]) for title in titles}
    identities = links or {"title:" + title for title in titles}
    kind = "github" if item.source_type == "github" else "article"
    return {_digest([topic, kind, identity, version])
            for identity in identities for version in versions}


class HistoryStore:
    """History is marked/saved by the caller only after successful publication."""

    def __init__(self, path: Path, retention_days: int = 30, now: datetime | None = None) -> None:
        if type(retention_days) is not int or retention_days <= 0:
            raise ValueError("History retention_days must be a positive integer")
        self.path = Path(path)
        self.retention_days = retention_days
        self.now = now
        self.state: dict = {"version": 1, "sent": {}, "stars": {}}
        self._load_failed = False

    def _now(self) -> datetime:
        current = self.now or datetime.now(timezone.utc)
        return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)

    def _prune(self) -> None:
        cutoff = self._now() - timedelta(days=self.retention_days)
        self.state["sent"] = {key: at for key, at in self.state["sent"].items()
                              if history_timestamp(at) >= cutoff}
        self.state["stars"] = {key: snapshot for key, snapshot in self.state["stars"].items()
                               if history_timestamp(snapshot["at"]) >= cutoff}

    def set_state(self, state: dict) -> None:
        self.state = validate_history_state(state)
        self._prune()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            self.set_state(json.loads(self.path.read_text(encoding="utf-8")))
        except (ValueError, UnicodeError):
            self._load_failed = True
            raise ValueError("Invalid local history; existing file was preserved") from None
        self._load_failed = False

    def is_seen(self, item: NewsItem, topic: str) -> bool:
        self._prune()
        return any(key in self.state["sent"] for key in _fingerprints(item, topic))

    def mark_sent(self, items: list[NewsItem], topic: str) -> None:
        fingerprints = set().union(*(_fingerprints(item, topic) for item in items))
        self._prune()
        at = self._now().isoformat()
        self.state["sent"].update(dict.fromkeys(fingerprints, at))

    def save(self) -> None:
        if self._load_failed:
            raise ValueError("Invalid local history; refusing to overwrite existing file")
        if self.path.exists():
            try:
                validate_history_state(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, UnicodeError):
                raise ValueError("Invalid local history; refusing to overwrite existing file") from None
        self.state = validate_history_state(self.state)
        self._prune()
        payload = json.dumps(self.state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=self.path.name + ".", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
