"""
[BKM-034 Point 13] Automated Delegation Retrospective Stage
Synthesizes a post-sprint DELEGATION_RETROSPECTIVE.md from the /tmp/delegate_story_*.log
# [FEAT-065] Cross-Platform Synchronization
step logs produced by delegate.py, cross-referencing live REST session metrics from the
OpenAgent core engine (127.0.0.1:4097), and comparing each story's DECLARED target path
# [FEAT-075] Content Immutability (The 18-Year Lock)
against the ACTUAL git diff footprint to detect path-search thrash.

Class 1 design: pure stdlib only, read-only REST GETs with a short timeout and graceful
fallback to log-only metrics, atomic .tmp + os.replace writes. No third-party packages.
"""

import argparse
import ast
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

REST_SESSION_URL = "http://127.0.0.1:4097/session"
REST_TIMEOUT = 5
LOG_GLOB = "/tmp/delegate_story_*.log"
DEFAULT_TARGET_DIR = os.path.expanduser("~/Dev_Lab")
DEFAULT_OUT = os.path.join(DEFAULT_TARGET_DIR, "DELEGATION_RETROSPECTIVE.md")
DEFAULT_LOOKBEHIND = 5

_LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[STORY (\d+)\] \[([A-Z_]+)\] (.*)$")
_START_RE = re.compile(r"Initiating delegation for '(?P<title>.+?)' \(file: (?P<file>[^)]+)\)")
_SESSION_RE = re.compile(r"Created REST session (\S+)")
_COMPLETE_RE = re.compile(r"Story \d+ dispatch complete in (?P<dur>[\d.]+)s\. finish=(?P<finish>\S+) tokens=(?P<tokens>.*)$")


def _parse_ts(ts_str):
    """Parse a 'YYYY-MM-DD HH:MM:SS' log timestamp into epoch seconds (0 on failure)."""
    try:
        return time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return 0.0


def _parse_tokens(raw):
    """Parse the COMPLETE-line tokens payload: inline-brace dict OR bare int."""
    raw = (raw or "").strip()
    if raw.startswith("{"):
        try:
            parsed = ast.literal_eval(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            return {}
    try:
        return {"total": int(raw)}
    except ValueError:
        return {}


def parse_story_log(path):
    """Parse a /tmp/delegate_story_<N>.log into a per-story record dict."""
    record = {
        "log_path": path,
        "story": None,
        "title": None,
        "declared_files": [],
        "session_ids": [],
        "runs": 0,
        "attempts": 0,
        "retries": 0,
        "failed": 0,
        "complete": None,
        "wall_clock_s": 0.0,
    }
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except OSError:
        return record

    first_ts = None
    last_ts = None
    run_start = None
    for raw in lines:
        m = _LINE_RE.match(raw.strip())
        if not m:
            continue
        ts_str, story_str, step, msg = m.groups()
        ts = _parse_ts(ts_str)
        if record["story"] is None:
            record["story"] = int(story_str)
        if first_ts is None:
            first_ts = ts
        last_ts = ts

        if step == "START":
            record["runs"] += 1
            run_start = ts
            sm = _START_RE.search(msg)
            if sm:
                record["title"] = sm.group("title")
                fpath = sm.group("file").strip()
                if fpath and fpath not in record["declared_files"]:
                    record["declared_files"].append(fpath)
        elif step == "SESSION_CREATED":
            sm = _SESSION_RE.search(msg)
            if sm and sm.group(1) not in record["session_ids"]:
                record["session_ids"].append(sm.group(1))
        elif step == "DISPATCH_ATTEMPT":
            record["attempts"] += 1
        elif step == "RETRY_BACKOFF":
            record["retries"] += 1
        elif step == "FAILED":
            record["failed"] += 1
        elif step == "COMPLETE":
            cm = _COMPLETE_RE.search(msg)
            if cm:
                record["complete"] = {
                    "duration_s": float(cm.group("dur")),
                    "finish": cm.group("finish"),
                    "tokens": _parse_tokens(cm.group("tokens")),
                }
                if run_start is not None:
                    record["wall_clock_s"] = max(0.0, ts - run_start)
            elif run_start is not None:
                record["complete"] = {"duration_s": None, "finish": msg, "tokens": None}
                record["wall_clock_s"] = max(0.0, ts - run_start)

    # Wall-clock fallback for runs that never emitted a COMPLETE line (still in-flight).
    if record["wall_clock_s"] <= 0.0 and first_ts is not None and last_ts is not None:
        record["wall_clock_s"] = max(0.0, last_ts - first_ts)
    return record


def parse_all_logs(log_glob=LOG_GLOB):
    """Discover and parse every /tmp/delegate_story_*.log, keyed by story number."""
    stories = {}
    for path in sorted(glob.glob(log_glob)):
        rec = parse_story_log(path)
        if rec["story"] is None:
            continue
        stories[rec["story"]] = rec
    return stories


def fetch_session_metrics(url=REST_SESSION_URL, timeout=REST_TIMEOUT):
    """Read-only GET of the live session list. Returns [] (graceful) if unreachable."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            return data
        return [] if not isinstance(data, dict) else [data]
    except Exception:
        return []


def _session_tokens(sess):
    """Defensively extract input/output/reasoning/cache token counts from a session dict."""
    t = sess.get("tokens") or {}
    if not isinstance(t, dict):
        return {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    cache = t.get("cache") or {}
    if isinstance(cache, dict):
        cr, cw = cache.get("read", 0), cache.get("write", 0)
    else:
        cr, cw = 0, 0
    return {
        "input": int(t.get("input") or 0),
        "output": int(t.get("output") or 0),
        "reasoning": int(t.get("reasoning") or 0),
        "cache_read": int(cr or 0),
        "cache_write": int(cw or 0),
    }


def enrich_with_session_metrics(stories, sessions):
    """Match REST sessions to story ids, attribute children (parentID), aggregate metrics."""
    by_id = {s.get("id"): s for s in sessions if isinstance(s, dict) and s.get("id")}
    for story in stories.values():
        matched = [by_id[s] for s in story["session_ids"] if s in by_id]
        if not matched:  # title fallback: 'Story N' in session title
            for s in by_id.values():
                if f"Story {story['story']}" in (s.get("title") or ""):
                    matched.append(s)
        story["matched_sessions"] = matched
        story["session_id"] = ", ".join(str(s.get("id")) for s in matched if s.get("id")) or (
            ", ".join(story["session_ids"]) or "-"
        )
        children = [s for s in by_id.values() if s.get("parentID") in story["session_ids"]]
        story["children"] = children

        agg = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
        cost = 0.0
        add = dele = files = 0
        agents, models = set(), set()
        rest_duration_ms = 0
        for s in matched + children:
            tk = _session_tokens(s)
            for k in agg:
                agg[k] += tk[k]
            cost += float(s.get("cost") or 0)
            summ = s.get("summary") or {}
            add += int(summ.get("additions") or 0)
            dele += int(summ.get("deletions") or 0)
            files += int(summ.get("files") or 0)
            if s.get("agent"):
                agents.add(s.get("agent"))
            m = s.get("model") or {}
            if m.get("id"):
                models.add(m.get("id"))
            tm = s.get("time") or {}
            if tm.get("created") and tm.get("updated"):
                rest_duration_ms = max(rest_duration_ms, int(tm["updated"]) - int(tm["created"]))

        story["tokens"] = agg
        story["cost"] = cost
        story["summary"] = {"additions": add, "deletions": dele, "files": files}
        story["agent"] = ", ".join(sorted(agents)) or "-"
        story["model"] = ", ".join(sorted(models)) or "-"
        story["rest_duration_ms"] = rest_duration_ms
    return stories


def _run_git(target_dir, *args):
    """Run a read-only git command in target_dir; return stdout ('' on any failure)."""
    try:
        proc = subprocess.run(
            ["git", "-C", target_dir] + list(args),
            capture_output=True, text=True, timeout=15,
        )
        return proc.stdout if proc.returncode == 0 else ""
    except Exception:
        return ""


def fetch_git_actuals(target_dir=DEFAULT_TARGET_DIR, lookbehind=DEFAULT_LOOKBEHIND):
    """List files ACTUALLY modified: git diff HEAD~N..HEAD, falling back to status+log."""
    out = _run_git(target_dir, "diff", "--name-only", f"HEAD~{lookbehind}..HEAD")
    paths = [p for p in out.splitlines() if p.strip()]
    if paths:
        return paths
    # Fallback: uncommitted worktree + recent commit log (diff empty).
    seen = set()
    st = _run_git(target_dir, "status", "--porcelain")
    for line in st.splitlines():
        if len(line) <= 3:
            continue
        p = line[3:].strip()
        if " -> " in p:  # rename 'old -> new'
            p = p.split(" -> ")[1]
        if p:
            seen.add(p)
    lg = _run_git(target_dir, "log", "--name-only", "--pretty=", f"-{max(lookbehind, 5)}")
    for p in lg.splitlines():
        if p.strip():
            seen.add(p.strip())
    return sorted(seen)


def _paths_aligned(declared, actual):
    """True if a declared target path and an actual changed path overlap (ancestor/equal/basename)."""
    d = declared.rstrip("/")
    a = actual.rstrip("/")
    if d == a:
        return True
    if d.startswith(a + "/") or a.startswith(d + "/"):
        return True
    return os.path.basename(d) == os.path.basename(a)


def score_path_alignment(story, actual_files):
    """Score declared-vs-actual path coverage; flag THRASH on divergence or sprawl."""
    declared = [d.lstrip("./") for d in story["declared_files"]]
    actual = [a.lstrip("./") for a in actual_files]
    matched = [d for d in declared if any(_paths_aligned(d, a) for a in actual)]
    coverage = len(matched) / len(declared) if declared else 1.0
    declared_tops = {d.split("/", 1)[0] for d in declared}
    unrelated_tops = sorted(
        {a.split("/", 1)[0] for a in actual if a.split("/", 1)[0] not in declared_tops}
    )
    divergent = sorted(set(declared) - set(matched))
    if not declared:
        verdict = "NO-DECLARED-TARGET"
    elif coverage >= 0.5 and len(unrelated_tops) <= 1:
        verdict = "OK"
    else:
        verdict = "THRASH"
    return {
        "verdict": verdict,
        "coverage": coverage,
        "divergent": divergent,
        "unrelated_tops": unrelated_tops,
        "actual": actual,
    }


def _md_escape(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _tokens_str(tok):
    return f"in={tok.get('input', 0)} out={tok.get('output', 0)}"


def synthesize_retrospective(stories, actual_files, target_dir=DEFAULT_TARGET_DIR, lookbehind=DEFAULT_LOOKBEHIND):
    """Render the full DELEGATION_RETROSPECTIVE.md markdown document."""
    lines = [
        "# DELEGATION_RETROSPECTIVE",
        "",
        f"> Generated {time.strftime('%Y-%m-%d %H:%M:%S')} | source logs `/tmp/delegate_story_*.log` | "
        f"git actuals `git -C {target_dir} diff --name-only HEAD~{lookbehind}..HEAD`",
        "",
        "## Per-Story Dispatch Table",
        "",
        "| Story | Title | Target Path | Session ID | Tokens In/Out | Cost | Duration | Retries | Child Sessions | Thrash |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for num in sorted(stories):
        st = stories[num]
        title = _md_escape(st["title"] or "-")
        target = "<br>".join(st["declared_files"]) or "-"
        sid = st.get("session_id") or "-"
        tok = _tokens_str(st.get("tokens") or {})
        cost = f"{st.get('cost') or 0.0:.4f}"
        dur = f"{st['wall_clock_s']:.1f}s"
        retries = f"{st['retries']} (attempts {st['attempts']})"
        children = st.get("children") or []
        child_str = f"{len(children)}"
        if children:
            child_str += ": " + ", ".join(c.get("id") for c in children[:3])
        verdict = (st.get("thrash") or {}).get("verdict") or "-"
        lines.append(
            f"| {num} | {title} | {target} | {sid} | {tok} | {cost} | {dur} | {retries} | {child_str} | {verdict} |"
        )

    lines += ["", "## Path Divergence Summary", ""]
    diverged = [st for st in stories.values() if (st.get("thrash") or {}).get("verdict") == "THRASH"]
    if diverged:
        for st in diverged:
            t = st["thrash"]
            lines.append(
                f"- **Story {st['story']}** declared `{', '.join(st['declared_files'])}`; actual git diff "
                f"touched `{', '.join(t['actual']) or '(none)'}`; divergent targets: {len(t['divergent'])} "
                f"(`{', '.join(t['divergent']) or '(none)'}`); unrelated top-level paths: "
                f"`{', '.join(t['unrelated_tops']) or '(none)'}`."
            )
    else:
        lines.append("No stories diverged from their declared target path.")

    lines += [
        "",
        "## Methodology (BKM)",
        "- Parse `/tmp/delegate_story_*.log` step lines: START (declared file), SESSION_CREATED (session id), "
        "DISPATCH_ATTEMPT/RETRY_BACKOFF/FAILED (attempt/retry counts), COMPLETE (duration, finish, tokens).",
        "- REST metrics: read-only GET `127.0.0.1:4097/session` (timeout <= 5s, graceful fallback to log-only); "
        "children attributed by `parentID` == story session id; tokens/cost/summary aggregated across parent + "
        "children; REST duration = `time.updated - time.created`.",
        "- Git actuals: `git -C <target_dir> diff --name-only HEAD~N..HEAD` (N=5), falling back to "
        "`status --porcelain` + `log --name-only` when empty. THRASH verdict = declared target coverage < 50% "
        "or > 1 unrelated top-level path touched.",
        "",
    ]
    return "\n".join(lines)


def atomic_write_text(path, content):
    """Atomic .tmp + os.replace write (same-directory temp for same-partition replace)."""
    path = os.path.abspath(os.path.expanduser(path))
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def run_retrospective(out_path=DEFAULT_OUT, target_dir=DEFAULT_TARGET_DIR, lookbehind=DEFAULT_LOOKBEHIND):
    """Full pipeline: parse logs -> fetch REST metrics -> git actuals -> score -> write markdown."""
    stories = parse_all_logs()
    sessions = fetch_session_metrics()
    enrich_with_session_metrics(stories, sessions)
    actual_files = fetch_git_actuals(target_dir, lookbehind)
    for st in stories.values():
        st["thrash"] = score_path_alignment(st, actual_files)
    md = synthesize_retrospective(stories, actual_files, target_dir, lookbehind)
    atomic_write_text(out_path, md + "\n")
    print(
        f"[RETRO] Wrote {os.path.abspath(out_path)} "
        f"({len(stories)} stories, {len(sessions)} sessions from REST)"
    )
    return md


def main(argv=None):
    parser = argparse.ArgumentParser(description="Automated Delegation Retrospective Stage")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output markdown path (default: ~/Dev_Lab/DELEGATION_RETROSPECTIVE.md)")
    parser.add_argument("--dir", default=DEFAULT_TARGET_DIR, help="Target working directory for git actuals (default: ~/Dev_Lab)")
    parser.add_argument("--lookbehind", default=DEFAULT_LOOKBEHIND, type=int, help="Commits to look back for git diff actuals (default: 5)")
    parser.add_argument("--logs-glob", default=LOG_GLOB, help="Glob for step logs (default: /tmp/delegate_story_*.log)")
    args = parser.parse_args(argv)
    run_retrospective(out_path=args.out, target_dir=args.dir, lookbehind=args.lookbehind)
    return 0


if __name__ == "__main__":
    sys.exit(main())