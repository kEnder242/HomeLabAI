# Sprint Plan: SPR-87.0 (The Sovereign DNA Meta-Language & 1:1 Bone Collection Architecture)

**Sprint Anchor:** `SPR-87.0`  
**Status:** DRAFT / PROPOSED  
**Reference ADR:** [`Portfolio_Dev/docs/plans/ADR_008_DNA_LANGUAGE_AND_BONE_COLLECTIONS.md`](file:///home/jallred/Dev_Lab/Portfolio_Dev/docs/plans/ADR_008_DNA_LANGUAGE_AND_BONE_COLLECTIONS.md)  
**Features Implemented:** `FEAT-601`, `FEAT-602`, `FEAT-603`, `FEAT-604`, `FEAT-605`

---

## 🎯 Strategic Objective
Decouple atomic semantic meaning from narrative presentation by establishing **1:1 Source Bone Collection Scratchpads**, a **Self-Contained DNA Macro Citation Grammar**, **Multi-Collection Paper Projections**, a **Sovereign VIBE Ledger**, and an automated **Zero-Loss Round-Trip Invariant Test Matrix**.

---

## 📋 Stories & Execution Phases

### Phase 1: 1:1 Source Bone Collection Scratchpads (`FEAT-601`)
- [ ] **Story 87.1 [SWARM:CLOUD]: 1:1 Source Scratchpad Migration & Indexer**
  - Establish `Portfolio_Dev/field_notes/data/bones/` directory holding 1:1 source scratchpads:
    - `stories_bones.json` (for `stories.html`)
    - `notes_jitc_bones.json` (for JITC raw drafts)
    - `resume_bones.json` (for resume drafts)
  - Ensure scratchpads record ordered bone vertebrae, certified local revisions ($R1 \dots Rn$), and proposed model mutations ($M1 \dots Mn$).
- [ ] **Story 87.2 [SWARM:CLOUD]: Draft Decomposer 1:1 Scratchpad Ingestion**
  - Update `HomeLabAI/src/curator/draft_decomposer.py` so importing/decomposing any document (Markdown, Google Doc, HTML) creates/updates its authoritative 1:1 `*_bones.json` file alongside central DNA cards.

### Phase 2: Self-Contained DNA Macro Grammar & Compiler (`FEAT-602`)
- [ ] **Story 87.3 [SWARM:CLOUD]: DNA Markdown Macro Parser & Serializer**
  - Create `Portfolio_Dev/scripts/dna_macro_compiler.py`.
  - Parse and serialize inline macros: `<!-- [ID:Rn style=type lens=name] -->` with following plain text.
  - Guarantee papers are readable offline in any markdown viewer without requiring ChromaDB.
- [ ] **Story 87.4 [SWARM:CLOUD]: Whitepaper & LaTeX Exporter Refactor**
  - Update `Portfolio_Dev/scripts/build_writer.py` to compile Markdown papers with embedded DNA macros into arXiv-ready LaTeX and HTML.

### Phase 3: Composable Paper Projection & Dynamic Lens Re-Projector (`FEAT-603`)
- [ ] **Story 87.5 [AGY:PRIMARY]: Composable Writer Multi-Source Spine & Dynamic Re-Projector**
  - Update `Portfolio_Dev/field_notes/writer.html` and Foyer REST endpoints (`/paper/*`) to compose papers from multiple bone collection files.
  - Implement dynamic Lens Re-Projection: flip an existing paper between lenses (e.g. Academic $\leftrightarrow$ Executive STAR) while preserving the composite bone spine.

### Phase 4: Bi-Directional Round-Trip Invariant & CI Shakedown (`FEAT-604`)
- [ ] **Story 87.6 [AGY:PRIMARY]: Round-Trip Mathematical Invariant & LLM Grading Test Suite**
  - Author `HomeLabAI/src/tests/test_dna_roundtrip_consistency.py`.
  - Enforce zero-loss invariant: $\Delta(\text{Original Source}, \text{Reconstruct}(\text{Bones}, R_1)) = 0$.
  - Add LLM semantic grading pass verifying consistency between paper text and referenced DNA card revisions.

### Phase 5: Sovereign VIBE Ledger & Taxonomy Ingestion (`FEAT-605`)
- [ ] **Story 87.7 [SWARM:CLOUD]: Initialize `vibe_data.json` & ChromaDB Integration**
  - Create `Portfolio_Dev/dna/vibe_data.json` and ChromaDB `vibe_dna` collection.
  - Ingest inaugural card `[VIBE-001]` ("The Granularity Triad: DNA Ideas, Certified Revisions, and Narrative Spines").
  - Wire `vibe_data.json` into `sync_chroma_dna.py`, `dna_forge_build.py`, and `build_lora_datasets.py`.

---

## 🛡️ Invariant Check & Verification Gate
- Fast unit tests verify AST/macro transformations hermetically.
- Live test asserts exact string identity between decomposed raw sources and $R1$ bone reconstructions.
- Live attending daemon on port 8765 and ChromaDB on port 8001 verified against Git HEAD.
