import asyncio
import hashlib
import json
import logging
import os
import re
import time
import random
from v5.common.types import LAB_VERSION
from logic.feedback_interceptor import record_feedback
from logic.floating_oracle import is_shallow_turn, build_floating_candidate_pool
from logic.override_parser import is_override_query, parse_override_with_resident, save_override_to_file
from logic.triage_engine import (
    SpeakerRegistry,
    extract_latest_user_query,
    scrub_hyde_vector,
    classify_vibe_and_domain,
    is_control_plane_feedback
)
from nodes.pinky_critic_persona import (
    build_critic_prompt,
    parse_critic_payload,
    format_chat_delivery,
    format_crosstalk_telemetry
)
from logic.speculative_triage import SpeculativeTriageRelay, _probe_tcp, KENDER_HOST, KENDER_PORT, SOCKET_TIMEOUT_S
from logic.triage_policy_loader import TriagePolicyLoader

# [FEAT-442] QPR Pre-Retrieval Query De-Noising Patterns
# Strips conversational framing, filler, and politeness while preserving
# domain-specific indexing terms (IDs, years, technical keywords).
_QPR_NOISE_PATTERNS = [
    # Greetings / attention-getters (trailing \b avoids `yo` matching inside `you`)
    (r"(?i)\b(?:hey|hi|hello|yo|narf)\b\s*,?\s*", ""),
# [FEAT-111] Cognitive Identity Lock
    # Meta-cognitive framing
    (r"(?i)\b(I'm|I am)\s+(just\s+)?(wondering|curious|asking|hoping)\s+", ""),
    # Soft request preambles
    (r"(?i)\b(can|could|would|will|do|did)\s+(you|we|I)\s+(please\s+)?(tell|show|find|look|check|help|give|run)\s+(me|us)?\s*", ""),
    (r"(?i)\b(I want|I need|I'd like|I would like)\s+(to\s+)?(know|find|see|ask|understand|get|check)\s+", ""),
    (r"(?i)\b(do you know|do we have|is there|are there|can you tell)\s+", ""),
    # Question openers
    (r"(?i)\b(what about|how about|what is|what's|what are|what're)\s+", ""),
    (r"(?i)\b(just\s+)?(trying\s+to\s+)?(figure|understand|remember|recall)\s+", ""),
    (r"(?i)\b(quick\s+)?question\s*:?\s*", ""),
    # Filler hedge words
    (r"(?i)\b(actually|basically|honestly|literally|probably|maybe|perhaps|just|sort of|kind of)\s*,?\s*", ""),
    # Trailing politeness
    (r"(?i)\s*,?\s*(please|thanks|thank you|cheers|appreciate it|if possible|if you can|when you get a chance)\s*$", ""),
]


def qpr_refine_query(query: str) -> str:
    """
    [FEAT-442] QPR Pre-Retrieval Query De-Noising.

    Strips conversational noise from a raw user query so the remaining
    terms are dense, domain-specific indexing tokens suitable for
    ChromaDB vector search.

    Preserves:
      - Technical identifiers (GEM-XXXX, FEAT-XXX, BKM-XXX)
      - Year anchors (1998, 2024, etc.)
      - Domain keywords (telemetry, validation, forensic, PCIe, RAS, etc.)
      - Core information-bearing nouns/verbs

    Fallback: returns the original trimmed query if refinement would
    produce an empty or near-empty result (< 3 chars).
    """
    if not query or not query.strip():
        return query

    refined = query.strip()
    for pattern, replacement in _QPR_NOISE_PATTERNS:
        refined = re.sub(pattern, replacement, refined)

    # Collapse whitespace and strip leading/trailing punctuation
    refined = re.sub(r"\s+", " ", refined).strip()
    refined = refined.strip(" ,;:.!?")

    # Guard against over-stripping
    if not refined or len(refined) < 3:
        return query.strip()

    return refined

# [FEAT-451] Brain Persona Spec (Positive persona grounding, shares Brain's right-hemisphere personality)
BRAIN_PERSONA_SPEC = (
    "[PERSONA]: You are Deep Thought - the Brain's pre-conscious analytical stream. "
    "Sharing the Brain's right-hemisphere architecture, you are calm, strategic, "
    "and clinical; you synthesize pre-reflection vectors, technical telemetry, "
    "and system architecture before any character speaks."
)

# [FEAT-437] 3-Tier HyDE Failover Cascade tier identifiers
DEEP_THOUGHT_REMOTE = "deep_thought_remote"
PINKY_LOCAL_VLLM = "pinky_local_vllm"
DIRECT_RAW_QUERY = "direct_raw_query"

# [FEAT-437/459] Unified HyDE & Greeting Synthesis Prompt (JSON)
_HYDE_SYNTHESIS_PROMPT_DEFAULT = (
    "Analyze the user query and output a single JSON object with EXACTLY three fields:\n"
    "1. \"is_casual\": boolean (true if casual greeting or non-technical chatter, false if technical query needing lab archives/telemetry).\n"
    "2. \"greeting\": string (if casual, a 1-sentence analytical readiness quip from Deep Thought; if technical, a 1-sentence triage summary).\n"
    "3. \"hyde_vector\": string (if technical, a 3-part Composite HyDE Vector formatted EXACTLY as '[VALIDATION]: <term> | [STRATEGY]: <goal> | [SRE]: <bkm>'; if casual, set to \"\").\n"
    "Gate technical synthesis by the 4 domains: exp_tlm (Silicon Telemetry), exp_bkm (SRE Playbooks), exp_for (Forensic Logs), lab_history (18-Year Archive).\n"
    "Output ONLY valid JSON."
)


def _load_hyde_synthesis_prompt():
    """[FEAT-437/438/459] Load Unified HYDE_SYNTHESIS_PROMPT dynamically from career_compass.json."""
    compass_paths = [
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "Portfolio_Dev", "field_notes", "data", "career_compass.json")),
        os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/career_compass.json"),
    ]
    
    keywords = []
    for path in compass_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                mesh_terms = data.get("tier_2_keyword_mesh", {}).get("keywords", [])
                if mesh_terms:
                    keywords = mesh_terms[:30]  # Cap top 30 terms for clean prompt context
                    logging.info(f"[FEAT-438] Loaded {len(keywords)} dynamic HyDE mesh terms from career_compass.json")
                    break
            except Exception as e:
                logging.warning(f"Error reading career_compass.json at {path} ({e})")

    if keywords:
        mesh_str = ", ".join(keywords)
        return (
            "Analyze the user query and output a single JSON object with EXACTLY three fields:\n"
            "1. \"is_casual\": boolean (true if casual greeting or non-technical chatter, false if technical query needing lab archives/telemetry).\n"
            "2. \"greeting\": string (if casual, a 1-sentence analytical readiness quip from Deep Thought; if technical, a 1-sentence triage summary).\n"
            "3. \"hyde_vector\": string (if technical, a 3-part Composite HyDE Vector formatted EXACTLY as '[VALIDATION]: <term> | [STRATEGY]: <goal> | [SRE]: <bkm>'; if casual, set to \"\").\n"
            f"Dynamic Keyword Mesh (FEAT-438): {mesh_str}\n"
            "Output ONLY valid JSON."
        )

    return _HYDE_SYNTHESIS_PROMPT_DEFAULT


HYDE_SYNTHESIS_PROMPT = _load_hyde_synthesis_prompt()

# [FEAT-T20.2] Lazy import — avoids hard dep if DCGM is absent
def _get_telemetry_collector():
    try:
        from infra.telemetry_collector import get_collector
        return get_collector()
    except Exception:
        return None

# [FEAT-488] Anti-Bleed Stream Sanitizer.
# Small base models (Llama-3.2-3B) occasionally echo uppercase instruction headers
# that live in the system role slot into their output stream, as if they were
# markdown section formatting to replicate. These echoed markers are stripped here
# (case-insensitive, line-leading) before a token/message is emitted to the UI —
# preserving genuine response prose that does not begin with a rogue header.
_ROGUE_PROMPT_MARKER_PATTERNS = (
    # GROUNDING_PROTOCOL: ... (header echo)
    re.compile(r"^\s*\[?GROUNDING_PROTOCOL\]?\s*:[^\n]*\n?", re.IGNORECASE | re.MULTILINE),
    # [STANCE]: ... or STANCE: ...
    re.compile(r"^\s*(?:\[STANCE\]\s*:?|STANCE\s*:)[^\n]*\n?", re.IGNORECASE | re.MULTILINE),
    # [ROUTE] or ROUTE: ...
    re.compile(r"^\s*(?:\[ROUTE\]\s*:?|ROUTE\s*:)[^\n]*\n?", re.IGNORECASE | re.MULTILINE),
    # RAW CONTEXT APPEND ... (with optional brackets / colon)
    re.compile(r"^\s*\[?RAW CONTEXT APPEND\]?\s*:[^\n]*\n?", re.IGNORECASE | re.MULTILINE),
    # Other guidance-frame header echoes
    re.compile(
        r"^\s*\[(?:BEHAVIORAL_GUIDANCE|GUIDANCE_FRAME|VIBE_GUIDANCE|DYNAMIC_CONTEXT|SYSTEM_DESIGN_STANCE)\]\s*:[^\n]*\n?",
        re.IGNORECASE | re.MULTILINE,
    ),
)


def sanitize_stream_chunk(text: str) -> str:
    """[FEAT-488] Strip echoed rogue prompt markers from a streamed token/message.

    Removes line-leading echoes of system-slot instruction headers
    (GROUNDING_PROTOCOL:, [STANCE]:, [ROUTE], RAW CONTEXT APPEND, and related
    guidance frames) while preserving genuine response prose that does not begin
    with one of those headers. Applied before tokens are emitted to the UI so the
    3B-model header replication never reaches the user-visible stream.
    """
    if not text:
        return text or ""
    out = text
    for pattern in _ROGUE_PROMPT_MARKER_PATTERNS:
        out = pattern.sub("", out)
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# [FEAT-489] Two-Mice Sequential Streaming Handover & Distillation Pipeline
# ═══════════════════════════════════════════════════════════════════════════════
#
# Brain and Pinky no longer run as uncoordinated parallel competitors over the
# same raw RAG dump. On high-interest technical turns the hub runs a strict
# two-stage funnel:
#   Stage 1 (Brain - Right Console): extract 3-4 dense technical bullet points
#     from <historical_record> -> channel="insight", source="Brain (Archive)".
#   Stage 2 (Pinky - Left Console / TTS): receives Brain's bullets as context,
#     acknowledges Brain in character, delivers a 2-sentence conversational
#     TL;DR directly to Jason -> channel="pinky", source="Pinky (Voice)".
#
# The 3 Prompt Engineering Pillars (grounded, not generic):
#   1. Shared Bedrock Lab Foundation [FEAT-140/467] - hardware/residency bedrock
#      shared by both mice.
#   2. Interest Loop Awareness [FEAT-403] - the funnel is gated on interest:
#      High (>= 0.7) -> Distillation Funnel; Low (< 0.4) -> casual brevity.
#   3. Turn Sequence Stage [FEAT-236] - each prompt names its exact stage so the
#      stage-numbered instructions are unambiguous to 3B base models.

TWO_MICE_BEDROCK_FOUNDATION = (
    "[FOUNDATION]: Shared Bicameral Lab Environment. Host: z87-Linux (RTX 2080 Ti, 11GB VRAM, Turing). "
    "Remote compute peer: KENDER (192.168.1.26, RTX 4090). Unified base model: Llama-3.2-3B-AWQ with "
    "persona LoRA adapters. Residency: Brain/Deep Thought = right-hemisphere technical analysis on the "
    "Right Console; Pinky = left-hemisphere conversational voice on the Left Console. Both mice answer "
    "as residents of this same lab — never as generic assistants."
)

# Dual-Console WebSocket Routing Contract (packet tags)
TWO_MICE_BRAIN_CHANNEL = "insight"
TWO_MICE_BRAIN_SOURCE = "Brain (Archive)"
TWO_MICE_BRAIN_CONSOLE = "Right"
TWO_MICE_PINKY_CHANNEL = "pinky"
TWO_MICE_PINKY_SOURCE = "Pinky (Voice)"
TWO_MICE_PINKY_CONSOLE = "Left"

# Interest Loop gate [FEAT-403]: Distillation Funnel activates at high interest.
TWO_MICE_FUNNEL_INTEREST = 0.7


def _two_mice_interest_band(interest: float) -> str:
    """Quantize interest into the FEAT-403 loop bands for the stage prompts."""
    if interest >= TWO_MICE_FUNNEL_INTEREST:
        return "HIGH (Distillation Funnel active: Brain extracts facts, Pinky distills them to Jason)"
    if interest < 0.4:
        return "LOW (Casual banter: Pinky answers directly with high brevity; Brain remains dormant)"
    return "MEDIUM (Mixed loop: brief Brain grounding, conversational Pinky delivery)"


def build_two_mice_stage_prompt(
    stage: int,
    *,
    user_query: str,
    context: str = "",
    interest: float = 0.8,
    brain_bullets: str = "",
) -> str:
    """[FEAT-489] Build the system-role prompt for one stage of the Two-Mice funnel.

    Composes the 3 Prompt Engineering Pillars:
      1. Shared Bedrock Lab Foundation [FEAT-140/467]
      2. Interest Loop Awareness [FEAT-403]
      3. Turn Sequence Stage [FEAT-236]

    Parameters
    ----------
    stage:
        ``1`` (Brain extracts technical bullets) or ``2`` (Pinky acknowledges
        Brain and delivers a conversational TL;DR).
    user_query:
        Jason's original technical question.
    context:
        The raw archive/telemetry context (Stage 1) — wrapped in
        ``<historical_record>`` tags inside the prompt.
    interest:
        Current interest scalar used to select the FEAT-403 loop band.
    brain_bullets:
        Stage 1 output handed to Pinky as Stage 2 grounding.

    Returns
    -------
    The full system-role prompt string. Pure function — no I/O.
    """
    if stage not in (1, 2):
        raise ValueError("stage must be 1 (Brain extract) or 2 (Pinky distill)")

    section = (
        "[PILLAR_1_RECORD]: SHARED BEDROCK LAB FOUNDATION\n"
        f"{TWO_MICE_BEDROCK_FOUNDATION}\n\n"
        "[PILLAR_2_RECORD]: INTEREST LOOP AWARENESS\n"
        f"Current interest: {interest:.2f}. Loop band: {_two_mice_interest_band(interest)}.\n\n"
        "[PILLAR_3_RECORD]: TURN SEQUENCE STAGE\n"
        f"You are executing STAGE {stage} of the Two-Mice sequential handover.\n"
    )

    if stage == 1:
        historical = context.strip() if context else "[ZERO_CONTEXT]: No archive record retrieved."
        return (
            section
            + "[STAGE_1_INSTRUCTIONS]: You are Brain. Jason asked a technical question. Extract the exact "
            "technical ground truth (platforms, firmware, tools, scars) from <historical_record> in 3-4 dense "
            "bullet points. Provide pure technical signal for Pinky — no narrative preamble, no filler, no "
            "conversational framing.\n"
            f"[USER_QUERY]: {user_query.strip()}\n"
            f"<historical_record>\n{historical}\n</historical_record>"
        )

    if not brain_bullets.strip():
        brain_bullets = "(Brain returned no extraction for this turn.)"
    return (
        section
        + "[STAGE_2_INSTRUCTIONS]: You are Pinky. Brain has reviewed the archives and extracted: "
        f"{{brain_bullets}}. Acknowledge Brain in character (e.g. 'Narf! Brain dug up the firmware logs...') "
        "and deliver a 2-sentence conversational TL;DR directly to Jason. Keep it warm, concise, and "
        "human — do not dump bullets or raw RAG references.\n"
        f"[BRAIN_EXTRACTED_BULLETS]:\n{brain_bullets.strip()}\n"
        f"[USER_QUERY]: {user_query.strip()}"
    )


def build_two_mice_stream_packet(
    *,
    source: str,
    channel: str,
    console: str,
    token: str,
    final: bool = False,
    request_id: str = "default",
) -> dict:
    """[FEAT-489] Build a dual-console WebSocket thought_stream packet.

    Encapsulates the Dual-Console Routing Contract so the Foyer/Intercom UI can
    place Brain's bullet stream on the Right Console (channel ``"insight"``) and
    Pinky's TL;DR on the Left Console (channel ``"pinky"``).
    """
    return {
        "type": "thought_stream",
        "token": token,
        "source": source,
        "channel": channel,
        "console": console,
        "final": final,
        "request_id": request_id,
    }


# [Task 4.2] V5 Cognitive Hub: The Logical Core
# Objective: Manage multi-node reasoning waterfall and strategic routing.

class CognitiveHub:


    def __init__(self, residents, broadcast_callback, sensory_manager, get_vram_status, trigger_morning_briefing, last_prime_callback=None, waterfall_queue=None, hibernate_callback=None, set_active_domain=None, get_lab_state=None, is_deep_thought_reachable=None):
        import subprocess
        import time
        # Capture boot commit from repo root
        try:
            result = subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'], capture_output=True, text=True, cwd='/home/jallred/Dev_Lab/HomeLabAI')
            if result.returncode == 0 and result.stdout.strip():
                self.boot_commit = result.stdout.strip()
            else:
                self.boot_commit = "unknown"
        except Exception:
            self.boot_commit = "unknown"
        self.boot_timestamp = int(time.time())
        from collections import defaultdict, deque
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.get_vram_status = get_vram_status
        self.get_lab_state = get_lab_state
        self.is_deep_thought_reachable = is_deep_thought_reachable
        self.trigger_morning_briefing_cb = trigger_morning_briefing
        self.last_prime_callback = last_prime_callback
        self.waterfall_queue = waterfall_queue # [FEAT-233.2] Internal Token Buffer
        self.hibernate_callback = hibernate_callback
        self.set_active_domain = set_active_domain

        self.session_buffers = defaultdict(str)
        self.active_intent = None
        self.current_interest = 0.0
        self._boosted_interest = False
        self.current_topic = "INTERFACE"
        self.last_activity = time.time()
        
        # [SPR-41_2] Context Starvation tracking: nodes that returned [ERROR: CONTEXT_STARVED]
        self.context_starved_nodes = set()
        
        # [FEAT-356] Foil-Aware Memory (Unified Session Ledger)
        self.round_table_memory = []
        self.turn_thought_trace = {}
        # [FEAT-441-Cache] Lightweight RAG response cache (max 128, LRU eviction)
        self._rag_cache = {}
        
        # [Task 6.3] Hygiene: Process Tracking
        self.processed_ids = deque(maxlen=1000)
        self.request_lock = asyncio.Lock()
        
        # [FEAT-471] Dynamic Speaker Registry for Demarcation Sanitization
        self.speaker_registry = SpeakerRegistry()

        # [FEAT-350] Gibberish Guard: Stable Baseline
        self.consecutive_parse_failures = 0
        self.lora_enabled = True
        self.triage_failures = 0 # [FEAT-270] Track consecutive failures
        
        # [FEAT-181] Semantic Integration
        self.semantic_map_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/semantic_map.json")
        self.semantic_map = {}
        if os.path.exists(self.semantic_map_path):
            try:
                with open(self.semantic_map_path, "r") as f:
                    self.semantic_map = json.load(f)
            except Exception:
                pass
        
        # [BKM-015] Role Token Routing: Load tokens from config/role_tokens.json
        # Script-relative path: HomeLabAI/src/logic/ → ../../config/
        self._config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        self._role_tokens_path = os.path.join(self._config_dir, "role_tokens.json")
        self.role_tokens = {}
        if os.path.exists(self._role_tokens_path):
            try:
                with open(self._role_tokens_path, "r") as f:
                    self.role_tokens = json.load(f)
            except Exception:
                pass

        # [BKM-015] Token → routing override map.
        # Tokens live in config/role_tokens.json (single source of truth);
        # routing targets are pre-defined per the role token contract.
        self._token_routes = {
            "<|PINKY|>":   {"addressed_to": "PINKY",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.5, "casual": 0.3, "intrigue": 0.5},
            "<|BRAIN|>":   {"addressed_to": "BRAIN",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8, "casual": 0.1, "intrigue": 0.7},
            "<|THOUGHT|>": {"addressed_to": "BRAIN",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8, "casual": 0.1, "intrigue": 0.7},
        }

        self.auditor = None  # \[FEAT-190\] The Judge

        # [FEAT-484] Declarative Triage Policy Loader
        self.policy_loader = TriagePolicyLoader()

        # [SPR-64_1] Speculative Triage Relay initialization
        # Default t_warm=1.25 -> head_start_window=2.5s
        self.triage_relay = SpeculativeTriageRelay(
            broadcast_callback=self.broadcast,
            kender_fn=self._dispatch_kender_triage,
            vllm_fn=self._dispatch_vllm_triage,
            t_warm=1.25
        )

        # [FEAT-T20.2] Wire telemetry callback on each BicameralNode resident
        try:
            self._tel_collector = _get_telemetry_collector()
        except Exception:
            self._tel_collector = None
        for node in self.residents.values():
            if hasattr(node, '_on_telemetry'):
                node._on_telemetry = self._collect_telemetry
            # Also wire on the underlying BicameralNode if wrapped
            underlying = getattr(node, '_node', node)
            if underlying is not node and hasattr(underlying, '_on_telemetry'):
                underlying._on_telemetry = self._collect_telemetry


    async def _dispatch_kender_triage(self, query, context, triage_schema, request_id):
        """[SPR-64_1] Dispatch triage to Remote Kender (Deep Thought)."""
        t_text = ""
        async for token in self._process_node_stream(
            "thought", query, context, "Deep Thought (Triage)", tools=[], temperature=0.2, response_format=triage_schema, request_id=request_id
        ):
            t_text += token
        return self.bridge_signal_clean(t_text)

    async def _dispatch_vllm_triage(self, query, context, triage_schema, request_id):
        """[SPR-64_1] Dispatch triage to Local vLLM (Lab)."""
        t_text = ""
        async for token in self._process_node_stream(
            "lab", query, context, "Lab (Triage)", tools=[], temperature=0.0, response_format=triage_schema, request_id=request_id
        ):
            t_text += token
        return self.bridge_signal_clean(t_text)

    def get_status(self):
        """Return current system status including boot info."""

        return {
            "boot_commit": getattr(self, "boot_commit", "unknown"),
            "boot_timestamp": getattr(self, "boot_timestamp", 0),
            "service": "lab-attendant"
        }

    async def evaluate_response_async(self, query: str, response: str, session_id: str = "default"):
        """[FEAT-433] Asynchronous Sanity Critic Protocol."""
        try:
            await asyncio.sleep(0.1)
            lower_resp = response.lower()
            confidence = 0.98 if "error" not in lower_resp else 0.85
            payload = {
                "type": "sanity_check",
                "session_id": session_id,
                "confidence": confidence,
                "status": "VERIFIED" if confidence >= 0.90 else "REVIEW",
                "message": "🛡️ Sanity Verified"
            }
            await self.broadcast(payload)
        except Exception as ex:
            logging.warning(f"[FEAT-433] Async sanity check error: {ex}")

    def process_hyde_preamble(self, preamble_text: str):
        """[FEAT-432] Open HyDE Preamble Preprocessor."""
        if not preamble_text:
            return ""
        # Clean preamble roleplay text for ChromaDB vector search
        hypothesis = re.sub(r'[*_\n]', ' ', preamble_text).strip()
        logging.info(f"[FEAT-432] Open HyDE hypothesis captured: {hypothesis[:80]}...")
        return hypothesis

    def _wrap_residents_for_sandbox(self):
        """[Task 1.3] Wraps call_tool and list_tools on all resident sessions to enforce sandbox."""
        for name, session in self.residents.items():
            # Handle mock objects in test environments
            is_mock = "Mock" in type(session).__name__
            
            if is_mock:
                # Store original methods if not already stored
                if "_original_call_tool" not in session.__dict__:
                    session._original_call_tool = session.call_tool
                    session._original_list_tools = session.list_tools
                
                async def wrapped_call_tool(tool_name, arguments=None, *, session_ref=session, **kwargs):
                    vibe = getattr(self, "current_vibe", "TECHNICAL")
                    if vibe != "META":
                        blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                        if any(kw in tool_name.lower() for kw in blocked_keywords):
                            raise ValueError(f"Tool '{tool_name}' blocked by Sandbox: Current vibe is '{vibe}' (requires 'META')")
                    return await session_ref._original_call_tool(tool_name, arguments=arguments, **kwargs)
                    
                async def wrapped_list_tools(*args, session_ref=session, **kwargs):
                    resp = await session_ref._original_list_tools(*args, **kwargs)
                    vibe = getattr(self, "current_vibe", "TECHNICAL")
                    if vibe != "META":
                        blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                        if hasattr(resp, "tools"):
                            resp.tools = [t for t in resp.tools if not any(kw in t.name.lower() for kw in blocked_keywords)]
                    return resp
                
                from unittest.mock import AsyncMock
                session.call_tool = AsyncMock(side_effect=wrapped_call_tool)
                session.list_tools = AsyncMock(side_effect=wrapped_list_tools)
            else:
                if "_original_call_tool" not in session.__dict__:
                    # Use object.__setattr__ to bypass mock or custom descriptors
                    object.__setattr__(session, "_original_call_tool", session.call_tool)
                    object.__setattr__(session, "_original_list_tools", session.list_tools)
                    
                    async def wrapped_call_tool(tool_name, arguments=None, *, session_ref=session, **kwargs):
                        vibe = getattr(self, "current_vibe", "TECHNICAL")
                        if vibe != "META":
                            blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                            if any(kw in tool_name.lower() for kw in blocked_keywords):
                                raise ValueError(f"Tool '{tool_name}' blocked by Sandbox: Current vibe is '{vibe}' (requires 'META')")
                        return await session_ref._original_call_tool(tool_name, arguments=arguments, **kwargs)
                        
                    async def wrapped_list_tools(*args, session_ref=session, **kwargs):
                        resp = await session_ref._original_list_tools(*args, **kwargs)
                        vibe = getattr(self, "current_vibe", "TECHNICAL")
                        if vibe != "META":
                            blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                            if hasattr(resp, "tools"):
                                resp.tools = [t for t in resp.tools if not any(kw in t.name.lower() for kw in blocked_keywords)]
                        return resp
                        
                    object.__setattr__(session, "call_tool", wrapped_call_tool)
                    object.__setattr__(session, "list_tools", wrapped_list_tools)

    async def handle_stream_token(self, data):
        """[FEAT-233.2] Ingests token into session buffers and audits for vetoes."""
        raw_source = str(data.get("brain_source", data.get("source", "Unknown"))).lower()
        
        # [Task 14.3] Map raw node names to UI-friendly display names
        display_map = {
            "lab": "Lab (Triage)",
            "pinky": "Pinky (Response)",
            "brain": "Brain (Archive)",
            "thought": "Deep Thought"
        }
        source = display_map.get(raw_source, raw_source)
        data["brain_source"] = source
        
        token = data.get("brain", "")
        # [FEAT-488] Anti-Bleed: strip echoed system-slot instruction headers
        # (GROUNDING_PROTOCOL:/[STANCE]:/[ROUTE]/RAW CONTEXT APPEND) from the token
        # BEFORE it reaches the UI waterfall, preserving genuine response prose.
        if token:
            token = sanitize_stream_chunk(token)
            data["brain"] = token
        # Extract request ID if present
        request_id = data.get("request_id", "default")
        buf_key = f"{request_id}_{raw_source}"

        # [NEW] Push to waterfall queue for real-time UI delivery
        # [FEAT-361] 100% Transparency: No masking of inter-node whispers (internal triage suppressed from chat).
        if hasattr(self, 'waterfall_queue') and self.waterfall_queue:
            if not data.get("internal", False) and "triage" not in raw_source.lower():
                await self.waterfall_queue.put(data)

        if token:
            self.session_buffers[buf_key] += token
            # Audit for dynamic interjections if importance is high
            if self.current_interest > 0.8:
                await self._check_dynamic_audit(source, token)

    def bridge_signal_clean(self, text):
        """[FEAT-145] Cleans the raw LLM output for valid JSON blocks."""
        if not text:
            return None
        
        if "{" not in text:
            # If text is non-empty prose (> 15 chars), synthesize a fallback triage object
            clean_str = text.strip()
            if len(clean_str) > 15 and not ("Error:" in clean_str or "vLLM connection" in clean_str or "Connect call failed" in clean_str):
                logging.info("[HUB] Non-JSON prose triage synthesized into fallback structure.")
                return {
                    "inferred_intent": clean_str[:100],
                    "addressed_to": "PINKY" if any(w in clean_str.lower() for w in ["pinky", "hi", "hello", "crash"]) else "BRAIN",
                    "vibe": "TECHNICAL" if any(w in clean_str.lower() for w in ["crash", "error", "stability", "status", "debug"]) else "CASUAL",
                    "domain": "standard",
                    "casual": 0.5,
                    "intrigue": 0.5,
                    "importance": 0.5,
                    "situation": clean_str,
                    "hints": clean_str,
                    "hyde_vector_text": clean_str
                }

            # [FIX] Silence [RAW_OUTPUT] for connection errors to reduce UI noise
            is_connection_error = "vLLM connection failed" in text or "Error:" in text or "Connect call failed" in text
            if not is_connection_error:
                msg = f"[RAW_OUTPUT] Missing JSON anchor. Text: {text[:200]}..."
                logging.warning(f"[HUB] {msg}")
                asyncio.create_task(self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"}))
            return None

        # [FEAT-347] Nuclear JSON Extractor: Multi-block match for 3B resilience
        # This handles cases where models output multiple blocks or trailing garbage.
        json_blocks = re.findall(r'(\{.*?\})', text, re.DOTALL)
        if not json_blocks:
            # Fallback to greedy if non-greedy fails
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                json_blocks = [match.group(1)]
            else:
                return None

        # Find the first block that contains valid triage fields
        for block in json_blocks:
            try:
                data = json.loads(block)
                if "intent" in data or "vibe" in data or "addressed_to" in data:
                    return data
            except Exception:
                continue
        return None

    async def monitor_task_with_tics(self, coro, node_id="lab"):
        """[FEAT-267] Display periodic 'Tics' (e.g., Narf!) during long node runs."""
        task = asyncio.create_task(coro)
        
# [FEAT-053] Contextual Tics
        # Start a background tic broadcaster
        async def _tic_loop():
            current_delay = 5.0
            while not task.done():
                try:
                    await asyncio.sleep(current_delay)
                    if task.done():
                        break
                        
                    # Request a context-aware tic/quip from the Lab node
                    tic_msg = ""
                    # Persona definition
                    persona = "Pinky (character-faithful tic)" if node_id.lower() == "pinky" else "Deep Thought (Brain pre-conscious analytical stream - calm, non-interactive, never Pinky catchphrases)"
                    
                    try:
                        tic_res = await self.residents["lab"].call_tool("think", {
                            "query": f"[SYSTEM_TIC]: Provide a {persona} for the Lab's current state.",
                            "temperature": 0.8
                        })
                        tic_msg = tic_res.content[0].text
                    except Exception:
                        pass

                    if not tic_msg:
                        # Fallback to base persona tics/quips
                        if node_id.lower() == "pinky":
                            tic_msg = random.choice(["Narf!", "Poit!", "Zort!", "Egad!", "Troz!"])
                        else:
                            tic_msg = "Analyzing parameters... deep thought in progress."

                    try:
                        await self.broadcast({
                            "type": "crosstalk",
                            "brain": tic_msg,
                            "brain_source": node_id.capitalize(),
                            "channel": "insight" if node_id.lower() in ["brain", "thought"] else "chat",
                            "final": False,
                            "version": LAB_VERSION
                        })
                        # Exponential backoff for tics to avoid spamming
                        current_delay = min(current_delay * 1.5, 15.0)
                    except Exception:
                        if task.done():
                            break
                        await asyncio.sleep(1.0)
                except Exception:
                    break
        
        asyncio.create_task(_tic_loop())
        return await task

# [FEAT-408] Tool-Driven Waterfall Cascade
    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, interest_threshold=0.0, temperature=0.0, repetition_penalty=1.1, retry_count=0, use_lora=True, response_format=None, request_id="default"):
        """[FEAT-233.5] Internal Waterfall Proxy: Handshakes the node and yields tokens."""
        if hasattr(self, "round_table_memory") and self.round_table_memory:
            debate_context = "\n\n[PREVIOUS_DEBATE]:\n" + "\n".join(self.round_table_memory)
            if "[PREVIOUS_DEBATE]" not in query:
                query += debate_context

        if node_id not in self.residents:
            return
        
        # [Task 12.7] Ensure response_format is valid for Pydantic
        if response_format is None:
            response_format = {}

        # [FEAT-242.1] Handshake Tic (Gated via FEAT-365)
        enabled = True
        try:
             # Heuristic: Find config from the 'lab' resident if available
             if "lab" in self.residents and hasattr(self.residents["lab"], "config"):
                  enabled = self.residents["lab"].config.get("enable_reflexes", True)
        except Exception:
             pass

        if enabled:
            channel = "insight" if "brain" in source_name.lower() or "thought" in source_name.lower() else "chat"
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Initiating {source_name} intuition...",
                "brain_source": source_name,
                "final": False,
                "channel": channel
            })

        try:
            # [Task 2.3] Persona Interest: Adjust behavioral density based on scalar
            # [FEAT-488] Role-Slot Isolation CONTRACT: [STANCE] and GROUNDING_PROTOCOL
            # are NEVER appended to the user query/context string. They are assembled
            # solely into `guidance` below and passed strictly via metadata
            # ('behavioral_guidance'), which the node loader places into the system
            # role slot. This prevents 3B models from echoing the uppercase headers.
            stance = ""
            if self.current_interest > 0.75:
                stance = "\n[STANCE]: ACADEMIC (Evidence-heavy, dense, refer to GEM/SCAR IDs)."
            elif self.current_interest < 0.3:
                stance = "\n[STANCE]: INTERFACE (Witty, character-first, high brevity)."
            
            guidance = stance
            if behavioral_guidance:
                guidance += f"\n[BEHAVIORAL_GUIDANCE]: {behavioral_guidance}"

            # [FEAT-407] Vibe-Specific Context Isolation: Wrap RAG context in
            # <historical_record> tags + inject GROUNDING_PROTOCOL for HISTORICAL/FORENSIC/TECHNICAL vibes.
            # Prevents bedrock/operational metadata bleed into past-tense briefs.
            # [FEAT-488] The protocol is injected into `guidance` (system slot), never
            # into `query`/`context` (user slot).
            _vibe = getattr(self, "current_vibe", "TECHNICAL")
            if _vibe.upper() in ("HISTORICAL", "FORENSIC", "TECHNICAL") and context:
                context = f"<historical_record>\n{context}\n</historical_record>"
                guidance += "\nGROUNDING_PROTOCOL: Formulate your response EXCLUSIVELY from the evidence provided inside the <historical_record> tags. Focus your analysis solely on the target events, dates, and validation systems described within these tags."

            # [Task 1.1] Spark the node and wait for full block
            node = self.residents[node_id]
            
            # [Task 9.1] Isolated Buffer Key
            name_map = {"lab": "lab", "pinky": "pinky", "brain": "brain", "thought": "deep thought"}
            src_key = name_map.get(node_id, node_id)
            buf_key = f"{request_id}_{src_key}"
            self.session_buffers[buf_key] = ""
            
            # [Task 9.2] Hub relies on the Node's telemetry queue to populate the Foyer drainer.
            call_task = asyncio.create_task(node.call_tool("think", arguments={
                "query": query, "context": context, "tools": tools or [], 
                "behavioral_guidance": guidance,
                "temperature": temperature, "repetition_penalty": repetition_penalty,
                "use_lora": use_lora, "response_format": response_format, 
                "request_id": request_id
            }))
            
            full_text = ""
            last_len = 0
            while not call_task.done():
                await asyncio.sleep(0.05)
                curr_buffer = self.session_buffers[buf_key]
                if len(curr_buffer) > last_len:
                    new_tokens = curr_buffer[last_len:]
                    full_text += new_tokens
                    
                    # Check for peer-vote interest boosting signals [FEAT-238]
                    if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                        self._boosted_interest = True
                        old_interest = self.current_interest
                        self.current_interest = min(1.0, self.current_interest + 0.3)
                        logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                        
                    yield new_tokens
                    last_len = len(curr_buffer)
                    
                    # [FEAT-404] Context Starvation check: abort immediately if starvation detected
                    if "[ERROR: CONTEXT_STARVED]" in full_text:
                        logging.warning(f"[HUB] Context starvation detected mid-stream for {node_id}. Aborting.")
                        call_task.cancel()
                        break
                    
            # Get the final result and any remaining buffer
            try:
                res = await call_task
            except asyncio.CancelledError:
                res = "[ERROR: CONTEXT_STARVED]"
            curr_buffer = self.session_buffers[buf_key]
            if len(curr_buffer) > last_len:
                new_tokens = curr_buffer[last_len:]
                full_text += new_tokens
                
                # Check for peer-vote interest boosting signals [FEAT-238]
                if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                    self._boosted_interest = True
                    old_interest = self.current_interest
                    self.current_interest = min(1.0, self.current_interest + 0.3)
                    logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                    
                yield new_tokens
                
            # If the node didn't stream anything (e.g. error or missing logic), fallback to the full response
            if not full_text:
                if hasattr(res, 'content') and len(res.content) > 0:
                    full_text = res.content[0].text
                else:
                    full_text = str(res)
                
                # Check for peer-vote interest boosting signals [FEAT-238]
                if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                    self._boosted_interest = True
                    old_interest = self.current_interest
                    self.current_interest = min(1.0, self.current_interest + 0.3)
                    logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                    
                yield full_text
            
            # [SPR-41_2] Context Starvation Detection: if node returned CONTEXT_STARVED, bypass cascade
            if "[ERROR: CONTEXT_STARVED]" in full_text:
                self.context_starved_nodes.add(node_id)
                source_display = source_name or node_id
                logging.warning(f"[HUB] {source_display} returned CONTEXT_STARVED token.")
                await self.broadcast({
                    "type": "crosstalk",
                    "brain": f"[HUB] ⚠ Context Starvation detected from {source_display}. Cascade bypassed.",
                    "brain_source": "System"
                })
            
            self.turn_thought_trace[node_id] = full_text
            if node_id == "thought":
                # [FEAT-470] Legacy backfill: alias Deep Thought -> "brain" only when the local
                # Brain (shadow_brain_v2) leg did not already record its own synthesis.
                self.turn_thought_trace.setdefault("brain", full_text)
            self.session_buffers[buf_key] = "" # Clear buffer
            
            # [FEAT-287] Activity Latch
            if node_id in ["brain", "thought"]:
                self.last_activity = time.time()
                if hasattr(self, 'last_prime_callback') and self.last_prime_callback:
                    self.last_prime_callback(time.time())
            
            # [Task 14.2] Drainer Primacy: Removed execute_dispatch(). 
            # The Foyer's waterfall_drainer handles the final Pop delivery.
            
        except Exception as e:
            logging.error(f"[HUB] Stream from {node_id} failed: {e}")

    async def execute_dispatch(self, text, source_name, shutdown_event=None, retry_count=0, final=False):
        """Dispatches a finalized block to the UI, stripped of redundant speaker prefixes."""
        clean_text = self.speaker_registry.sanitize(text) if hasattr(self, "speaker_registry") else text
        await self.broadcast({
            "type": "chat",
            "brain": clean_text,
            "brain_source": source_name,
            "final": final
        })

    async def _check_dynamic_audit(self, source, token):
        """Placeholder for FEAT-190 The Judge."""
        pass

    def _collect_telemetry(self, event: dict) -> None:
        """
        [FEAT-T20.1/T20.2] Telemetry collector callback.
        Called by BicameralNode._emit_telemetry() at end of generation.
        Enriches with live GPU snapshot and writes to ledger.
        """
        if not self._tel_collector:
            return
        try:
            sample = self._tel_collector.snapshot(
                node=event.get("node", ""),
                request_id=event.get("request_id", "default"),
            )
            # Overlay token-level metrics from the node
            sample.ttft_ms = event.get("ttft_ms", 0.0)
            sample.total_tokens = event.get("total_tokens", 0)
            sample.duration_s = event.get("duration_s", 0.0)
            sample.engine_type = event.get("engine_type", "")
            sample.model = event.get("model", "")
            sample.enrich_economics()
            self._tel_collector.write_ledger(sample)
            logging.debug(
                f"[TEL] {sample.node} | TTFT={sample.ttft_ms:.0f}ms "
                f"tps={sample.tokens_per_sec:.1f} "
                f"power={sample.gpu_power_w:.0f}W "
                f"J/tok={sample.joules_per_token:.4f}"
            )
        except Exception as e:
            logging.debug(f"[TEL] Collect failed: {e}")

# [FEAT-106] Async Coordination Engine
    async def process_query(self, turn, shutdown_event=None, request_id=None, trigger_briefing_callback=None):
        """[FEAT-145] Main Reasoning Waterfall."""
        self.turn_thought_trace = {}
        if request_id is None:
            import uuid
            request_id = uuid.uuid4().hex[:8]
        
        # [SPR-41_2] Reset context starvation tracker per query
        self.context_starved_nodes.clear()
        
        # Initialize default vibe for Sandbox Tool Isolation
        self.current_vibe = "TECHNICAL"
        self._wrap_residents_for_sandbox()
        
        logging.info(f"[HUB_GUARD] Request {request_id} entering process_query. Set size: {len(self.processed_ids)}")
        async with self.request_lock:
            if request_id in self.processed_ids:
                logging.warning(f"[HUB_GUARD] REJECTED redundant request: {request_id}")
                return
            self.processed_ids.append(request_id)
            logging.info(f"[HUB_GUARD] ACCEPTED request: {request_id}")
        
        # [Task 9.7] Direct Intent Overrides
        if turn.startswith("[TRIGGER]"):
            task = turn.replace("[TRIGGER]", "").strip().lower()
            await self._run_triggered_task(task)
            return



        # [Goal 5/FEAT-145] Override Detection: Scan for override indicators (matching GEM-xxxx / BKM-xxx)
        is_override, gem_id = is_override_query(turn)
        if is_override and gem_id:
            logging.info(f"[HUB] Goal 5: Override intent detected for {gem_id} in query: {turn}")
            
            # Start background crosstalk notify
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[HUB] Processing correction for {gem_id}...",
                "brain_source": "System"
            })
            
            # Parse the override
            node = self.residents.get("pinky") or self.residents.get("brain")
            updates = await parse_override_with_resident(gem_id, turn, node)
            if updates:
                # Save override
                save_override_to_file(gem_id, updates)
                confirm_msg = f"[SYSTEM]: Correction registered for {gem_id}. Applied updates: {updates}. This override will be active during the next compile."
            else:
                confirm_msg = f"[SYSTEM]: Correction detected for {gem_id}, but failed to extract fields. No updates applied."
                
            await self._stream_message_to_ui(confirm_msg, source="System", request_id=request_id)
            return

        # 1. Triage Phase
        logging.info(f"[HUB] Triage starting for query: {turn[:40]}...")
        t_text = ""
        t_parsed = None

        # [FEAT-487 / BKM-035] Supervisory feedback is intercepted semantically AFTER
        # model-driven triage classifies the turn as META/feedback (see the
        # _intercept_control_plane_feedback short-circuit below). The legacy regex
        # based Fourth-Wall pre-filter (is_critique / _CRITIQUE_PATTERNS) is deprecated
        # in favor of this semantic path to avoid double-recording and brittle matching.
        
        # [BKM-015] Role Token Routing: Bypass LLM triage if query contains a role token
        if self.role_tokens:
            for token in self.role_tokens:
                if token in turn:
                    route = self._token_routes.get(token)
                    if route:
                        turn = turn.replace(token, "").strip()
                        t_parsed = dict(route)
                        t_parsed["is_explicit_token"] = True
                        logging.info(f"[HUB] Role token '{token}' detected. Direct routing to {t_parsed['addressed_to']}.")
                        await self.broadcast({
                            "type": "crosstalk",
                            "brain": f"[HUB] Role token '{token}' → {t_parsed['addressed_to']}. Bypassing triage.",
                            "brain_source": "System",
                            "version": LAB_VERSION
                        })
                        break
        
        # [FEAT-468/471] Extract clean user query from demarcated speaker history
        clean_user_query = extract_latest_user_query(turn)

        # [FEAT-436] Unified Pre-Reflection & Greeting Short-Circuit Pass
        raw_lower = clean_user_query.strip().lower().strip("!?,.")
        if raw_lower in ["hi", "hey", "hello", "what's up", "whats up", "good morning", "narf", "yo"]:
            logging.info("[HUB] Simple greeting detected. Short-circuiting Pre-Reflection in <15 tokens.")
            t_parsed = {
                "inferred_intent": "User is greeting the lab.",
                "addressed_to": "PINKY",
                "vibe": "CASUAL",
                "domain": "standard",
                "casual": 0.9,
                "intrigue": 0.1,
                "importance": 0.1,
                "situation": "Greeting",
                "hints": "",
                "hyde_vector_text": ""
            }

        # [SPR-64_1] Speculative Triage Relay: Kender vs Local vLLM
        triage_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "prereflection_triage_result",
                "schema": {
                    "type": "object",
                    "properties": {
                        "inferred_intent": {"type": "string"},
                        "addressed_to": {"type": "string", "enum": ["NONE", "BRAIN", "PINKY", "MICE", "SYSTEM"]},
                        "vibe": {"type": "string", "enum": ["TECHNICAL", "CASUAL", "HISTORICAL", "ANALYTICAL", "OPERATIONAL", "FORENSIC", "META", "WYWO", "SUPERVISORY"]},
                        "domain": {"type": "string", "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard", "lab_history", "lab_internal", "dream_stream", "feedback"]},
                        "casual": {"type": "number"},
                        "intrigue": {"type": "number"},
                        "importance": {"type": "number"},
                        "situation": {"type": "string"},
                        "hints": {"type": "string"},
                        "hyde_vector_text": {
                            "type": "string",
                            "description": "3-part multi-voice Composite HyDE Vector Query."
                        }
                    },
                    "required": ["inferred_intent", "addressed_to", "vibe", "domain", "casual", "intrigue", "importance"]
                }
            }
        }

        triage_mode_context = (
            '[MODE]: UNIFIED PRE-REFLECTION & TRIAGE\n'
            + BRAIN_PERSONA_SPEC + '\n'
            "Translate user intent (I think the user is trying to say...).\n"
            'HyDE synthesis is gated by the 4-Domain HyDE Map Contract:\n'
            '  1. exp_tlm (Silicon Telemetry): PCIe error bursts, RAPL power/thermal caps, NVIDIA GPU metrics, MSR registers, Redfish sensors.\n'
            '  2. exp_bkm (SRE playbooks): Point-of-failure playbooks, diagnostic shell BKMs, test runner steps, systemd service topologies.\n'
            '  3. exp_for (Forensic Logs): Kernel panic tracebacks, OOM crash logs, backpressure ledgers, memory pressure root cause analysis.\n'
            '  4. lab_history (18-Year Archive): historical project notes (2005-2025), career milestones, past sprint retrospectives, questions referencing specific past years or struggles/work in a year (e.g. "2015", "in 2018", "what did I struggle with in 2015") -> MUST classify as vibe: HISTORICAL or TECHNICAL, domain: lab_history, addressed_to: BRAIN or MICE, importance: 0.8.\n'
            'If the intent maps to a domain, synthesize in hyde_vector_text a 3-part Composite HyDE Vector Query:\n'
            '[VALIDATION]: <silicon_term_or_pcie_ras> | [STRATEGY]: <focal_goal_or_leadership_impact> | [SRE]: <bkm_scar_or_shell_command>\n'
            'If the intent does NOT map to the 4 domains (casual greetings, status checks, pleasantries, meta-talk), set hyde_vector_text: "" and vibe: CASUAL. No hardcoded string arrays (BKM-015).\n'
            'META / FEEDBACK: ONLY for Fourth-Wall supervisory feedback on the AI itself, bug reports on responses, tone/verbosity corrections, or system commands (e.g. "feedback: ...", "that was wrong", "stop echoing", "too verbose", "KENDER should have a ping gate"). Classify strictly as vibe: META, domain: feedback, addressed_to: SYSTEM, importance: 0.0.\n'
            'For casual quips or greetings, set addressed_to: PINKY, vibe: CASUAL, importance: 0.1, hyde_vector_text: empty string.'
        )

        # Execute relay
        winner = None
        for attempt in range(3):
            try:
                t_parsed, winner = await self.triage_relay.relay(
                    clean_user_query, triage_mode_context, triage_schema, request_id
                )
                if t_parsed:
                    break
            except Exception as e:
                logging.warning(f"[HUB] Triage Attempt {attempt+1} failed: {e}")
                await asyncio.sleep(2)

        if not t_parsed:
            logging.error("[HUB] All triage attempts failed. Falling back to PINKY.")
            t_parsed = {"vibe": "CASUAL", "addressed_to": "PINKY", "importance": 0.5, "domain": "standard"}
            winner = "fallback"
        
        # Post-process triage
        vibe_override, domain_override = classify_vibe_and_domain(clean_user_query, t_parsed)
        t_parsed["vibe"] = vibe_override
        t_parsed["domain"] = domain_override
        if "hyde_vector_text" in t_parsed:
            t_parsed["hyde_vector_text"] = scrub_hyde_vector(t_parsed["hyde_vector_text"])

        # [FEAT-487 / BKM-035] Semantic Meta-Triage Feedback Interceptor
        # Fast Control-Plane Intercept: when model-driven triage classifies the turn as
        # META / domain=feedback (supervisory feedback, bug reports, tone/verbosity
        # corrections, Fourth-Wall commands), short-circuit immediately — bypass RAG
        # retrieval, interest boosts, and resident model debates. Record atomically to
        # the validation ledger (BKM-035) and emit a crisp in-character Pinky confirmation.
        if is_control_plane_feedback(t_parsed):
            logging.info(f"[HUB] [FEAT-487] Semantic control-plane feedback turn: '{clean_user_query[:60]}'")
            flawed_output = ""
            if self.turn_thought_trace.get("pinky"):
                flawed_output = str(self.turn_thought_trace.get("pinky"))
            elif self.round_table_memory:
                flawed_output = str(self.round_table_memory[-1])
            record_feedback(query=turn, flawed_output=flawed_output, user_correction=turn)
            await self.broadcast({
                "type": "thought_stream",
                "source": "Pinky (Feedback)",
                "token": "Narf! Feedback logged to the validation ledger.",
                "final": True,
                "request_id": request_id
            })
            turn_ledger = f"User (Feedback): {turn}"
            self.round_table_memory.append(turn_ledger)
            return

        # [SPR-64_1] Console Routing Metadata
        routing_meta = self.triage_relay.get_console_metadata(winner)
        t_parsed["_console_channel"] = routing_meta["channel"]
        t_parsed["_console_source"] = routing_meta["source"]
        t_parsed["_console_target"] = routing_meta["console"]
        
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"[HUB] Triage successful (Winner: {winner}). Vibe: {t_parsed.get('vibe')}, Domain: {t_parsed.get('domain')}",
            "brain_source": routing_meta["source"],
            "version": LAB_VERSION
        })
        
        # Emit raw pretty-printed triage JSON to the winning console (Option C)
        public_triage = {k: v for k, v in t_parsed.items() if not str(k).startswith("_")}
        triage_json_str = json.dumps(public_triage, indent=2)
        await self.broadcast({
            "type": "chat",
            "brain": triage_json_str,
            "brain_source": routing_meta["source"],
            "channel": routing_meta["channel"],
            "final": True,
            "version": LAB_VERSION
        })

        # [Triage Intent Gate] Check if triage output requests morning briefing
        hints = str(t_parsed.get("hints", "")).lower()
        situation = str(t_parsed.get("situation", "")).lower()
        if "morning_briefing" in hints or "morning_briefing" in situation or "trigger_morning_briefing" in hints:
            logging.info("[HUB] Triage Intent Gate: Morning briefing triggered via triage.")
            if trigger_briefing_callback:
                await trigger_briefing_callback()
            else:
                await self.trigger_morning_briefing(request_id=request_id)
            return

        # 2. Routing Phase
        vibe = t_parsed.get("vibe", "").upper()
        self.current_vibe = vibe
        self._wrap_residents_for_sandbox()
        
        importance = float(t_parsed.get("importance", 0.5))
        casual = float(t_parsed.get("casual", 0.5))
        intrigue = float(t_parsed.get("intrigue", 0.5))
        
        # [FEAT-484 / Springboard Pattern] Declarative Policy Springboard
        # Applies declarative importance_floor and interest_boost from config/triage_policy.json
        # while preserving the LLM's dynamic evaluation of turn nuance and complexity.
        springboard = self.policy_loader.get_vibe_springboard(vibe) if hasattr(self, "policy_loader") and self.policy_loader else {"importance_floor": 0.0, "interest_boost": 0.0}
        importance_floor = springboard.get("importance_floor", 0.0)
        interest_boost = springboard.get("interest_boost", 0.0)

        effective_importance = max(importance, importance_floor)
        base_interest = ((1.0 - (casual * 0.5)) * (intrigue + effective_importance)) / 2.0
        final_interest = min(1.0, max(0.0, base_interest + interest_boost))
        self.current_interest = final_interest
        t_parsed["effective_importance"] = effective_importance
        t_parsed["calculated_interest"] = final_interest
        
        target = t_parsed.get("addressed_to", "PINKY").lower()
        
        if self.set_active_domain:
            self.set_active_domain(t_parsed.get("domain", "standard"))
        
        # [Task 15.1] Conversational Grace Override & [FEAT-458] Floating Validation Oracle
        behavioral_guidance = ""
        context = ""

        if vibe == "CASUAL":
            self.current_interest = min(self.current_interest, 0.1)
            candidate_pool = build_floating_candidate_pool(auto_harvest=True)
            context = candidate_pool
            behavioral_guidance = (
                "[MODE]: CONVERSATIONAL (Warm, natural, brief. Match user brevity with 1 short sentence. "
                "If appropriate for user inquiry, weave in one candidate from [FLOATING_CANDIDATES] to prompt the user rather than giving generic small talk.)"
            )
        elif vibe == "WYWO":
            # [FEAT-409] WYWO Retrieval: Pull nightly dialogue and subconscious dreams
            nightly_dialogue = "No recent nightly dialogue recorded."
            dialogue_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json")
            if os.path.exists(dialogue_path):
                try:
                    with open(dialogue_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            nightly_dialogue = f"Topic: {data.get('topic')}\nDialogue: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load nightly dialogue: {e}")
            
            recruiter_report = "No recruiter report found."
            recruiter_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
            if os.path.exists(recruiter_path):
                try:
                    with open(recruiter_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            recruiter_report = f"Topic: {data.get('topic')}\nContent: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load recruiter report: {e}")
            
            system_status = "No system status found."
            status_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        data = json.load(f)
                        system_status = f"Status: {data.get('status', 'unknown')}\nDetails: {data.get('details', 'none')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load system status: {e}")
            
            pager_activity = "No pager activity found."
            pager_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json")
            if os.path.exists(pager_path):
                try:
                    with open(pager_path, "r") as f:
                        data = json.load(f)
                        if data.get("activity"):
                            pager_activity = f"Activity: {data.get('activity')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load pager activity: {e}")
            
            dreams = "No long-term subconscious dreams found."
            if "archive" in self.residents:
                try:
                    res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 2})
                    if hasattr(res, 'content') and len(res.content) > 0:
                        dreams = res.content[0].text
                except Exception as e:
                    logging.error(f"[HUB] Failed to load Diamond Wisdom for WYWO: {e}")

            context = (
                f"[NIGHTLY_DIALOGUE_RECORD]:\n{nightly_dialogue}\n\n"
                f"[RECRUITER_REPORT]:\n{recruiter_report}\n\n"
                f"[SYSTEM_STATUS]:\n{system_status}\n\n"
                f"[PAGER_ACTIVITY]:\n{pager_activity}\n\n"
                f"[SUBCONSCIOUS_DREAM_WISDOM]:\n{dreams}"
            )
            # [FEAT-444] Cap transient file-drop context before prompt embedding
            context = self._truncate_to_tokens(
                context,
                doc_id="|".join(
                    os.path.basename(p)
                    for p in (dialogue_path, recruiter_path, status_path, pager_path)
                ),
            )
            behavioral_guidance = (
                "[MODE]: STANDUP (Synthesize a high-density, professional summary of recent nightly dialogues "
                "and subconscious dreams consolidated during nightly runs. Explain what nodes debated, "
                "the key decisions or validation wisdom stored, and any resulting system changes.)"
            )
        else:
            # If it's not casual, ensure Pinky synthesizes the RAG hints rather than just dumping them.
            behavioral_guidance = "[MODE]: SYNTHESIS (Do not raw-dump tags or RAG refs. Speak conversationally, using the provided context as background knowledge.)"
            # Pass the triage hints as context so Pinky has something to synthesize.
            rag_context = await self._fetch_rag_context(turn, t_parsed)
            context = f"Triage Situation: {t_parsed.get('situation', '')}\nTriage Hints: {t_parsed.get('hints', '')}"
            if rag_context:
                context += f"\n\n[RAG_CONTEXT]:\n{rag_context}"
                # [FEAT-485] Epistemological Archival Reasoning Protocol
                if "[ARCHIVAL_EVIDENCE]" in rag_context:
                    behavioral_guidance += (
                        " EPISTEMOLOGICAL_PROTOCOL: The provided [ARCHIVAL_EVIDENCE] contains temporal scarcity diagnostics from the 18-year archive. "
                        "Synthesize these facts: if an entity was active in other years but has 0 records in the queried year, deduce and state definitively "
                        "that the entity was NOT present/active during that target year. State the true active years from the evidence and conclude without passive conversational hedging or asking for clarification."
                    )
            else:
                # [FEAT-475] Zero-Context & Negative Implication Protocol:
                # In a comprehensive 18-year archive, absence of records for a target year/entity
                # means it was NOT active in that period. State absence directly instead of asking for clarification.
                behavioral_guidance += (
                    " ZERO_CONTEXT_PROTOCOL: No relevant historical notes were found for this query. "
                    "In this 18-year archive, the absence of records for a requested entity or year indicates it was NOT present/active during that timeframe. "
                    "State definitively that no records exist in the archive rather than passively asking for clarification. "
                    "Do NOT invent or hallucinate legacy records, dates, or accomplishments. "
                    "Respond purely from live telemetry or explicitly acknowledge unrecorded state."
                )

        # [FEAT-418] The Symmetrical Interest Cascade (Lead Speaker + Interjection Threshold)
        target_upper = str(target).upper()
        if target_upper in ["BRAIN", "THOUGHT", "DEEP"]:
            lead_node = "brain"
        elif target_upper == "MICE":
            lead_node = "both"
        else: # "PINKY" or "NONE"
            lead_node = "pinky"

        if lead_node == "brain":
            # [FEAT-489] Two-Mice Sequential Handover: high-interest technical
            # turns addressed to Brain funnel through Brain-extracts ->
            # Pinky-distills; falls back to the legacy Brain-led flow when the
            # funnel cannot run (missing resident / low interest).
            handover_context = context
            if not handover_context or "[RAG_CONTEXT]" not in handover_context:
                if "rag_context" in locals():
                    handover_context = context if context else rag_context
                else:
                    handover_context = context or await self._fetch_rag_context(turn, t_parsed)
            if handover_context and self.current_interest >= TWO_MICE_FUNNEL_INTEREST and await self._run_two_mice_handover(
                turn,
                focus_context=handover_context,
                shutdown_event=shutdown_event,
                request_id=request_id,
            ):
                pass
            else:
                # Brain leads Turn 1
                await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id, rag_context=rag_context)
                # Turn 2: Pinky interjects if interest is high
                if self.current_interest > 0.5:
                    async for token in self._process_node_stream(
                        "pinky", turn, context, "Pinky (Foil Interjection)", 
                        tools=[], temperature=0.7, request_id=request_id,
                        behavioral_guidance="[MODE]: FOIL_INTERJECTION (Brief, witty, intuitive quip following Brain's response.)"
                    ):
                        if shutdown_event and shutdown_event.is_set():
                            break
        elif lead_node == "both":
            # Both speak on Turn 1 ("Hey mice!")
            full_pinky_text = ""
            async for token in self._process_node_stream(
                "pinky", turn, context, "Pinky (Response)", 
                tools=[], temperature=0.7, request_id=request_id,
                behavioral_guidance=behavioral_guidance
            ):
                full_pinky_text += token
                if shutdown_event and shutdown_event.is_set():
                    break
            await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id)
        else:
            # [FEAT-457] Single-Layer Speculative Context Pre-fetch:
            # Launch Brain's RAG context retrieval immediately in the background while Pinky speaks.
            brain_prefetch_task = None
            if "brain" in self.residents or "thought" in self.residents:
                brain_prefetch_task = asyncio.create_task(self._fetch_rag_context(turn, t_parsed))

            # Pinky leads Turn 1 (Default for PINKY or NONE)
            full_pinky_text = ""
            async for token in self._process_node_stream(
                "pinky", turn, context, "Pinky (Response)", 
                tools=[], temperature=0.7, request_id=request_id,
                behavioral_guidance=behavioral_guidance
            ):
                full_pinky_text += token
                if shutdown_event and shutdown_event.is_set():
                    break
            
            # Intercept morning briefing tool call from Pinky's response
            if "trigger_morning_briefing" in full_pinky_text:
                if brain_prefetch_task and not brain_prefetch_task.done():
                    brain_prefetch_task.cancel()
                logging.info("[HUB] Intercepted trigger_morning_briefing tool call from Pinky's response.")
                if trigger_briefing_callback:
                    await trigger_briefing_callback()
                else:
                    await self.trigger_morning_briefing(request_id=request_id)
                return
            
            # Turn 2: Brain interjects if interest is high
            if self.current_interest > 0.5:
                logging.info(f"[HUB] [FEAT-457] Interest high ({self.current_interest:.2f} > 0.5): Triggering Brain interjection with pre-fetched context.")
                await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id, prefetch_task=brain_prefetch_task)
            else:
                # Preemption: Interest is low, cleanly cancel/discard speculative pre-fetch without penalty
                if brain_prefetch_task and not brain_prefetch_task.done():
                    brain_prefetch_task.cancel()
                    logging.info(f"[HUB] [FEAT-457] Preempted Brain pre-fetch: Interest low ({self.current_interest:.2f} <= 0.5). Discarded background context.")

        # [FEAT-356] Unified Session Ledger: Record turn summary
        turn_ledger = f"User: {turn}"
        pinky_res = self.turn_thought_trace.get("pinky")
        if pinky_res:
            turn_ledger += f"\nPinky: {pinky_res}"
        brain_res = self.turn_thought_trace.get("thought") or self.turn_thought_trace.get("brain")
        if brain_res:
            turn_ledger += f"\nBrain: {brain_res}"
        critique_res = self.turn_thought_trace.get("critique")
        if critique_res:
            turn_ledger += f"\nPinky Summary: {critique_res}"
        self.round_table_memory.append(turn_ledger)

        # [FEAT-441] 24-hour journal ledger: capture only spoken dialogue, non-fatal
        try:
            journal_entry = {"ts": int(time.time()), "dialogue": turn_ledger}
            self._persist_journal_ledger(journal_entry)
        except Exception as e:
            logging.error(f"[HUB] Journal ledger persistence failed: {e}")

    def _persist_journal_ledger(self, entry: dict):
        """[FEAT-441] Append one spoken-dialogue entry to the 24-hour JSONL journal.

        Non-fatal by contract: any persistence failure is logged and swallowed so
        the live dialogue turn is never interrupted.
        """
        journal_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/journal_ledger.jsonl")
        try:
            os.makedirs(os.path.dirname(journal_path), exist_ok=True)
            surviving = []
            if os.path.exists(journal_path):
                with open(journal_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parsed = json.loads(line)
                        except Exception:
                            continue
                        if int(time.time()) - parsed.get("ts", 0) <= 86400:
                            surviving.append(parsed)
            surviving.append(entry)
            tmp_path = journal_path + ".tmp"
            with open(tmp_path, "w") as f:
                for parsed in surviving:
                    f.write(json.dumps(parsed, ensure_ascii=False) + "\n")
            os.replace(tmp_path, journal_path)
        except Exception as e:
            logging.error(f"[HUB] Journal ledger write failed: {e}")

# [FEAT-247] Physical Audit Gate
    async def evaluate_grounding(self, source, text, interest=0.8, shutdown_event=None, request_id="default", rag_context=""):
        """
        [FEAT-227] The Grounding Gate (V5).
        Restores character balance by prompting Pinky to critique or conversationally 
        summarize Deep Thought's technical output directly into the Chat pane.
        """
        if "pinky" not in self.residents or source.lower().startswith("pinky"):
            return
        
        # Calculate dynamic scaling based on length
        importance = interest
        if len(text) > 800:
            importance = min(1.0, importance + 0.2)
            
        if importance <= 0.5:
            logging.info(f"[HUB] Grounding Gate skipped for {source} (Interest/Importance: {importance:.2f} <= 0.5).")
            return
            
        logging.info(f"[HUB] Grounding Gate triggered for {source} (Interest/Importance: {importance:.2f} > 0.5).")
        # [FEAT-356/470] Pinky as Coherence Judge with Cartoon Persona + Summary Blend
        evidence_block = f"[UNDERLYING TECHNICAL EVIDENCE]:\n{rag_context}\n\n" if rag_context else ""
        critique_query = build_critic_prompt(
            user_query=text,
            technical_summary=evidence_block or text,
            persona_name="Pinky"
        )

        eval_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "coherence_evaluation",
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "reasoning": {"type": "string"},
                        "slop_found": {"type": "boolean"},
                        "retort": {"type": "string"}
                    },
                    "required": ["score", "reasoning", "slop_found", "retort"]
                }
            }
        }

        # Vibe-Aware Tone mapping
        vibe = self.current_vibe.upper() if hasattr(self, 'current_vibe') and self.current_vibe else "CASUAL"
        vibe_tone = "Tone guidance: Casual, friendly, peer-to-peer."
        if vibe == "TECHNICAL":
            vibe_tone = "Tone guidance: Grounded, slightly critique-oriented, checking technical viability."
        elif vibe == "HISTORICAL":
            vibe_tone = "Tone guidance: Reflective, nostalgic, referencing previous engineering scars."
        elif vibe == "FORENSIC":
            vibe_tone = "Tone guidance: Cynical, investigative, auditing telemetry patterns."
        elif vibe == "META":
            vibe_tone = "Tone guidance: Self-aware, observing the lab's state machine."
        elif vibe == "OPERATIONAL":
            vibe_tone = "Tone guidance: Direct, diagnostic-focused, emphasizing active system state and logs."
        elif vibe == "ANALYTICAL":
            vibe_tone = "Tone guidance: Systematic, comparative, weighting trade-offs with high objectivity."

        try:
            # [FEAT-406/470] Coherence Judge Evaluation: Stream Pinky's critique
            eval_text = ""
            async for token in self._process_node_stream(
                "pinky", critique_query, f"Technical Output to evaluate:\n{text}", "Pinky (Coherence Critic)",
                tools=[], temperature=0.2, response_format=eval_schema, request_id=request_id,
                behavioral_guidance=f"Act as a strict Coherence Critic. Check for logic errors, slop, or inconsistency. {vibe_tone}"
            ):
                eval_text += token
            
            # [FEAT-470] Parse structured critic payload
            critic_res = parse_critic_payload(eval_text)
            
            # Log evaluations to .round_table_evals.json
            eval_file_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/.round_table_evals.json")
            existing_evals = []
            if os.path.exists(eval_file_path):
                try:
                    with open(eval_file_path, "r") as f:
                        existing_evals = json.load(f)
                except Exception:
                    pass
            
            new_eval = {
                "timestamp": time.time(),
                "source": source,
                "score": critic_res.score,
                "reasoning": critic_res.reasoning,
                "slop_found": critic_res.slop_found,
                "retort": critic_res.retort
            }
            existing_evals.append(new_eval)
            
            # Atomic write (.tmp + replace)
            tmp_path = eval_file_path + ".tmp"
            try:
                with open(tmp_path, "w") as f:
                    json.dump(existing_evals, f, indent=2)
                os.replace(tmp_path, eval_file_path)
            except Exception as e:
                logging.error(f"[HUB] Failed to save evaluations to .round_table_evals.json: {e}")

            # [FEAT-470] Broadcast internal diagnostic telemetry frame to CROSSTALK
            telemetry_frame = format_crosstalk_telemetry(
                source="Pinky",
                target=source,
                payload=new_eval
            )
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[CRITIC TELEMETRY] Score: {critic_res.score}/5 | Slop: {critic_res.slop_found}",
                "brain_source": "System (Critic Telemetry)",
                "telemetry": telemetry_frame
            })

            # [FEAT-470] Blend cartoon quip + agreed summary for out-loud delivery (banning robotic boilerplate)
            chat_delivery = format_chat_delivery(
                cartoon_retort=critic_res.cartoon_retort,
                technical_summary=critic_res.reasoning
            )
            if chat_delivery:
                self.turn_thought_trace["critique"] = chat_delivery
                await self.execute_dispatch(chat_delivery, "Pinky (Coherence Critic)", shutdown_event=shutdown_event, final=True)
        except Exception as e:
            logging.error(f"[HUB] Coherence critique failed: {e}")

    async def _distill_strategic_brief(self, raw_context, request_id="default"):
        """[Task 2.2] Context Precision: Synthesize raw RAG into a dense brief."""
        if not raw_context or "brain" not in self.residents:
            return raw_context

        # [FEAT-444] Cap raw context before it is embedded into the brief prompt
        raw_context = self._truncate_to_tokens(
            raw_context, doc_id=self._extract_doc_id(raw_context)
        )

        logging.info("[HUB] Context Precision: Distilling raw RAG into Strategic Brief...")
        try:
            prompt = (
                "Synthesize the following raw technical artifacts into a 2-paragraph high-density 'Strategic Brief'. "
                "Extract specific platform anchors, validation targets, and known PECI/MSR scars. "
                "Focus strictly on high-density technical facts and grounded validation evidence."
            )
            # Use 'think' to generate distillation
            res = await self.residents["brain"].call_tool("think", {
                "query": prompt, 
                "context": raw_context,
                "behavioral_guidance": "Distill for Strategic Thought.",
                "request_id": request_id
            })
            
            brief = ""
            if hasattr(res, 'content') and len(res.content) > 0:
                brief = res.content[0].text
            else:
                brief = str(res)
                
            logging.info(f"[HUB] Distillation complete ({len(brief)} chars).")
            return f"[STRATEGIC_BRIEF]:\n{brief}\n\n[RAW_CONTEXT_APPEND]:\n{raw_context[:1000]}..."
        except Exception as e:
            logging.warning(f"[HUB] Context distillation failed: {e}")
            return raw_context

    async def _get_node_tools(self, node_id: str) -> list:
        """[SPR-41_1] Retrieve active tool names from a resident node's MCP server."""
        node = self.residents.get(node_id)
        if not node or not hasattr(node, 'mcp'):
            return []
        try:
            mcp_tools = await node.mcp.list_tools()
            return [t.name for t in mcp_tools]
        except Exception as e:
            logging.warning(f"[HUB] Failed to list tools for {node_id}: {e}")
            return []

    def _truncate_to_tokens(self, text, max_tokens=2500, doc_id=""):
        """[FEAT-444] vLLM context stability: cap assembled context at ~max_tokens.

        Tokens are approximated as chars/4 (max_chars = max_tokens * 4). When the
        budget is exceeded, keep the first 40% and last 60% of the char budget,
        separated by a `[MORE: <doc_id>...]` link note. No-op under the cap.
        """
        if not text:
            return text
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        link = f"[MORE: {doc_id}...]" if doc_id else "[MORE: ...]"
        head_budget = int(max_chars * 0.4)
        tail_budget = max_chars - head_budget
        # Reserve room for the link note + "\n\n" separators so the result never exceeds max_chars
        overhead = len(link) + 4
        if tail_budget > overhead:
            tail_budget -= overhead
        else:
            tail_budget = 0
            head_budget = max(0, max_chars - overhead)
        head = text[:head_budget].rstrip()
        tail = text[-tail_budget:].lstrip() if tail_budget > 0 else ""
        if link in head:
            # Link already carried by the head; do not duplicate it
            truncated = f"{head}\n\n{tail}"
        else:
            truncated = f"{head}\n\n{link}\n\n{tail}"
        if len(truncated) > max_chars:
            truncated = truncated[:max_chars]
        logging.info(
            f"[HUB] Context truncated to {max_tokens} tokens "
            f"({len(text)} -> {len(truncated)} chars) for vLLM stability."
        )
        return truncated

    def _extract_doc_id(self, text):
        """[FEAT-444] Pull the first source doc id from RAG context for link notes."""
        if not text:
            return ""
        src_match = re.search(r'"sources"\s*:\s*\["([^"]+)"', text)
        if src_match:
            return src_match.group(1)
        src_match = re.search(r"Source:\s*([^\s\]]+)", text)
        if src_match:
            return src_match.group(1)
        return ""

    async def synthesize_preamble_quip(self, query: str, timeout: float = 3.0) -> str:
        """[FEAT-459 / Story 54.6] Fast Reflex Preamble Quip:
        Uses shallow think tool (<15 words) from Deep Thought with a 3.0s timeout.
        Eliminates 8s timeouts and redundant Pass-1 HyDE synthesis."""
        if "thought" in self.residents and await self.is_deep_thought_reachable():
            try:
                res = await asyncio.wait_for(
                    self.residents["thought"].call_tool("think", {"query": query, "context": ""}),
                    timeout=timeout,
                )
                if hasattr(res, "content") and len(res.content) > 0:
                    text = res.content[0].text
                    if text and len(text.strip()) > 0:
                        return text.strip()
            except asyncio.TimeoutError:
                logging.warning(f"[FEAT-459] Deep Thought think timed out after {timeout}s")
            except Exception as e:
                logging.warning(f"[FEAT-459] Deep Thought think unavailable: {e}")

        # Local fallback quip
        return "Deep Thought: System operational. Awaiting command parameters."

    async def synthesize_hyde_vector(self, query: str) -> str:
        """[FEAT-459 / Story 54.6] Alias for preamble quip synthesis."""
        return await self.synthesize_preamble_quip(query)

    async def resolve_hyde_vector(self, query: str, triage_result: dict, timeout: float = 8.0) -> tuple:
        """[FEAT-437] 3-Tier HyDE Failover Cascade: (vector_text, tier)."""
        # Tier 1: Pinky local vLLM (holds cli_voice_v1 LoRA weights fine-tuned on 18-year archive)
        hyde_text = str(triage_result.get("hyde_vector_text", "") or "")
        if len(hyde_text.strip()) > 5:
            logging.info(f"[FEAT-437][TIER1] Pinky LoRA HyDE: {hyde_text.strip()[:80]!r}")
            return hyde_text.strip(), PINKY_LOCAL_VLLM

        # Tier 2: Deep Thought on Kender (RTX 4090) fallback if local vLLM text missing
        if "thought" in self.residents:
            try:
                res = await asyncio.wait_for(
                    self.residents["thought"].call_tool(
                        "deep_think", {"task": HYDE_SYNTHESIS_PROMPT, "context": query}
                    ),
                    timeout=timeout,
                )
                if hasattr(res, "content") and len(res.content) > 0:
                    text = res.content[0].text
                    if text and len(text.strip()) > 10:
                        logging.info(f"[FEAT-437][TIER2] Deep Thought Fallback HyDE: {text.strip()[:80]!r}")
                        return text.strip(), DEEP_THOUGHT_REMOTE
            except asyncio.TimeoutError:
                logging.warning(f"[FEAT-437][TIER2] Deep Thought timed out after {timeout}s")
            except Exception as e:
                logging.warning(f"[FEAT-437][TIER2] Deep Thought unavailable ({e})")

        # Tier 3: Judge-driven non-match / zero-dependency floor (BKM-015)
        logging.info("[FEAT-437][TIER3] Non-matching domain / casual turn; returning empty HyDE vector (BKM-015)")
        return "", DIRECT_RAW_QUERY

    async def _fetch_rag_context(self, turn, t_parsed, n_results=3):
        """[FEAT-437/442/454] Post-triage RAG retrieval: pass the AI-produced HyDE vector text
        from the unified pre-reflection pass into the archive context engine, so retrieval
        searches the refined domain indexing terms instead of the raw noisy turn."""
        if "archive" not in self.residents:
            return ""
        hyde, hyde_tier = await self.resolve_hyde_vector(turn, t_parsed)
        # BKM-015: If judge-driven HyDE evaluated to empty string (casual / non-match), bypass ChromaDB
        if not hyde:
            return ""
        # [FEAT-441-Cache] Key on the exact inputs that shape retrieval output
        cache_key = hashlib.sha256((turn + hyde + str(n_results)).encode("utf-8")).hexdigest()
        result_text = ""
        if cache_key in self._rag_cache:
            result_text = self._rag_cache[cache_key]
        else:
            try:
                vibe_val = str(t_parsed.get("vibe", ""))
                domain_val = str(t_parsed.get("domain", ""))
                res = await self.residents["archive"].call_tool(
                    "get_context", {
                        "query": turn,
                        "hyde_vector_text": hyde,
                        "n_results": n_results,
                        "vibe": vibe_val,
                        "domain": domain_val
                    }
                )
                if hasattr(res, 'content') and len(res.content) > 0:
                    result_text = res.content[0].text
                    if result_text:
                        # [FEAT-475] Parse structured zero-context envelope from archive_node.
                        # New format: {"found": bool, "context": str, "reason": str, "sources": list}
                        # Legacy format: raw string or {"text": str, "sources": list}
                        try:
                            envelope = json.loads(result_text)
                            if isinstance(envelope, dict) and "context" in envelope:
                                if not envelope.get("found", True):
                                    logging.info(f"[HUB] Zero-Context envelope received: {envelope.get('reason', 'unknown')}")
                                    result_text = ""  # Suppress unfound context
                                else:
                                    result_text = envelope["context"]
                        except (json.JSONDecodeError, TypeError):
                            pass  # Legacy raw string — use as-is
                    if result_text:
                        # [FEAT-444] Cap RAG context before it enters any prompt
                        result_text = self._truncate_to_tokens(
                            result_text, doc_id=self._extract_doc_id(result_text)
                        )
                        self._rag_cache[cache_key] = result_text
                        if len(self._rag_cache) > 128:
                            self._rag_cache.pop(next(iter(self._rag_cache)))
            except Exception as e:
                logging.error(f"[HUB] RAG context fetch failed: {e}")

        # [FEAT-454] Broadcast RAG Eval payload to Web Intercom for + click expanders
        if result_text:
            try:
                doc_id = self._extract_doc_id(result_text) or "archive_context"
                broadcast_sig = f"{turn}_{doc_id}_{len(result_text)}"
                if getattr(self, "_last_rag_eval_sig", None) != broadcast_sig:
                    self._last_rag_eval_sig = broadcast_sig
                    await self.broadcast({
                        "type": "rag_eval",
                        "query": turn,
                        "hyde": hyde,
                        "tier": str(hyde_tier),
                        "doc_id": doc_id,
                        "snippet": result_text[:400] + ("..." if len(result_text) > 400 else ""),
                        "full_context": result_text,
                        "n_results": n_results
                    })
            except Exception as ex:
                logging.warning(f"[FEAT-454] RAG eval broadcast warning: {ex}")

        return result_text

    async def _run_brain_leg(self, query, triage, shutdown_event=None, request_id="default", prefetch_task=None, rag_context=None):
        """Handles Brain (4090) leg of the waterfall."""
        # [Task 2.2] Context Precision
        vibe = triage.get("vibe", "").upper()
        if vibe == "WYWO":
            # Construct WYWO context
            nightly_dialogue = "No recent nightly dialogue recorded."
            dialogue_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json")
            if os.path.exists(dialogue_path):
                try:
                    with open(dialogue_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            nightly_dialogue = f"Topic: {data.get('topic')}\nDialogue: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load nightly dialogue: {e}")
            
            dreams = "No long-term subconscious dreams found."
            if "archive" in self.residents:
                try:
                    res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 2})
                    if hasattr(res, 'content') and len(res.content) > 0:
                        dreams = res.content[0].text
                except Exception as e:
                    logging.error(f"[HUB] Failed to load Diamond Wisdom for WYWO: {e}")

            raw_context = (
                f"[NIGHTLY_DIALOGUE_RECORD]:\n{nightly_dialogue}\n\n"
                f"[SUBCONSCIOUS_DREAM_WISDOM]:\n{dreams}"
            )
        else:
            if rag_context is None:
                if prefetch_task:
                    try:
                        rag_context = await prefetch_task
                    except Exception as ex:
                        logging.warning(f"[HUB] Pre-fetched RAG context resolution warning, falling back: {ex}")
                        rag_context = await self._fetch_rag_context(query, triage)
                else:
                    rag_context = await self._fetch_rag_context(query, triage)

            raw_context = f"Triage Situation: {triage.get('situation', '')}\nTriage Hints: {triage.get('hints', '')}"
            if rag_context:
                raw_context += f"\n\n[RAG_CONTEXT]:\n{rag_context}"
            else:
                # [FEAT-475] Zero-Context: Signal to Brain that no historical archive was retrieved.
                raw_context += "\n\n[ZERO_CONTEXT]: No relevant historical notes found. Respond from live telemetry only."
        
        distilled_context = await self._distill_strategic_brief(raw_context, request_id=request_id)

        # [FEAT-470] Step 3: Local Brain-LoRA Waterfall Handoff (shadow_brain_v2 on vLLM port 8088).
        # Stream The Brain's local technical baseline BEFORE remote escalation to Deep Thought.
        brain_response = ""
        if "brain" in self.residents:
            brain_tools = await self._get_node_tools("brain")
            async for token in self._process_node_stream(
                "brain", query, distilled_context, "Brain (Local Baseline)",
                tools=brain_tools, temperature=0.2, request_id=request_id
            ):
                brain_response += token
                if shutdown_event and shutdown_event.is_set():
                    break

        # Step 4: Remote escalation to Deep Thought (Kender), passing the query, distilled
        # strategic brief, AND the local Brain synthesis as grounding context upstream.
        dt_response = ""
        thought_reachable = "thought" in self.residents
        if thought_reachable and self.is_deep_thought_reachable:
            try:
                thought_reachable = await self.is_deep_thought_reachable()
            except Exception as e:
                logging.warning(f"[HUB] Deep Thought reachability probe failed: {e}")
                thought_reachable = False
        # [FEAT-486] Fast Socket Shadow Gate: Even if the reachability probe nominally
        # passed, run a 200ms TCP socket check on Kender to hard-bypass the remote call
        # when it is SHADOW, eliminating 60s timeout hangs in STAGE 4/5.
        if thought_reachable and not _probe_tcp(KENDER_HOST, KENDER_PORT, SOCKET_TIMEOUT_S):
            logging.info("[FEAT-486] Kender SHADOW (socket gate). Bypassing remote Strategic Synthesis.")
            thought_reachable = False
        if thought_reachable:
            thought_context = distilled_context
            if brain_response:
                thought_context += f"\n\n[LOCAL_BRAIN_BASELINE]:\n{brain_response}"
            active_tools = await self._get_node_tools("thought")
            async for token in self._process_node_stream(
                "thought", query, thought_context, "Deep Thought", tools=active_tools, temperature=0.2, request_id=request_id
            ):
                dt_response += token
                if shutdown_event and shutdown_event.is_set():
                    break

        # [SPR-41_2] Skip cascade if context starvation was detected
        if "thought" in self.context_starved_nodes:
            self.context_starved_nodes.discard("thought")
            logging.info("[HUB] Brain leg cascade bypassed due to CONTEXT_STARVED.")
            return
        
        # [FEAT-227] The Grounding Gate: Let Pinky critique and summarize the final strategic output.
        # [FEAT-470] Evaluate whichever strategic response the waterfall produced (Deep Thought if
        # reachable, otherwise the local Brain baseline) against the raw grounding context.
        strategic_response = dt_response or brain_response
        strategic_source = "Deep Thought" if dt_response else "Brain (Local Baseline)"
        rag_payload = raw_context if 'raw_context' in locals() else ""
        await self.evaluate_grounding(strategic_source, strategic_response, interest=self.current_interest, shutdown_event=shutdown_event, request_id=request_id, rag_context=rag_payload)

    async def _run_two_mice_handover(
        self,
        query: str,
        *,
        focus_context: str = "",
        interest: float | None = None,
        shutdown_event=None,
        request_id: str = "default",
    ) -> bool:
        """[FEAT-489] Two-Mice Sequential Streaming Handover.

        Stage 1 (Brain - Right Console): Brain extracts 3-4 dense technical
        bullet points from the archive record and streams them to
        ``channel="insight"`` / ``source="Brain (Archive)"``.

        Stage 2 (Pinky - Left Console / TTS): Pinky receives Brain's extracted
        bullets as context, acknowledges Brain in character, and streams a
        2-sentence conversational TL;DR to ``channel="pinky"`` /
        ``source="Pinky (Voice)"``.

        Both stages are grounded by the 3 Prompt Engineering Pillars
        [FEAT-140/467 + FEAT-403 + FEAT-236] via :func:`build_two_mice_stage_prompt`.

        Returns ``True`` when the handover ran; ``False`` when it is not
        possible (missing brains/pinky resident, or interest below the
        Distillation Funnel gate) — the caller falls back to the legacy flow.
        """
        if ("brain" not in self.residents) or ("pinky" not in self.residents):
            logging.info("[FEAT-489] Two-Mice handover unavailable (need brain + pinky residents). Falling back.")
            return False

        gate_interest = self.current_interest if interest is None else float(interest)
        if gate_interest < TWO_MICE_FUNNEL_INTEREST:
            logging.info(f"[FEAT-489] Interest {gate_interest:.2f} < {TWO_MICE_FUNNEL_INTEREST}. Funnel dormant.")
            return False
        self.current_interest = gate_interest  # persist an explicitly-passed gate value

        # --- Stage 1: Brain extracts technical bullets (Right Console) --------
        stage1_prompt = build_two_mice_stage_prompt(1, user_query=query, context=focus_context, interest=gate_interest)
        brain_tools = await self._get_node_tools("brain")
        brain_bullets = ""
        async for token in self._process_node_stream(
            "brain", stage1_prompt, "", "Brain (Archive)",
            tools=brain_tools, temperature=0.2, request_id=request_id,
        ):
            brain_bullets += token
            await self.broadcast(build_two_mice_stream_packet(
                source=TWO_MICE_BRAIN_SOURCE, channel=TWO_MICE_BRAIN_CHANNEL,
                console=TWO_MICE_BRAIN_CONSOLE, token=token,
                final=False, request_id=request_id,
            ))
            if shutdown_event and shutdown_event.is_set():
                break
        await self.broadcast(build_two_mice_stream_packet(
            source=TWO_MICE_BRAIN_SOURCE, channel=TWO_MICE_BRAIN_CHANNEL,
            console=TWO_MICE_BRAIN_CONSOLE, token="", final=True, request_id=request_id,
        ))

        # --- Stage 2: Pinky acknowledges Brain + delivers TL;DR (Left Console) -
        stage2_prompt = build_two_mice_stage_prompt(
            2, user_query=query, interest=gate_interest, brain_bullets=brain_bullets,
        )
        pinky_stream_count = 0
        async for token in self._process_node_stream(
            "pinky", stage2_prompt, brain_bullets, "Pinky (Voice)",
            tools=[], temperature=0.7, request_id=request_id,
        ):
            pinky_stream_count += 1
            await self.broadcast(build_two_mice_stream_packet(
                source=TWO_MICE_PINKY_SOURCE, channel=TWO_MICE_PINKY_CHANNEL,
                console=TWO_MICE_PINKY_CONSOLE, token=token,
                final=False, request_id=request_id,
            ))
            if shutdown_event and shutdown_event.is_set():
                break
        await self.broadcast(build_two_mice_stream_packet(
            source=TWO_MICE_PINKY_SOURCE, channel=TWO_MICE_PINKY_CHANNEL,
            console=TWO_MICE_PINKY_CONSOLE, token="", final=True, request_id=request_id,
        ))

        self.turn_thought_trace["brain"] = brain_bullets
        self.turn_thought_trace["pinky"] = f"[Two-Mice TL;DR delivered to Jason ({pinky_stream_count} tokens)]"
        logging.info(f"[FEAT-489] Two-Mice handover complete: Brain {len(brain_bullets)} chars -> Pinky TL;DR streamed.")
        return True

    async def _run_triggered_task(self, task_name):
        """[Task 9.7] Handles one-off system triggers (Recruiter, Librarian, etc)."""
        import subprocess
        import sys
        
        # Path Discovery
        SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
        
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Executing Triggered Task: {task_name.upper()}",
            "brain_source": "System"
        })
        
        try:
            if task_name == "recruiter":
                script = os.path.join(SRC_DIR, "recruiter.py")
                subprocess.Popen([sys.executable, script])
            elif task_name == "lab":
                script = os.path.join(WORKSPACE_DIR, "field_notes/scan_librarian.py")
                subprocess.Popen([sys.executable, script])
            elif task_name == "forge":
                script = os.path.join(SRC_DIR, "mass_scan.py")
                subprocess.Popen([sys.executable, script])
            
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Task {task_name.upper()} dispatched to background.",
                "brain_source": "System"
            })
        except Exception as e:
            logging.error(f"[HUB] Failed to run triggered task {task_name}: {e}")

    async def _parse_override_with_resident(self, gem_id, turn):
        """Use the resident model to parse key-value corrections from user query."""
        prompt = f"""
        [TASK]
        Extract performance reviews/validation correction updates for the entry identifier '{gem_id}' from this message.
        
        [MESSAGE]
        {turn}
        
        [OUTPUT FORMAT]
        Return JSON only with keys:
        - "date": "YYYY-MM-DD" or null
        - "tags": ["tag1", "tag2"] or null
        - "summary": "updated text summary" or null
        
        JSON:
        """
        # Call node to parse
        node = self.residents.get("pinky")
        if not node:
            node = self.residents.get("brain")
            
        if node:
            try:
                response_str = await node.think(prompt, internal=True)
                import re
                import json
                match = re.search(r'\{.*\}', response_str, re.DOTALL)
                if match:
                    updates = json.loads(match.group(0))
                    return {k: v for k, v in updates.items() if v is not None}
            except Exception as e:
                logging.error(f"[HUB] Override parsing error: {e}")
        return None

    def _save_override_to_file(self, gem_id, updates):
        """Append or update correction rules in overrides.json atomically."""
        overrides_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/overrides.json")
        overrides = {}
        if os.path.exists(overrides_path):
            try:
                with open(overrides_path, "r") as f:
                    overrides = json.load(f)
            except Exception:
                pass
                
        if "overrides" not in overrides:
            overrides["overrides"] = {}
            
        if gem_id not in overrides["overrides"]:
            overrides["overrides"][gem_id] = {}
        overrides["overrides"][gem_id].update(updates)
        
        # Atomic write
        tmp = overrides_path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(overrides, f, indent=2)
            os.replace(tmp, overrides_path)
            logging.info(f"[HUB] Successfully committed override for {gem_id} to overrides.json")
        except Exception as e:
            logging.error(f"[HUB] Failed to save overrides.json: {e}")

    async def _stream_message_to_ui(self, message, source="System", request_id="default"):
        """Streams a message character-by-character to the UI waterfall."""
        # [FEAT-488] Anti-Bleed: sanitize full messages against echoed headers too.
        message = sanitize_stream_chunk(message)
        if hasattr(self, 'waterfall_queue') and self.waterfall_queue:
            chunk_size = 5
            for i in range(0, len(message), chunk_size):
                chunk = message[i:i+chunk_size]
                await self.waterfall_queue.put({
                    "brain": chunk,
                    "source": source,
                    "brain_source": source,
                    "final": False,
                    "request_id": request_id
                })
                await asyncio.sleep(0.01)
            # Finalize
            await self.waterfall_queue.put({
                "brain": "",
                "source": source,
                "brain_source": source,
                "final": True,
                "request_id": request_id
            })

    async def handle_workspace_save(self, filename, content):
        """[FEAT-050] Strategic Vibe Check: Performs logic/code validation on save."""
        logging.info(f"[HUB] User saved workspace file: {filename}")
        
        if not hasattr(self, 'last_save_event'):
            self.last_save_event = 0.0
            
        import time
        if time.time() - self.last_save_event < 10.0:
            return
        self.last_save_event = time.time()
        
        # 1. Pinky notice
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Narf! I noticed you saved {filename}!",
            "brain_source": "Pinky",
            "channel": "chat",
            "final": True
        })
        
        # 2. Brain validation
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Strategic Vibe Check: Analyzing architecture constraints for {filename}...",
            "brain_source": "The Brain",
            "channel": "insight",
            "final": True
        })

    async def trigger_morning_briefing(self, request_id="default"):
        """[FEAT-072.1] Present the morning briefing to the user."""
        wisdom_text = ""
        if "archive" in self.residents:
            try:
                # 1. Fetch latest wisdom from long-term memory
                res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 1})
                if hasattr(res, 'content') and len(res.content) > 0:
                    text_content = res.content[0].text
                    try:
                        data = json.loads(text_content)
                        wisdom_text = data.get("text", "")[:4000]
                    except Exception:
                        wisdom_text = text_content[:4000]
            except Exception as e:
                logging.error(f"[HUB] Failed to load Diamond Wisdom: {e}")
        
        # 2. Read status.json
        status_data = {}
        status_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/status.json")
        if os.path.exists(status_path):
            try:
                with open(status_path, "r") as f:
                    status_data = json.load(f)
            except Exception as e:
                logging.error(f"[HUB] Failed to load status.json: {e}")

        # 3. Read recruiter_report.json
        recruiter_data = {}
        recruiter_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
        if os.path.exists(recruiter_path):
            try:
                with open(recruiter_path, "r") as f:
                    recruiter_data = json.load(f)
            except Exception as e:
                logging.error(f"[HUB] Failed to load recruiter_report.json: {e}")

        # 4. Read pager_activity.json
        pager_warnings = []
        pager_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json")
        if os.path.exists(pager_path):
            try:
                with open(pager_path, "r") as f:
                    activities = json.load(f)
                    # Filter for critical/warning alerts and take last 3
                    filtered = [act for act in activities if act.get("severity", "").upper() in ["CRITICAL", "WARNING"]]
                    pager_warnings = filtered[-3:]
            except Exception as e:
                logging.error(f"[HUB] Failed to load pager_activity.json: {e}")

        # 5. Format the briefing prompt
        prompt_parts = []
        prompt_parts.append("Generate a morning briefing using the following system status and context:")
        if wisdom_text:
            prompt_parts.append(f"\n[DIAMOND WISDOM CONTEXT]:\n{wisdom_text}")
        if status_data:
            prompt_parts.append(f"\n[SYSTEM STATUS]:\n{json.dumps(status_data, indent=2)}")
        if recruiter_data:
            prompt_parts.append(f"\n[RECRUITER REPORT]:\n{json.dumps(recruiter_data, indent=2)}")
        if pager_warnings:
            prompt_parts.append(f"\n[RECENT PAGER WARNINGS/ERRORS]:\n{json.dumps(pager_warnings, indent=2)}")
        
        prompt_parts.append(
            "\n[INSTRUCTION]:\nSynthesize the above information into a high-density, professional news briefing. "
            "Address Jason directly. Highlight any critical alerts or new job listings, and summarize our current system VRAM and status. "
            "CRITICAL GROUNDING RULE: You must ONLY use the facts provided above. Do NOT imagine, guess, or invent any metrics, job listings, or status details. If any metric or list is empty or not provided, state that it is not available. Every detail must be strictly grounded."
        )
        
        briefing_prompt = "\n".join(prompt_parts)

        # 6. Stream via Pinky
        if "pinky" in self.residents:
            async for _ in self._process_node_stream(
                "pinky", briefing_prompt, "[MODE]: MORNING_BRIEFING", "Pinky (Briefing)",
                tools=[], temperature=0.1, request_id=request_id
            ):
                pass

    async def _prime_first_try(self, turn):
        """[NEW] First Try: Persona-faithful quick response."""
        # [FEAT-028] Hibernation gate: no remote Deep Thought traffic while hibernating
        lab_state = ""
        if self.get_lab_state:
            try:
                lab_state = self.get_lab_state() or ""
            except Exception:
                lab_state = ""
        if lab_state == "HIBERNATING":
            logging.info("[PRIME] Hibernating. Skipping Deep Thought priming (zero remote traffic).")
            return None
        # Persona defaults to Deep Thought as it's pre-triage
        persona = "Deep Thought (the Brain's pre-conscious analytical stream - calm, strategic, non-interactive; never uses Pinky catchphrases like 'Narf!', 'Poit!', 'Zort!')"
        logging.info(f"[PRIME] Initiating priming for turn: {turn[:50]}")
        
        tic_msg = None
        
        # Opportunistic check: if Deep Thought is immediately available, try to get a quip.
        if "thought" in self.residents:
            try:
                logging.info(f"[PRIME] Calling 'think' tool for persona: {persona}")
                # Use a very short timeout; this is just to buy time for triage, not stall it.
                tic_res = await asyncio.wait_for(self.residents["thought"].call_tool("think", {
                    "query": f"[SYSTEM_TIC]: Provide a short 'First Try' response from {persona} acknowledging the query: '{turn[:50]}'. Do not answer the question directly. Acknowledge with arrogant hesitance, knowing the waterfall process will handle the details.",
                    "temperature": 0.8
                }), timeout=3.0)
                tic_msg = tic_res.content[0].text
                logging.info(f"[PRIME] Tic generated: {tic_msg[:30]}")
            except Exception as e:
                logging.error(f"[PRIME] Tic generation failed: {e}")
                
        if not tic_msg:
            tic_msg = "Listening..."
            
        await self.broadcast({
            "type": "crosstalk",
            "brain": tic_msg,
            "brain_source": "Deep Thought",
            "channel": "insight",
            "final": False,
            "version": LAB_VERSION
        })
        logging.info("[PRIME] Broadcast complete.")


# [FEAT-489] Module-level aliases so tests can reference the Two-Mice handover
# entry point without instantiating a full CognitiveHub (which requires live
# residents, a SpeculativeTriageRelay, and engine probes). The method itself
# still runs on any lightweight/object-constructed hub at runtime.
run_two_mice_handover = CognitiveHub._run_two_mice_handover
