import asyncio
import json
import logging
import os
import socket
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional

# [FEAT-583] RDNA HyDE bypass probe: sub-15ms CPU FastEmbed vs ChromaDB port 8001
from logic.vector_pre_triage import probe_clara_dna_sync

SOCKET_TIMEOUT_S = 0.2
API_PROBE_TIMEOUT_S = 1.7  # [FEAT-531] 2x Rule for Cold Probe (2 * 0.85s)
KENDER_HOST = "192.168.1.26"
KENDER_PORT = 11434

# [FEAT-586] Path Anchor: resolve config from this module (HomeLabAI/src/logic/ -> HomeLabAI/config/)
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "infrastructure.json"

# [FEAT-586] Valid values for the operator-declarable triage engine preference.
VALID_PREFERRED_ENGINES = ("M5_AIR", "LOCAL_VLLM")

def _resolve_config_path() -> Path:
    """[FEAT-586] Locate config/infrastructure.json via Path anchor (module-relative).

    Prefers the Path(__file__)-anchored location; falls back to the legacy
    hardcoded home path for older checkouts.
    """
    if CONFIG_PATH.exists():
        return CONFIG_PATH
    legacy = Path(os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json"))
    return legacy if legacy.exists() else CONFIG_PATH

def _load_triage_preference() -> str:
    """[FEAT-586] Read the operator's preferred triage engine from infrastructure.json.

    Returns 'M5_AIR' (remote deep-thought silicon) or 'LOCAL_VLLM'.
    Defaults to 'M5_AIR' when the key is absent or holds an invalid value.
    """
    try:
        config_path = _resolve_config_path()
        if config_path.exists():
            with open(config_path, "r") as f:
                pref = json.load(f).get("preferred_triage_engine", "M5_AIR")
            if pref in VALID_PREFERRED_ENGINES:
                return pref
            logging.warning(f"[FEAT-586] Unknown preferred_triage_engine '{pref}'; defaulting to M5_AIR.")
    except Exception as e:
        logging.warning(f"[FEAT-586] Failed to load preferred_triage_engine: {e}")
    return "M5_AIR"

def _load_engine_seats() -> List[Dict[str, Any]]:
    """[FEAT-531] Load declarative engine seats from config/infrastructure.json."""
    config_path = str(_resolve_config_path())  # [FEAT-586] Path-anchored discovery
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
                if "seats" in data:
                    return data["seats"]
    except Exception as e:
        logging.warning(f"[SPECULATIVE] Failed to load seats from infrastructure.json: {e}")
    
    # Fallback default seats
    return [
        {
            "id": "M5_AIR",
            "name": "M5_AIR",
            "host": "192.168.1.46",
            "port": 8000,
            "protocol": "OPENAI",
            "probe_path": "/v1/chat/completions",
            "probe_payload": {"model": "mlx-community--Qwen3.5-9B-4bit", "messages": [{"role": "user", "content": "."}], "max_tokens": 1},
            "t_warmed": 0.09,
            "t_cold": 0.85
        },
        {
            "id": "KENDER",
            "name": "KENDER",
            "host": "192.168.1.26",
            "port": 11434,
            "protocol": "OLLAMA",
            "probe_path": "/api/tags",
            "probe_payload": None,
            "t_warmed": 0.12,
            "t_cold": 1.2
        },
        {
            "id": "LOCAL",
            "name": "LOCAL",
            "host": "127.0.0.1",
            "port": 8088,
            "protocol": "VLLM",
            "probe_path": "/v1/models",
            "probe_payload": None,
            "t_warmed": 0.045,
            "t_cold": 0.05
        }
    ]

def _probe_tcp(host: str, port: int, timeout: float = SOCKET_TIMEOUT_S) -> bool:
    """Return True if a TCP connect succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False

def _probe_http(url: str, payload: Optional[dict] = None, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
    """Return True if HTTP endpoint returns 200 within *timeout* seconds."""
    try:
        if payload:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"User-Agent": "AcmeLab/5.0", "Content-Type": "application/json"},
                method="POST"
            )
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "AcmeLab/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False

def _probe_seat(seat: Dict[str, Any]) -> bool:
    """[FEAT-531] Generic declarative seat health probe."""
    host = seat.get("host", "127.0.0.1")
    port = seat.get("port", 80)
    if not _probe_tcp(host, port, timeout=SOCKET_TIMEOUT_S):
        return False
    
    probe_path = seat.get("probe_path", "/v1/models")
    url = f"http://{host}:{port}{probe_path}"
    payload = seat.get("probe_payload")
    # 2x Rule: Probe timeout is 2 * t_cold
    t_probe = 2.0 * seat.get("t_cold", 0.85)
    return _probe_http(url, payload=payload, timeout=t_probe)

def resolve_active_deep_thought_target(seats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    [FEAT-531] Declarative Multi-Seat Engine Resolver:
    Iterates through configured engine seats and selects the first active remote engine.
    If all remote seats fail, falls back to LOCAL vLLM.
    """
    if seats is None:
        seats = _load_engine_seats()
    
    for seat in seats:
        if seat.get("id") == "LOCAL":
            continue
        if _probe_seat(seat):
            return seat
            
    # Default fallback to LOCAL seat
    local_seat = next((s for s in seats if s.get("id") == "LOCAL"), {
        "id": "LOCAL",
        "name": "LOCAL",
        "host": "127.0.0.1",
        "port": 8088,
        "protocol": "VLLM",
        "t_warmed": 0.045,
        "t_cold": 0.05
    })
    return local_seat


class _EWMALatencyEstimator:
    """[FEAT-586] Jacobson & Karels EWMA latency/jitter estimator (srtt/rttvar style).

    Smooths observed triage-completion latency into L_t (EWMA latency) and
    J_t (EWMA jitter), which feed the dynamic lead window:
        W_lead = (2 * t_warmed) + L_t + (4 * J_t)
    Gains follow Jacobson & Karels: alpha = 1/8 on latency, beta = 1/4 on jitter.
    With zero history (L_t = J_t = 0) the formula degrades to the legacy
    static head-start (2 * t_warmed), preserving the pre-FEAT-586 baseline.
    """
    ALPHA = 1 / 8.0   # EWMA gain on smoothed latency (Jacobson & Karels RTO)
    BETA = 1 / 4.0    # EWMA gain on jitter (mean deviation)

    def __init__(self) -> None:
        self.latency = 0.0   # L_t: EWMA-smoothed latency (srtt)
        self.jitter = 0.0    # J_t: EWMA-smoothed mean deviation (rttvar)
        self._samples = 0

    def observe(self, measured_seconds: float) -> None:
        """Feed one measured triage-latency sample into the EWMA smoother."""
        if measured_seconds is None or measured_seconds <= 0:
            return
        self._samples += 1
        if self._samples == 1:
            # No history yet: the first sample seeds L_t directly.
            self.latency = float(measured_seconds)
            self.jitter = 0.0
            return
        err = measured_seconds - self.latency
        self.latency += self.ALPHA * err
        self.jitter += self.BETA * (abs(err) - self.jitter)

    def lead_window(self, t_warmed: float) -> float:
        """[FEAT-586] W_lead = (2 * t_warmed) + L_t + (4 * J_t)."""
        return (2.0 * float(t_warmed)) + self.latency + (4.0 * self.jitter)


class SpeculativeTriageRelay:
    """
    [SPR-67_0 / FEAT-500] Speculative Triage Relay with Dynamic Deep Thought Multi-Seat Resolution.
    Races Sovereign Deep Thought (M5 Air / Kender) and Local vLLM for the fastest triage JSON.
    [FEAT-486 / FEAT-500] A Dual-Check Gate probes M5 Air first, then Kender:
    If a remote Deep Thought target is reachable, a 10.0s patient warmup runway is granted.
    If remote seats are unreachable, the head-start window is skipped with zero delay
    and local vLLM is dispatched immediately.
    """
    def __init__(self, broadcast_callback, deep_thought_fn=None, vllm_fn=None, t_warmed=0.09,
                 kender_fn=None, socket_timeout=SOCKET_TIMEOUT_S, api_timeout=API_PROBE_TIMEOUT_S,
                 preferred_engine: Optional[str] = None):
        self.broadcast = broadcast_callback
        self.deep_thought_fn = deep_thought_fn or kender_fn
        self.kender_fn = self.deep_thought_fn # backward compatibility
        self.vllm_fn = vllm_fn
        self.t_warmed = t_warmed
        # [FEAT-531] 2x Rule for Warmed Speculative Head-Start Window (2 * 0.09s = 0.18s)
        self.head_start_window = 2 * t_warmed
        # [FEAT-586] Dynamic Configurable Triage Engine Preference (declarative; overridable)
        self.preferred_engine = preferred_engine or _load_triage_preference()
        # [FEAT-586] Per-target Jacobson & Karels EWMA estimators feed the dynamic W_lead.
        self._estimators: Dict[str, _EWMALatencyEstimator] = {}
        # Dynamic lead window; seeded at the legacy 2x baseline until EWMA history accumulates.
        self.lead_window = self.head_start_window
        self.socket_timeout = socket_timeout
        self.api_timeout = api_timeout

    async def relay(self, query, context, triage_schema, request_id="default"):
        """
        Execute the speculative relay.
        Returns (triage_dict, winner_name) or (None, None).

        [FEAT-583] A decisive RDNA vector match short-circuits the relay entirely:
        runtime LLM HyDE generation is bypassed and pre-compiled target DNA
        anchors (explicit_links) are injected directly into the triage stream.
        [FEAT-586] The operator-preferred engine is granted the dynamic EWMA
        lead window W_lead = (2 * t_warmed) + L_t + (4 * J_t).
        [FEAT-586] Intent Lock: the opening quip is buffered and only attached
        once the winner (intent resolution) is known, guaranteeing semantic
        coherence between the quip and the final routing decision.
        """
        t_start = time.monotonic()

        # [FEAT-583] RDNA HyDE Bypass: sub-15ms CPU vector probe short-circuit.
        # A top-1 rdna match (distance < 0.45) with a decisive runner-up margin
        # (dist_2 - dist_1 >= 0.05) bypasses runtime LLM HyDE generation entirely.
        try:
            bypass_payload = self._maybe_rdna_hyde_bypass(query)
        except Exception as e:
            logging.warning(f"[FEAT-583] RDNA HyDE bypass probe failed: {e}")
            bypass_payload = None
        if bypass_payload is not None:
            bypass_payload["hyde_bypassed"] = True
            bypass_payload["winner"] = "rdna_bypass"
            bypass_payload["duration_ms"] = round((time.monotonic() - t_start) * 1000.0, 1)
            logging.info(f"[FEAT-583] RDNA HyDE bypass engaged (explicit_links={bypass_payload.get('explicit_links')})")
            return bypass_payload, "rdna_bypass"

        # [FEAT-531] Declarative Multi-Seat Resolution
        active_target = resolve_active_deep_thought_target()
        target_name = active_target["name"]
        t_warmed_seat = active_target.get("t_warmed", self.t_warmed)
        self.head_start_window = 2 * t_warmed_seat
        logging.info(f"[FEAT-531] Initiating Speculative Relay (Target: {target_name}, Head-start: {self.head_start_window:.3f}s)")

        if target_name == "LOCAL":
            logging.info("[FEAT-531] Remote Deep Thought seats unreachable. Fast dual-check gate: dispatching local vLLM with zero delay.")
            result = await self._run_vllm(query, context, triage_schema, request_id)
            if self._is_valid_triage(result):
                return self._finalize_payload(result, "vllm", t_start), "vllm"
            return None, None

        logging.info(f"[FEAT-500] Deep Thought target resolved: {target_name} ({active_target['host']}:{active_target['port']})")

        # [FEAT-586] Asymmetric head-start gate: the preferred engine claims W_lead.
        if self.preferred_engine == "LOCAL_VLLM":
            lead_name, racer_name = "vllm", "deep_thought"
            lead_launcher, racer_launcher = self._run_vllm, self._run_deep_thought
            logging.info(f"[FEAT-586] Preferred engine LOCAL_VLLM: granting dynamic lead window to local vLLM (lead_window={self.lead_window:.3f}s)")
        else:
            lead_name, racer_name = "deep_thought", "vllm"
            lead_launcher, racer_launcher = self._run_deep_thought, self._run_vllm
            logging.info(f"[FEAT-586] Preferred engine M5_AIR: granting dynamic lead window to Deep Thought (lead_window={self.lead_window:.3f}s)")

        # [FEAT-586] Dynamic W_lead = (2 * t_warmed) + L_t + (4 * J_t), EWMA-smoothed.
        estimator = self._estimators.setdefault(lead_name, _EWMALatencyEstimator())
        self.lead_window = estimator.lead_window(t_warmed_seat)

        # 1. Launch the preferred (lead) engine
        lead_task = asyncio.create_task(lead_launcher(query, context, triage_schema, request_id))
        t_lead = time.monotonic()

        # 2. Wait for the dynamic lead window
        done, pending = await asyncio.wait([lead_task], timeout=self.lead_window)

        # 3. If the lead engine finishes inside the window, it wins outright
        if done:
            try:
                result = done.pop().result()
                if self._is_valid_triage(result):
                    estimator.observe(time.monotonic() - t_lead)
                    logging.info(f"[FEAT-586] Preferred engine ({lead_name}) won (lead window completion)")
                    return self._finalize_payload(result, lead_name, t_start), lead_name
            except Exception as e:
                logging.warning(f"[FEAT-586] Preferred engine ({lead_name}) failed in lead window: {e}")

        # 4. Lead slow: launch the racer
        logging.info(f"[SPR-67_0] Preferred engine ({lead_name}) slow. Launching {racer_name} candidate...")
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"[SPECULATIVE] Preferred engine ({lead_name}) slow. Launching {racer_name} candidate...",
            "brain_source": "System"
        })

        racer_task = asyncio.create_task(racer_launcher(query, context, triage_schema, request_id))

        # 5. Race the remaining tasks
        runners = [lead_task, racer_task]
        while runners:
            done, runners = await asyncio.wait(runners, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                try:
                    result = task.result()
                    if self._is_valid_triage(result):
                        # Cancel the other runner
                        for r in runners:
                            if not r.done():
                                r.cancel()

                        winner = racer_name if task is racer_task else lead_name
                        estimator.observe(time.monotonic() - t_lead)
                        logging.info(f"[SPR-67_0] {winner.upper()} won (Speculative race)")
                        return self._finalize_payload(result, winner, t_start), winner
                except Exception as e:
                    logging.warning(f"[SPR-67_0] Runner failed: {e}")
                    continue

        return None, None

    def _finalize_payload(self, result, winner, t_start):
        """[FEAT-586/583] Enrich the winning triage dict with relay metadata.

        Intent Lock: the opening quip is only attached after the winner (intent
        resolution) is known, and only from the resolved winner's own triage
        output -- guaranteeing the quip and the routing decision stay coherent.
        """
        payload = dict(result)
        payload["winner"] = winner
        payload["duration_ms"] = round((time.monotonic() - t_start) * 1000.0, 1)
        payload["hyde_bypassed"] = False
        payload.setdefault("explicit_links", [])
        payload["quip"] = result.get("quip", "")
        return payload

    def _maybe_rdna_hyde_bypass(self, query) -> Optional[Dict[str, Any]]:
        """[FEAT-583] RDNA HyDE bypass gate.

        Fires when the sub-15ms CPU vector probe finds a decisive top-1 RDNA match:
        min_distance < 0.45 AND the runner-up margin (dist_2 - dist_1) >= 0.05.
        On bypass, pre-compiled target DNA anchors (explicit_links) replace
        runtime LLM HyDE generation. Returns an injected triage payload on
        bypass, otherwise None (fail-safe: never crashes the triage path).
        """
        probe = probe_clara_dna_sync(query)
        if probe.get("min_distance", 1.0) >= 0.45:
            return None
        if probe.get("best_collection") != "rdna":
            return None

        top2 = self._probe_rdna_top2(query)
        if top2 is None or len(top2) < 2:
            return None
        dist_1, dist_2 = top2[0], top2[1]
        if (dist_2 - dist_1) < 0.05:
            return None

        return self._build_rdna_bypass_payload(query, probe.get("best_meta") or {}, dist_1, dist_2)

    @staticmethod
    def _probe_rdna_top2(query) -> Optional[List[float]]:
        """[FEAT-583] Focused top-2 distance probe against the ChromaDB `rdna` collection.

        Returns [dist_1, dist_2] on success, None on any failure so the bypass
        can never crash the triage path.
        """
        if not query or not query.strip():
            return None
        try:
            from fastembed import TextEmbedding
            import chromadb
            model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            client = chromadb.HttpClient(host="127.0.0.1", port=8001)
            client.heartbeat()
            col = client.get_collection("rdna")
            vec = list(model.embed([query.strip()]))[0].tolist()
            res = col.query(query_embeddings=[vec], n_results=2, include=["distances"])
            dists = res["distances"][0]
            if len(dists) >= 2:
                return [float(dists[0]), float(dists[1])]
        except Exception as e:
            logging.warning(f"[FEAT-583] RDNA top-2 probe failed: {e}")
        return None

    @staticmethod
    def _build_rdna_bypass_payload(query, meta, dist_1, dist_2) -> Dict[str, Any]:
        """[FEAT-583] Assemble the injected triage payload for a decisive RDNA match."""
        rdna_id = meta.get("rdna_id") or meta.get("target_dna_id") or "RDNA-UNK"
        target_col = meta.get("target_collection") or "philosophy_dna"
        target_id = meta.get("target_dna_id") or ""
        target_title = meta.get("target_dna_title") or ""
        question_text = meta.get("question_text") or meta.get("canonical_question") or query

        # Pre-compiled target DNA anchor(s) from the matched RDNA card.
        # Prefer real explicit_links when the collection carries them; otherwise
        # construct the anchor from the card's declarative target_dna mapping.
        explicit_links = meta.get("explicit_links") or []
        if isinstance(explicit_links, str):
            explicit_links = [explicit_links]
        if not explicit_links and target_id:
            explicit_links = [target_id]

        return {
            "addressed_to": "NONE",  # entity routing deferred to the resolved intent
            "domain": meta.get("intent_category") or "standard",
            "situation": (
                f"[RDNA BYPASS] {question_text} -> "
                f"{target_col}:{target_id} (dist_1={dist_1:.3f}, margin={dist_2 - dist_1:.3f})"
            ),
            "vibe": "RDNA",
            "quip": "",  # [FEAT-586] Intent Lock: opening quip buffered (no LLM on bypass path)
            "explicit_links": explicit_links,
            "hyde_bypassed": True,
            "winner": "rdna_bypass",
            "duration_ms": 0.0,
            "inferred_intent": meta.get("intent_category") or "rdna_anchor_match",
            "importance": float(meta.get("confidence_floor") or 0.75),
            "casual": 0.0,
            "intrigue": 0.9,
            "rdna_match": {
                "collection": "rdna",
                "id": rdna_id,
                "distance": round(float(dist_1), 4),
                "margin": round(float(dist_2) - float(dist_1), 4),
                "target_dna_id": target_id,
            },
            "target_dna": {
                "collection": target_col,
                "id": target_id,
                "title": target_title,
            },
        }

    async def _run_deep_thought(self, query, context, triage_schema, request_id):
        if self.deep_thought_fn:
            return await self.deep_thought_fn(query, context, triage_schema, request_id)
        return None

    async def _run_kender(self, query, context, triage_schema, request_id):
        return await self._run_deep_thought(query, context, triage_schema, request_id)

    async def _run_vllm(self, query, context, triage_schema, request_id):
        return await self.vllm_fn(query, context, triage_schema, request_id)

    def _is_valid_triage(self, result):
        if not isinstance(result, dict):
            return False
        # [FEAT-518] Reject transient warming objects
        situation_str = str(result.get("situation", "")).lower()
        hint_str = str(result.get("hints", "")).lower()
        if "warming" in situation_str or "warming" in hint_str:
            return False
        # Check for essential triage fields
        required_fields = ["vibe", "addressed_to", "importance"]
        return all(field in result for field in required_fields)

    @staticmethod
    def get_console_metadata(winner):
        """
        Return channel/source metadata based on winner.
        """
        if winner in ["kender", "deep_thought", "m5_air", "rdna_bypass"]:
            return {
                "channel": "insight",
                "source": "Deep Thought (Triage)",
                "console": "Right"
            }
        else: # vllm
            return {
                "channel": "chat",
                "source": "Lab (Triage)",
                "console": "Left"
            }
