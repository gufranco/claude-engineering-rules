from __future__ import annotations

import getpass
import json
import os
import pwd
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

LOCAL_LIST = Path(".claude") / "machine-identifiers.txt"
EXEMPT_PREFIX = "!"
DICTIONARY = Path("/usr/share/dict/words")
PROBE_TIMEOUT_S = 2
MIN_TOKEN_LENGTH = 3
MAX_WORKSPACE_ENTRIES = 400
MAX_SESSION_FILES = 200
MAC_TEMP_ROOTS = ("/var/folders/", "/private/var/folders/")
INCLUDE_PREFIX = "includeif."
INCLUDE_SUFFIX = ".path"
ORG_IN_CONDITION = re.compile(r"url:\S*?[:/]([A-Za-z0-9._-]+)/\*\*")
DIR_IN_CONDITION = re.compile(r"gitdir(?:/i)?:\*\*/([^/]+)/")
GH_ACCOUNT = re.compile(r"\baccount (\S+)")
REMOTE_OWNER = re.compile(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$")
SYNC_PRODUCTS = frozenset(
    {"box", "dropbox", "google drive", "icloud drive", "nextcloud", "onedrive", "sync"}
)
GENERIC_FOLDER_WORDS = frozenset(
    {
        "archive",
        "clients",
        "code",
        "desktop",
        "dev",
        "documents",
        "downloads",
        "home",
        "misc",
        "personal",
        "projects",
        "repos",
        "src",
        "sync",
        "test",
        "tmp",
        "work",
        "workspace",
    }
)


class Kind(str, Enum):
    HOME_PATH = "home directory path"
    USERNAME = "login name"
    HOSTNAME = "host name"
    REAL_NAME = "real name"
    EMAIL = "personal email"
    WORKSPACE = "local folder name"
    WINDOW = "terminal window or session name"
    SESSION_ID = "live agent session id"
    TEMP_PATH = "machine temp path"
    ACCOUNT = "other account or organization"
    LISTED = "listed identifier"


@dataclass(frozen=True, slots=True)
class Identifier:
    kind: Kind
    token: str


def probe(args: list[str]) -> str:
    binary = shutil.which(args[0])
    if binary is None:
        return ""
    try:
        done = subprocess.run(
            [binary, *args[1:]], capture_output=True, text=True, timeout=PROBE_TIMEOUT_S
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _dictionary() -> frozenset[str]:
    try:
        words = DICTIONARY.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return frozenset()
    return frozenset(w for w in words.split() if w.islower())


def is_generic(token: str, dictionary: frozenset[str]) -> bool:
    lowered = token.lower()
    singular = lowered.removesuffix("s")
    if len(token) < MIN_TOKEN_LENGTH or lowered in GENERIC_FOLDER_WORDS | SYNC_PRODUCTS:
        return True
    if singular in GENERIC_FOLDER_WORDS or {lowered, singular} & dictionary:
        return True
    return shutil.which(token) is not None


def _host_names() -> list[str]:
    raw = [
        socket.gethostname(),
        *_lines(probe(["scutil", "--get", "ComputerName"])),
        *_lines(probe(["scutil", "--get", "LocalHostName"])),
    ]
    return [name.removesuffix(".local") for name in raw if name]


def _account_name() -> str:
    uid = os.getuid()
    gecos = next((e.pw_gecos for e in pwd.getpwall() if e.pw_uid == uid), "")
    return gecos.split(",")[0].strip()


def _real_names(dictionary: frozenset[str]) -> list[str]:
    git_name = probe(["git", "config", "--global", "user.name"]).strip()
    full = [name for name in (_account_name(), git_name) if " " in name]
    parts = [p for name in full for p in name.split() if not is_generic(p, dictionary)]
    return [*full, *parts]


def _includes() -> list[tuple[str, str]]:
    pattern = r"^includeif\..*\.path$"
    listing = probe(["git", "config", "--global", "-z", "--get-regexp", pattern])
    entries = [entry.split("\n", 1) for entry in listing.split("\0") if "\n" in entry]
    return [(key, value) for key, value in entries]


def _include_paths() -> list[Path]:
    return [Path(os.path.expanduser(value)) for _key, value in _includes()]


def _condition(key: str) -> str:
    return key.removeprefix(INCLUDE_PREFIX).removesuffix(INCLUDE_SUFFIX)


def _accounts(user: str) -> list[str]:
    logins = GH_ACCOUNT.findall(probe(["gh", "auth", "status"]))
    conditions = [_condition(key) for key, _value in _includes()]
    orgs = [m for c in conditions for m in ORG_IN_CONDITION.findall(c)]
    folders = [m for c in conditions for m in DIR_IN_CONDITION.findall(c)]
    return [name for name in (*logins, *orgs, *folders) if name.lower() != user.lower()]


def repo_owner(repo: Path) -> str:
    url = probe(["git", "-C", str(repo), "remote", "get-url", "origin"]).strip()
    match = REMOTE_OWNER.search(url)
    return match.group(1).lower() if match else ""


def _emails_in(path: Path) -> list[str]:
    return _lines(
        probe(["git", "config", "--file", str(path), "--get-all", "user.email"])
    )


def _emails() -> list[str]:
    direct = _lines(probe(["git", "config", "--global", "--get-all", "user.email"]))
    included = [e for path in _include_paths() for e in _emails_in(path)]
    return [e for e in (*direct, *included) if "noreply" not in e]


def _children(path: Path) -> list[str]:
    try:
        entries = sorted(path.iterdir())[:MAX_WORKSPACE_ENTRIES]
    except OSError:
        return []
    return [e.name for e in entries if e.is_dir() and not e.name.startswith(".")]


def _outside_repositories(home: Path, segments: list[str]) -> list[str]:
    inside = (
        i
        for i in range(len(segments))
        if home.joinpath(*segments[: i + 1], ".git").exists()
    )
    return segments[: next(inside, len(segments))]


def workspace_names(home: Path, repo: Path, dictionary: frozenset[str]) -> list[str]:
    try:
        relative = repo.resolve().relative_to(home.resolve())
    except ValueError:
        return []
    segments = _outside_repositories(home, list(relative.parts[:-1]))
    ancestors = [home.joinpath(*segments[: i + 1]) for i in range(len(segments) - 1)]
    nested = [name for folder in ancestors for name in _children(folder)]
    joined = ["/".join(segments[: i + 1]) for i in range(1, len(segments))]
    names = [*segments, *nested]
    return [*joined, *(n for n in names if not is_generic(n, dictionary))]


def _window_names(dictionary: frozenset[str]) -> list[str]:
    template = "#{session_name}\t#{window_name}"
    listing = probe(["tmux", "list-windows", "-a", "-F", template])
    names = [part for line in _lines(listing) for part in line.split("\t")]
    return [n for n in names if not n.isdigit() and not is_generic(n, dictionary)]


def _session_id(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("sessionId")
    except (OSError, ValueError, AttributeError):
        return ""
    return value if isinstance(value, str) else ""


def _session_ids(home: Path) -> list[str]:
    folder = home / ".claude" / "sessions"
    files = sorted(folder.glob("*.json"))[:MAX_SESSION_FILES]
    return [sid for sid in (_session_id(path) for path in files) if sid]


def _temp_paths() -> list[str]:
    tmpdir = os.environ.get("TMPDIR", "").rstrip("/")
    owned = [tmpdir] if tmpdir.startswith(MAC_TEMP_ROOTS) else []
    return [f"claude-{os.getuid()}", *owned]


def listed(home: Path) -> tuple[list[str], frozenset[str]]:
    try:
        text = (home / LOCAL_LIST).read_text(encoding="utf-8")
    except OSError:
        return [], frozenset()
    rows = [r for r in _lines(text) if not r.startswith("#")]
    marked = [r for r in rows if r.startswith(EXEMPT_PREFIX)]
    exempt = frozenset(r[len(EXEMPT_PREFIX) :].lower() for r in marked)
    return [r for r in rows if not r.startswith(EXEMPT_PREFIX)], exempt


def _tagged(kind: Kind, tokens: list[str]) -> list[Identifier]:
    return [Identifier(kind, token) for token in tokens if token]


def _owned(identifier: Identifier, owner: str) -> bool:
    return identifier.kind is Kind.ACCOUNT and identifier.token.lower() == owner


def discover(home: Path, repo: Path) -> list[Identifier]:
    dictionary = _dictionary()
    user = getpass.getuser()
    extra, exempt = listed(home)
    owner = repo_owner(repo)
    found = [
        *_tagged(Kind.HOME_PATH, [str(home), str(home).replace("/", "-")]),
        *_tagged(Kind.USERNAME, sorted({user, home.name})),
        *_tagged(Kind.HOSTNAME, _host_names()),
        *_tagged(Kind.REAL_NAME, _real_names(dictionary)),
        *_tagged(Kind.EMAIL, _emails()),
        *_tagged(Kind.WORKSPACE, workspace_names(home, repo, dictionary)),
        *_tagged(Kind.WINDOW, _window_names(dictionary)),
        *_tagged(Kind.SESSION_ID, _session_ids(home)),
        *_tagged(Kind.TEMP_PATH, _temp_paths()),
        *_tagged(Kind.ACCOUNT, _accounts(user)),
        *_tagged(Kind.LISTED, extra),
    ]
    kept = [i for i in found if i.token.lower() not in exempt and not _owned(i, owner)]
    return list({i.token.lower(): i for i in reversed(kept)}.values())
