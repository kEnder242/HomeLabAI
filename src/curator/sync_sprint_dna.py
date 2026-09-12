#!/usr/bin/env python3
"""[FEAT-557] sprint_dna Smart Archiving Trigger & Distillation Engine.

Dedicated ChromaDB sync for historical & active sprint documentation.

Implements Story 76.3 of SPR-76.0:

* **Hybrid chunking** — Level 1 (Story cards with prompt triggers, touched
  files, lessons learned) + Level 2 (Sprint Overview with high-level themes,
  metrics, retros).
* **Discrete 3-tier recency curve** — Active sprint ``1.0``, past 5 sprints
  ``0.85``, older archived sprints ``0.30`` (stored in metadata ``recency``).
* **Smart archiving queue** — A single-worker distillation envelope that logs
  the elapsed execution time of the sync so the orchestrator can track
  distillation cost; designed to be triggered when a sprint moves into
  ``docs/sprints/archive/``.
* Writes to ChromaDB collection ``sprint_dna`` on port 8001 (HttpClient with
  PersistentClient fallback).
"""

import os
import re
import json
import hashlib
import logging
import time

import chromadb
from chromadb.utils import embedding_functions

# Config ---------------------------------------------------------------------
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")
COLLECTION_SPRINT = "sprint_dna"

SPRINT_ARCHIVE_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/docs/sprints/archive"
)
ACTIVE_SPRINT_DIR = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/docs/sprints/active"
)
SPRINT_DATA_OUTPUT = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/sprint_data.json"
)
DNA_MANIFEST_PATH = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/dna_manifest.json"
)

# Ignore non-sprint artifacts that live in the archive directory.
SKIP_FILENAMES = {
    "SPRINT_RESONANT_VIBE_v12.0.md",  # vibe spec, not a numbered sprint plan
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ----------------------------------------------------------------------------
# Recency tiering
# ----------------------------------------------------------------------------
def _sprint_number(filename: str):
    """Extract the primary numeric identifier from a sprint filename.

    Both naming conventions reduce to their *major* sprint number:
    ``SPR_74_0`` -> ``74`` and the 2011-era sub-sprints ``SPR_11_06`` /
    ``SPR_11_07`` / ``SPR_11_08`` all reduce to ``11`` (so the ancient
    2011 plans do not masquerade as the most recent sprint). Returns
    ``None`` for artifacts that cannot be ranked.
    """
    m = re.search(r"SPR_(\d+)", filename)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def classify_recency(sprint_num, current_active):
    """Assign the discrete 3-tier recency weight.

    * ``current_active``        -> ``1.0``
    * ``current_active-1 .. -5`` -> ``0.85``
    * anything older            -> ``0.30``

    Returns ``(weight, tier)`` where ``tier`` is one of ``"active"``,
    ``"recent5"``, ``"archived"``.
    """
    if sprint_num is None:
        return 0.30, "archived"  # non-numeric artifacts sink to oldest tier
    delta = current_active - sprint_num
    if delta <= 0:
        return 1.0, "active"
    if delta <= 5:
        return 0.85, "recent5"
    return 0.30, "archived"


# ----------------------------------------------------------------------------
# Hybrid chunking
# ----------------------------------------------------------------------------
_STORY_HEADER = re.compile(
    r"^(?P<hash>#{2,4})\s*(?P<title>.*?(?:Story|story|Task|GOAL|Goal).*?)$"
)

_LEVEL2_HEADERS = (
    "O V E R V I E W", "OVERVIEW", "MISSION", "GOAL", "THEME", "CONTEXT",
    "SUMMARY", "ARCHITECTURE", "BACKGROUND",
)

_TRIMMED_HEADERS = (
    "VALIDATION GAUNTLET", "VERIFICATION LEDGER", "APPENDIX", "REFERENCES",
)


def _line_blocks(content):
    """Split file content into sections separated by markdown headers."""
    lines = content.splitlines()
    blocks = []
    current_header = None
    current_lines = []
    for raw in lines:
        line = raw.rstrip()
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m and m.group(2).strip():
            if current_header is not None:
                blocks.append((current_header, "\n".join(current_lines).strip()))
            current_header = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_header is not None:
        blocks.append((current_header, "\n".join(current_lines).strip()))
    return blocks


def _is_story_header(header):
    """A Level-1 story-card header mentions a Story / Task / discrete Goal."""
    return bool(_STORY_HEADER.match("## " + header))


def _is_overview_header(header):
    head_u = header.upper()
    for t in _LEVEL2_HEADERS:
        if t in head_u:
            return True
    return False


def _trim_body(body):
    """Drop trailing, verbose validation/appendix sections from chunk bodies."""
    for trim in _TRIMMED_HEADERS:
        idx = body.upper().find(trim)
        if idx != -1 and body[idx - 1: idx].strip() in ("", "\n", "#"):
            body = body[:idx]
    return body.strip()


def _chunk_id(prefix, base, digest_len=16):
    return f"{prefix}_{hashlib.md5(base.encode('utf-8', errors='ignore')).hexdigest()[:digest_len]}"


def parse_sprint_file(filepath, sprint_num):
    """Parse a single sprint markdown file into hybrid chunk documents.

    Returns a list of ``{id, document, metadata, level, weight}`` dicts.
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    stem = os.path.basename(filepath).replace(".md", "")
    chunks = []

    # ---- Level 2: Sprint Overview -----------------------------------------
    overview_parts = []
    for header, body in _line_blocks(content):
        if _is_overview_header(header) and body:
            overview_parts.append(f"## {header}\n{body}")
    if not overview_parts:
        # Fall back to the document head when no explicit overview header.
        head = content[:1800]
        if head:
            overview_parts = [head.strip()]

    overview_doc = f"SPRINT OVERVIEW: {stem}\n\n" + "\n\n".join(overview_parts)
    overview_doc = _trim_body(overview_doc)
    if overview_doc:
        chunks.append({
            "id": _chunk_id("SPR", f"{stem}_overview"),
            "document": overview_doc,
            "metadata": {
                "sprint_id": stem,
                "sprint_num": sprint_num,
                "level": 2,
                "kind": "overview",
                "source": os.path.basename(filepath),
            },
        })

    # ---- Level 1: Story Cards ---------------------------------------------
    for idx, (header, body) in enumerate(_line_blocks(content)):
        if not _is_story_header(header):
            continue
        body = _trim_body(body)
        if not body:
            continue
        story_title = header.strip("# ").strip()
        story_doc = f"STORY CARD: {story_title}\n\n{body}"
        chunks.append({
            "id": _chunk_id("SPR", f"{stem}|{idx}|{story_title}"),
            "document": story_doc,
            "metadata": {
                "sprint_id": stem,
                "sprint_num": sprint_num,
                "level": 1,
                "kind": "story",
                "story_title": story_title,
                "source": os.path.basename(filepath),
            },
        })

    return chunks


# ----------------------------------------------------------------------------
# Chroma plumbing (mirrors Portfolio_Dev/sync_chroma_dna.py conventions)
# ----------------------------------------------------------------------------
def get_chroma_client():
    """HttpClient on port 8001 with PersistentClient fallback."""
    try:
        logging.info("Attempting to connect to ChromaDB HttpClient on port 8001...")
        client = chromadb.HttpClient(host="127.0.0.1", port=8001)
        client.heartbeat()
        logging.info("HttpClient heartbeat successful.")
        return client
    except Exception as e:
        logging.warning(f"HttpClient connection failed: {e}. Falling back to PersistentClient.")
        return chromadb.PersistentClient(path=DB_PATH)


def get_safe_collection(client, name, ef):
    try:
        return client.get_or_create_collection(name=name, embedding_function=ef)
    except Exception:
        return client.get_or_create_collection(name=name)


def discover_sprint_files(active_dir, archive_dir):
    """Return ``(current_active, [(sprint_num, filepath)])`` for all sprint docs.

    ``current_active`` is the highest sprint number found across the active
    directory (treating active sprints as the recency anchor). Archived sprints
    are all ranked relative to it.
    """
    files = []
    for directory in (active_dir, archive_dir):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(directory, name)
            num = _sprint_number(name)
            files.append((num, path))

    ranked = [(n, p) for (n, p) in files if n is not None]
    current_active = max((n for n, _ in ranked), default=0)
    return current_active, ranked


# ----------------------------------------------------------------------------
# Smart archiving queue (single-worker distillation envelope)
# ----------------------------------------------------------------------------
def enqueue_single_sprint_distillation(filepath, elapsed_seconds=None):
    """[FEAT-557] Single-worker distillation envelope for a just-archived sprint.

    Logs the distillation to stderr/stdout with execution-duration telemetry so
    the orchestrator can observe how long a single-sprint sync took against the
    sovereign engine. Returns ``True`` when a file was enqueued (non-empty).
    """
    if not filepath or not os.path.exists(filepath):
        logging.warning("[sprint_dna] distillation skipped: missing %s", filepath)
        return False
    dur = elapsed_seconds if elapsed_seconds is not None else 0.0
    logging.info(
        "[sprint_dna] SMART-ARCHIVE enqueued single-sprint distillation for %s "
        "(elapsed=%.3fs)",
        os.path.basename(filepath), dur,
    )
    return True


# ----------------------------------------------------------------------------
# Sprint Card Manifest Compilation
# ----------------------------------------------------------------------------
def clean_sprint_title(line, sprint_id):
    line = re.sub(r"^#+\s*", "", line).strip()
    line = re.sub(r"^[🚀🎯🕵️🛠️\s]+", "", line).strip()
    line = re.sub(r"^(?:SPRINT\s+(?:PLAN|LOG)|Sprint\s+(?:Plan|Log))[:\s]*", "", line, flags=re.IGNORECASE).strip()
    line = re.sub(r"^\[?SPR[-_]\d+(?:[-_]\d+)?\]?[:\s]*", "", line, flags=re.IGNORECASE).strip()
    line = re.sub(r"^\d+\.\d+[:\s]*", "", line).strip()
    return line or f"Sprint {sprint_id}"


def parse_single_sprint_card(filepath):
    bn = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    m = re.search(r"SPR_(\d+)(?:_(\d+))?", bn)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) is not None else 0
    sprint_id = f"SPR-{major}.{minor}"

    lines = content.splitlines()
    first_h1 = ""
    for l in lines:
        if l.startswith("# "):
            first_h1 = l
            break

    title = clean_sprint_title(first_h1, sprint_id)

    # Extract Theme
    theme = ""
    for i, l in enumerate(lines):
        if "**Theme:**" in l or "**THEME:**" in l:
            theme = re.split(r"\*\*Theme:\*\*", l, flags=re.IGNORECASE)[-1].strip()
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith("**") and not lines[j].strip().startswith("#"):
                theme += " " + lines[j].strip()
                j += 1
            break

    # Extract Mission/Goal
    narrative = ""
    m_miss = re.search(
        r"##\s*(?:🎯\s*)?(?:THE\s+MISSION|OVERVIEW|MISSION|GOAL)[^\n]*\n+([^#\n]+(?:\n+[^#\n]+)?)",
        content,
        re.IGNORECASE,
    )
    if m_miss:
        narrative = m_miss.group(1).strip()
    elif theme:
        narrative = theme
    else:
        paragraphs = [
            p.strip()
            for p in content.split("\n\n")
            if p.strip() and not p.strip().startswith("#")
        ]
        narrative = paragraphs[0] if paragraphs else f"Sprint {sprint_id} execution plan and tasks."

    narrative = re.sub(r"\s+", " ", narrative)[:400].strip()
    origin_text = theme or narrative

    is_active = "active" in filepath
    tier = "ACTIVE" if is_active else "COMPLETED"
    rel_path = filepath.split("Dev_Lab/")[-1] if "Dev_Lab/" in filepath else filepath

    return {
        "id": sprint_id,
        "title": title,
        "origin": {
            "text": origin_text[:350],
            "source": bn,
        },
        "synthesis": {
            "narrative_context": narrative,
            "lab_anchors": [rel_path],
            "review_notes": "Active sprint in execution." if is_active else "Archived sprint record.",
        },
        "metadata": {
            "tags": [f"sprint-{major}", "sprint-plan"],
            "status": tier,
            "bucket_id": "bucket_5_infra",
        },
        "_sort_key": (major, minor),
    }


def compile_sprint_manifest(files):
    cards = []
    for _, filepath in files:
        bn = os.path.basename(filepath)
        if bn in SKIP_FILENAMES or "ORACLE" in bn:
            continue
        card = parse_single_sprint_card(filepath)
        if card:
            cards.append(card)

    by_id = {}
    for c in cards:
        sid = c["id"]
        if sid not in by_id:
            by_id[sid] = c
        else:
            if c["metadata"]["status"] == "ACTIVE" and by_id[sid]["metadata"]["status"] != "ACTIVE":
                by_id[sid] = c
            elif "PLAN" in c["origin"]["source"] and "PLAN" not in by_id[sid]["origin"]["source"]:
                by_id[sid] = c

    sorted_cards = sorted(by_id.values(), key=lambda x: x["_sort_key"], reverse=True)
    for c in sorted_cards:
        del c["_sort_key"]
    return sorted_cards


# ----------------------------------------------------------------------------
# Sync
# ----------------------------------------------------------------------------
def sync(dry_run=False):
    t_start = time.monotonic()
    logging.info(
        "[sprint_dna] Scanning archive at %s", SPRINT_ARCHIVE_PATH
    )
    current_active, files = discover_sprint_files(
        ACTIVE_SPRINT_DIR, SPRINT_ARCHIVE_PATH
    )
    if not files:
        logging.warning("[sprint_dna] No sprint documents discovered.")
        return {"uploaded": 0, "sprints": 0, "legacy_skipped": 0}

    sprint_cards = compile_sprint_manifest(files)
    logging.info("[sprint_dna] Compiled %d high-level sprint cards.", len(sprint_cards))

    all_chunks = []
    skipped = 0
    stats = {"active": 0, "recent5": 0, "archived": 0}
    for sprint_num, path in files:
        if os.path.basename(path) in SKIP_FILENAMES:
            skipped += 1
            continue
        weight, tier = classify_recency(sprint_num, current_active)
        stats[tier] += 1
        for chunk in parse_sprint_file(path, sprint_num):
            chunk["metadata"]["recency"] = weight
            chunk["metadata"]["tier"] = tier
            chunk["document"] = (
                f"[recency:{weight}] {chunk['document']}"
            )
            all_chunks.append(chunk)

    logging.info(
        "[sprint_dna] Discovered %d sprint docs (current_active=%d; "
        "tiers active=%d recent5=%d archived=%d). Produced %d chunks.",
        len(files), current_active, stats["active"], stats["recent5"],
        stats["archived"], len(all_chunks),
    )

    # Emit sprint_data.json and update dna_manifest.json
    if not dry_run and sprint_cards:
        try:
            os.makedirs(os.path.dirname(SPRINT_DATA_OUTPUT), exist_ok=True)
            with open(SPRINT_DATA_OUTPUT, "w", encoding="utf-8") as f:
                json.dump(sprint_cards, f, indent=2)
            logging.info("[sprint_dna] Emitted %d cards to %s", len(sprint_cards), SPRINT_DATA_OUTPUT)
        except Exception as e:
            logging.error("[sprint_dna] Failed to emit sprint_data.json: %s", e)

        try:
            if os.path.exists(DNA_MANIFEST_PATH):
                with open(DNA_MANIFEST_PATH, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                manifest_data["sprint"] = sprint_cards
                with open(DNA_MANIFEST_PATH, "w", encoding="utf-8") as f:
                    json.dump(manifest_data, f, indent=2)
                logging.info("[sprint_dna] Updated %d sprint cards in %s", len(sprint_cards), DNA_MANIFEST_PATH)
        except Exception as e:
            logging.error("[sprint_dna] Failed to update dna_manifest.json: %s", e)

    if dry_run or not all_chunks:
        return {
            "uploaded": 0 if dry_run else len(all_chunks),
            "sprints": len(files),
            "sprint_cards_compiled": len(sprint_cards),
            "legacy_skipped": skipped,
            "dry_run": dry_run,
            "chunks": len(all_chunks),
        }

    client = get_chroma_client()
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    collection = get_safe_collection(client, COLLECTION_SPRINT, ef)

    try:
        collection.delete(where={"source": {"$in": [os.path.basename(p) for _, p in files]}})
    except Exception as e:
        logging.warning("[sprint_dna] Could not clear prior sprint_dna entries: %s", e)

    ids = [c["id"] for c in all_chunks]
    documents = [c["document"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    logging.info("[sprint_dna] Uploading %d chunks to sprint_dna...", len(ids))
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    elapsed = time.monotonic() - t_start
    enqueue_single_sprint_distillation(
        os.path.join(SPRINT_ARCHIVE_PATH, "BATCH_SYNC"), elapsed
    )
    logging.info("[sprint_dna] Sync complete in %.3fs (%d chunks).", elapsed, len(ids))
    return {
        "uploaded": len(ids),
        "sprints": len(files),
        "sprint_cards_compiled": len(sprint_cards),
        "legacy_skipped": skipped,
        "dry_run": dry_run,
        "chunks": len(all_chunks),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="[FEAT-557] sprint_dna ChromaDB sync.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse & chunk without writing to ChromaDB.")
    args = parser.parse_args()
    result = sync(dry_run=args.dry_run)
    logging.info("[sprint_dna] Result: %s", result)
