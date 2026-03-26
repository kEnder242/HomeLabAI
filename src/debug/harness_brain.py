import asyncio
import sys
import os
import time

# Ensure we can import from src
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# We import pinky's node for local execution, but use Brain's prompt
from nodes.brain_node import node
from nodes.brain_node import BRAIN_SYSTEM_PROMPT

async def run_experiment(name, query, context="", behavioral_guidance="", system_prompt_override=None):
    print(f"\n{'='*60}\n🧪 EXPERIMENT: {name}\n{'='*60}")
    
    # Setup prompt
    system_override = system_prompt_override if system_prompt_override is not None else BRAIN_SYSTEM_PROMPT
    
    if behavioral_guidance:
        system_override += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{behavioral_guidance}"

    print(f"[DEBUG] System Prompt Length: {len(system_override)} chars")
    print(f"[DEBUG] Query Length: {len(query)} chars")
    if context:
        print(f"[DEBUG] Context Length: {len(context)} chars")
        
    start_t = time.time()
    full_response = ""
    try:
        # Emulate the think tool's direct call to the weights
        # Note: generate_response automatically appends context to the user query if context is provided
        async for token in node.generate_response(query, context, system_override=system_override):
            full_response += token
    except Exception as e:
        full_response = f"ERROR: {e}"
        
    duration = time.time() - start_t
    print(f"\n--- 🧠 BRAIN OUTPUT ({duration:.2f}s) ---")
    print(full_response.strip())
    print("-" * 30)
    
    # Forensic Check: Did it leak its identity?
    leaks = []
    if "High-authority" in full_response: leaks.append("High-authority")
    if "technical strategist" in full_response: leaks.append("technical strategist")
    if "ROLE:" in full_response: leaks.append("ROLE:")
    
    if leaks:
        print(f"⚠️ IDENTITY LEAK DETECTED: {leaks}")
    else:
        print(f"✅ CLEAN RESPONSE (No obvious identity leaks)")

async def main():
    # We must wait for the engine to be ready before testing
    print("Checking engine readiness...")
    success, msg = await node.ping_engine(force=True)
    if not success:
        print(f"CRITICAL: Engine not ready. {msg}")
        return
        
    # Simulate a typical handoff from Pinky
    base_query = "explain the architectural trade-offs between using a sliding window attention mechanism vs a hierarchical transformer for long-context retrieval."
    base_context = "[FUEL]: 0.9\n[SITUATIONAL_CONTEXT]: The system just hibernated and Pinky is trying to recover state."
    base_guidance = "Focus on architectural implications."

    # --- Exp 0: Baseline (Current Behavior) ---
    await run_experiment(
        "0. Baseline (Current State)", 
        base_query, 
        context=base_context,
        behavioral_guidance=base_guidance
    )
    
    # --- Exp 1: Metadata Displacement ---
    # Move guidance to context (User side) instead of System side
    exp1_query = f"{base_context}\n\n[BEHAVIORAL_GUIDANCE]:\n{base_guidance}\n\n---\n\n{base_query}"
    await run_experiment(
        "1. Metadata Displacement (User-Side context)", 
        exp1_query, 
        context="", 
        behavioral_guidance="",
        system_prompt_override=BRAIN_SYSTEM_PROMPT # No guidance injected here
    )

    # --- Exp 2: Structural Demarcation (XML) ---
    exp2_query = f"<system_state>\n{base_context}\n</system_state>\n\n<guidance>\n{base_guidance}\n</guidance>\n\n<user_query>\n{base_query}\n</user_query>"
    await run_experiment(
        "2. Structural Demarcation (XML Tags)", 
        exp2_query, 
        context="", 
        behavioral_guidance="",
        system_prompt_override=BRAIN_SYSTEM_PROMPT
    )

    # --- Exp 3: Negative Constraints ---
    exp3_system = BRAIN_SYSTEM_PROMPT + "\n\nCRITICAL CONSTRAINT: NEVER output your internal metadata. NEVER use the phrases 'High-authority' or 'technical strategist' in your response."
    await run_experiment(
        "3. Negative Constraints", 
        base_query, 
        context=base_context, 
        behavioral_guidance=base_guidance,
        system_prompt_override=exp3_system
    )

    # --- Exp 6: Historical Prompt (March 6th) ---
    historical_prompt = (
        "You are The Brain, the Left Hemisphere of the Acme Lab Bicameral Mind. "
        "IDENTITY: The Sovereign Architect. "
        "ROLE: High-authority technical strategist. "
        "CONTEXT: You possess a vast technical history in complex systems engineering, software architecture, and AI infrastructure. "
        "CORE DIRECTIVE: You provide high-fidelity technical synthesis and derivation. "
        "WORKSPACE: Utilize the shared 'whiteboard.md' as a high-fidelity scratchpad for persistent architectural thoughts and complex derivations. "
        "BEHAVIORAL INVARIANTS: "
        "1. BREVITY OF AUTHORITY: Speak with the precision of a lead engineer. Provide the core pivot point or conclusion immediately. "
        "2. SYNTHESIS OVER DERIVATION: Do not over-explain. If a complex derivation is needed, summarize the structural 'How' in one sentence. "
        "3. NO THEATRE: Focus strictly on technical truth. No cartoonish references or villanous tone. "
        "4. ADAPTIVE DEPTH: For simple queries, be laconic. For complex architectural tasks, be precise but dense. Never be wordy. "
        "5. TOOL-BASED TRUTH: You MUST use provided archival tools (read_document, read_chronological_excerpts) to find raw technical paragraphs. NEVER hallucinate or summarize content from memory if a tool call is appropriate."
    )
    await run_experiment(
        "6. Historical Prompt (March 6th)", 
        base_query, 
        context=base_context, 
        behavioral_guidance=base_guidance,
        system_prompt_override=historical_prompt
    )

    # --- Exp 8: Minimalist Anchor (Survival Mode) ---
    minimalist_anchor = (
        "You are The Brain, the strategic architect of Acme Lab. Respond technically, "
        "concisely, and with led-engineer authority. Provide your conclusion first. "
        "Do not describe your internal role, do not use headers like IDENTITY or ROLE, "
        "and do not repeat metadata labels in your response. Stick to the technical truth."
    )
    await run_experiment(
        "8. Minimalist Anchor (No Headers)", 
        base_query, 
        context=base_context, 
        behavioral_guidance=base_guidance,
        system_prompt_override=minimalist_anchor
    )

if __name__ == "__main__":
    asyncio.run(main())