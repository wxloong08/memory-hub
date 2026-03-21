# Memory Systems & Context Engineering for LLMs: Research Survey

**Date:** 2026-03-18
**Purpose:** Literature review for Memory Hub V2 project — a cross-platform AI conversation memory system
**Scope:** arXiv papers (2024-2026) and industry best practices on LLM memory, context engineering, and conversation continuity

---

## Table of Contents

1. [Survey Papers](#1-survey-papers)
2. [Memory Architectures & Frameworks](#2-memory-architectures--frameworks)
3. [Context Engineering & Compression](#3-context-engineering--compression)
4. [Knowledge Graph-Based Memory](#4-knowledge-graph-based-memory)
5. [Benchmarks & Evaluation](#5-benchmarks--evaluation)
6. [Industry Best Practices](#6-industry-best-practices)
7. [Relevance to Memory Hub V2](#7-relevance-to-memory-hub-v2)
8. [Recommended Technical Roadmap](#8-recommended-technical-roadmap)

---

## 1. Survey Papers

### 1.1 Memory in the Age of AI Agents

- **Authors:** Yuyang Hu, Shichun Liu, Yanwei Yue, et al. (47 researchers)
- **Date:** December 2025 (revised January 2026)
- **arXiv:** [2512.13564](https://arxiv.org/abs/2512.13564)
- **Core idea:** Comprehensive survey proposing a three-lens framework for analyzing agent memory:
  - **Forms:** Token-level, parametric, and latent memory
  - **Functions:** Factual memory (knowledge), experiential memory (past interactions), working memory (active processing)
  - **Dynamics:** How memory is created, modified, and accessed across agent lifecycles
- **Key insight:** Traditional short/long-term memory taxonomies are insufficient. Modern agent memory needs to be understood through form, function, and dynamics simultaneously.
- **Relevance:** Provides the theoretical foundation for classifying our memory types. Our system should support all three functional categories: factual (user preferences, project context), experiential (conversation history), and working (active session state).

### 1.2 From Human Memory to AI Memory: A Survey on Memory Mechanisms in the Era of LLMs

- **Authors:** (Multiple authors, ACM TOIS)
- **Date:** April 2025
- **Link:** [ACM TOIS](https://dl.acm.org/doi/10.1145/3748302)
- **Core idea:** Proposes an eight-quadrant classification framework grounded in three dimensions (object, form, time). Reviews personal memory and system memory perspectives.
- **Relevance:** The personal vs. system memory distinction maps directly to our per-user memory vs. shared project context.

---

## 2. Memory Architectures & Frameworks

### 2.1 MemGPT: Towards LLMs as Operating Systems

- **Authors:** Charles Packer, Sarah Wooders, Kevin Lin, Vivian Fang, Shishir G. Patil, Ion Stoica, Joseph E. Gonzalez
- **Date:** October 2023 (revised February 2024)
- **arXiv:** [2310.08560](https://arxiv.org/abs/2310.08560)
- **Core idea:** Treats LLM context management like OS virtual memory. Implements a two-tier architecture:
  - **Main context (in-context):** Active working memory within the context window
  - **External context (out-of-context):** Archival memory (long-term) + recall memory (conversation history)
  - Uses function calling to self-manage what enters/exits the context window
- **Key technique:** Virtual context management with interrupt mechanisms, inspired by OS memory paging
- **Now:** Evolved into [Letta](https://docs.letta.com/) open-source agent framework
- **Relevance to our project:** **HIGH.** The tiered memory model (main context / archival / recall) directly maps to our needs. When switching between CLI sessions, we need to page relevant memory into the new context window — exactly what MemGPT does.

### 2.2 Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory

- **Authors:** Prateek Chhikara, Dev Khant, Saket Aryan, Taranjeet Singh, Deshraj Yadav
- **Date:** April 2025
- **arXiv:** [2504.19413](https://arxiv.org/abs/2504.19413)
- **Core idea:** Production-oriented memory system with three core operations:
  1. **Dynamic extraction** — Identifies salient information from conversations
  2. **Consolidation** — Organizes extracted info into structured formats
  3. **Retrieval** — Accesses stored information for contextual responses
- **Graph memory variant:** Captures complex relational structures for ~2% additional improvement
- **Results:** 26% improvement over OpenAI's memory on LLM-as-Judge metric; 91% lower p95 latency; 90%+ token cost savings
- **Relevance to our project:** **CRITICAL.** Mem0's extract-consolidate-retrieve pipeline is the most production-proven approach. Their graph memory enhancement aligns with our need to track relationships between conversations, topics, and user preferences across platforms.

### 2.3 Memoria: A Scalable Agentic Memory Framework for Personalized Conversational AI

- **Authors:** Samarth Sarin, Lovepreet Singh, Bhaskarjit Sarmah, Dhagash Mehta
- **Date:** December 2025
- **arXiv:** [2512.12686](https://arxiv.org/abs/2512.12686)
- **Core idea:** Hybrid memory framework combining:
  1. **Dynamic session-level summarization** — Short-term dialogue coherence
  2. **Weighted knowledge graph user modeling** — Long-term user traits, preferences, behavioral patterns
- **Key contribution:** Operates within token constraints while providing persistent, interpretable, context-rich memory
- **Relevance to our project:** **HIGH.** The dual approach (session summaries + knowledge graph) is directly applicable. Session summaries enable quick context restoration when switching CLIs, while KG-based user modeling supports cross-platform preference tracking.

### 2.4 A-MEM: Agentic Memory for LLM Agents (NeurIPS 2025)

- **Authors:** Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang
- **Date:** February 2025 (revised October 2025)
- **arXiv:** [2502.12110](https://arxiv.org/abs/2502.12110)
- **Core idea:** Zettelkasten-inspired memory system that creates interconnected knowledge networks:
  1. **Structured capture:** Generates notes with contextual descriptions, keywords, and tags
  2. **Dynamic linking:** Analyzes historical memories to identify connections
  3. **Memory evolution:** New memories trigger updates to existing memories' context and attributes
- **Key insight:** Memory should not be static storage — it should evolve and self-organize
- **Relevance to our project:** **HIGH.** The Zettelkasten approach (atomic notes + bidirectional links + tags) is an excellent model for organizing cross-platform conversation memories. Each conversation summary becomes a "note" that links to related conversations, topics, and user preferences.

### 2.5 Memory-Augmented Architecture for Long-Term Context Handling

- **Authors:** (Multiple authors)
- **Date:** June 2025
- **arXiv:** [2506.18271](https://arxiv.org/abs/2506.18271)
- **Core idea:** Dynamically retrieves, updates, and prunes relevant information from past interactions for effective long-term context handling.
- **Key technique:** Active memory pruning to prevent context degradation over time
- **Relevance:** The pruning mechanism is essential — our system must handle memory growth gracefully as conversations accumulate.

---

## 3. Context Engineering & Compression

### 3.1 Agentic Context Engineering (ACE) — ICLR 2026

- **Authors:** Qizheng Zhang, Changran Hu, Shubhangi Upasani, et al.
- **Date:** October 2025 (revised January 2026)
- **arXiv:** [2510.04618](https://arxiv.org/abs/2510.04618)
- **Core idea:** Treats contexts as "evolving playbooks" that accumulate, refine, and organize strategies through generation, reflection, and curation. Addresses:
  - **Brevity bias:** Losing domain insights for brevity during summarization
  - **Context collapse:** Details eroding through iterative rewriting
- **Results:** +10.6% on agent tasks, +8.6% on finance benchmarks using smaller open-source models
- **Key insight:** Context should self-improve based on execution feedback, not just be statically composed
- **Relevance to our project:** **HIGH.** When building context for CLI session switching, we should not just dump memory — we should curate and evolve the context based on what has been useful in previous sessions.

### 3.2 ACON: Optimizing Context Compression for Long-Horizon LLM Agents

- **Authors:** Minki Kang, Wei-Ning Chen, Dongge Han, et al.
- **Date:** October 2025
- **arXiv:** [2510.00615](https://arxiv.org/abs/2510.00615)
- **Core idea:** Framework for compressing environment observations and interaction histories:
  1. Uses paired trajectories (successful full-context vs. failed compressed-context) to identify failure points
  2. Iteratively refines compression strategies
  3. Distills optimized compressor into smaller models
- **Results:** 26-54% memory reduction with 95% accuracy preservation
- **Relevance to our project:** **MEDIUM.** The compression techniques are useful for reducing stored conversation size while preserving key information. Particularly relevant for the context injection system when CLI quota is limited.

### 3.3 Recurrent Context Compression (RCC)

- **Authors:** (Multiple authors)
- **Date:** June 2024
- **arXiv:** [2406.06110](https://arxiv.org/abs/2406.06110)
- **Core idea:** Efficiently expands context window within constrained storage. Proposes instruction reconstruction to avoid poor responses when both instructions and context are compressed.
- **Relevance:** The instruction reconstruction technique is important — when injecting compressed memory into a new session, system instructions must remain intact.

---

## 4. Knowledge Graph-Based Memory

### 4.1 PersonalAI: Knowledge Graph Storage and Retrieval for Personalized LLM Agents

- **Authors:** (Multiple authors)
- **Date:** June 2025
- **arXiv:** [2506.17001](https://arxiv.org/abs/2506.17001)
- **Core idea:** Flexible external memory framework based on knowledge graphs. Builds on AriGraph with a hybrid graph design supporting standard edges and two types of hyper-edges for rich semantic and temporal representations.
- **Key contribution:** LLM automatically constructs and updates the memory graph
- **Relevance to our project:** **MEDIUM-HIGH.** Shows how to structure personal memory as a knowledge graph with temporal awareness — directly applicable for tracking user preferences, project states, and conversation relationships across platforms.

### 4.2 AriGraph: Learning Knowledge Graph World Models with Episodic Memory

- **Authors:** (Multiple authors, IJCAI 2025)
- **Date:** July 2024
- **arXiv:** [2407.04363](https://arxiv.org/abs/2407.04363)
- **Core idea:** Constructs and updates a memory graph integrating semantic and episodic memories. The KG combines semantic knowledge with episodic vertices and edges to improve RAG performance.
- **Relevance:** The semantic + episodic distinction is useful for our system — semantic memory (facts, preferences) vs. episodic memory (specific conversation events).

---

## 5. Benchmarks & Evaluation

### 5.1 BEAM: Beyond a Million Tokens — Benchmarking Long-Term Memory in LLMs

- **Authors:** Mohammad Tavakoli, Alireza Salemi, et al.
- **Date:** October 2025 (revised February 2026)
- **arXiv:** [2510.27246](https://arxiv.org/abs/2510.27246)
- **Core idea:** Benchmark with 100 conversations (up to 10M tokens, 2,000 questions). Introduces LIGHT framework with three complementary memory systems inspired by human cognition:
  1. **Long-term episodic memory**
  2. **Short-term working memory**
  3. **Scratchpad** for storing important information
- **Results:** Even million-token context models struggle with lengthy dialogues; LIGHT achieves 3.5-12.69% improvement
- **Key insight:** Raw context length is not enough — structured memory management is essential
- **Relevance to our project:** Validates our approach of structured memory over raw conversation dumping. The three-tier system (episodic + working + scratchpad) is a solid architecture reference.

---

## 6. Industry Best Practices

### 6.1 Context Engineering (Andrej Karpathy's Definition)

Context engineering is "the careful practice of populating the context window with precisely the right information at exactly the right moment." This has emerged as the successor to prompt engineering, focusing on the entire information architecture rather than individual prompts.

### 6.2 Four Core Strategies (Industry Consensus, 2025-2026)

Based on analysis of practices from Anthropic, OpenAI, and leading AI companies:

1. **External Memory / Scratchpads:** AI agents use persistent scratchpads to preserve information across interactions
2. **Context Trimming:** Prune context using importance-based heuristics. A focused 300-token context often outperforms an unfocused 113K-token context
3. **Isolation / Separation of Concerns:** Specialized sub-agents with dedicated context windows (as in OpenAI Swarm)
4. **Model Context Protocol (MCP):** Now governed by the Linux Foundation's Agentic AI Foundation; universal standard for connecting AI agents to tools. Adopted by Anthropic, OpenAI, Google, Microsoft.

### 6.3 Key Principles from Promptingguide.ai

- System prompt design with explicit role and behavioral guidelines
- Structured I/O management with JSON schemas
- Dynamic context integration (real-time information injection)
- RAG for caching and retrieving previous results
- State and historical context management across multi-step workflows
- Clear tool definitions for agent capabilities

### 6.4 2026 Emerging Trends

- **Hierarchical memory architectures:** Short-term, working, and long-term memory layers
- **Context rot awareness:** Performance degrades with poorly curated context growth
- **Self-improving context (ACE approach):** Contexts evolve based on execution feedback
- **MCP as universal connector:** Standardized tool/memory integration across platforms

**Sources:**
- [Context Engineering Guide - PromptingGuide.ai](https://www.promptingguide.ai/guides/context-engineering-guide)
- [Context Engineering: The Definitive 2025 Guide - FlowHunt](https://www.flowhunt.io/blog/context-engineering/)
- [Context Engineering Best Practices - Kubiya](https://www.kubiya.ai/blog/context-engineering-best-practices)
- [Context Engineering Guide - Turing College](https://www.turingcollege.com/blog/context-engineering-guide)
- [GitHub: Context Engineering Resources](https://github.com/mlnjsh/context-engineering)

---

## 7. Relevance to Memory Hub V2

Our project goals mapped to research findings:

| Our Goal | Relevant Research | Key Takeaway |
|----------|------------------|--------------|
| Sync & save complete conversations | Mem0's extract-consolidate-retrieve | Don't store raw conversations — extract salient information and consolidate |
| CLI switching without re-establishing context | MemGPT's virtual context management | Page relevant memory into new context window on demand |
| Memory CRUD | A-MEM's Zettelkasten approach | Atomic, linked, tagged memories with evolution capabilities |
| Cross-platform consistency | Memoria's hybrid approach | Session summaries + knowledge graph for user modeling |
| Context injection efficiency | ACON compression + ACE self-improvement | Compress and curate context, don't dump everything |
| Long-term memory quality | BEAM benchmark insights | Structured memory >> raw context length |

---

## 8. Recommended Technical Roadmap

Based on this survey, the recommended architecture for Memory Hub V2 combines insights from the most relevant papers:

### Tier 1: Memory Storage (from Mem0 + A-MEM)
- **Extract-Consolidate-Retrieve pipeline** (Mem0) for processing raw conversations
- **Zettelkasten-style atomic notes** (A-MEM) with structured attributes: content, keywords, tags, links
- **Graph-based relationships** (Mem0 Graph / Memoria KG) for connecting memories across conversations and platforms

### Tier 2: Context Management (from MemGPT + ACE)
- **Virtual context management** (MemGPT) with tiered memory: working memory / archival memory / recall memory
- **Self-improving context curation** (ACE) that evolves based on which context proved useful
- **Importance-based trimming** (ACON) to fit within context window limits

### Tier 3: Cross-Platform Integration
- **Session-level summarization** (Memoria) for each platform conversation
- **MCP-based tool integration** for standardized memory access across Claude Code, web, API
- **Dynamic context injection** tuned to target platform's context window size

### Tier 4: Quality & Evaluation
- **Multi-dimensional evaluation** (BEAM) covering retrieval accuracy, temporal reasoning, multi-hop inference
- **Memory pruning & contradiction resolution** to prevent context rot
- **Forgetting mechanisms** for outdated or irrelevant information

### Priority Implementation Order:
1. **Conversation extraction pipeline** (Mem0-style) — foundation for everything else
2. **Structured memory storage** (A-MEM Zettelkasten) — atomic, searchable, linkable memories
3. **Context injection engine** (MemGPT-style paging) — enables CLI switching
4. **Knowledge graph layer** (Memoria/PersonalAI) — cross-conversation relationship tracking
5. **Self-improving context curation** (ACE) — optimization over time

---

## Appendix: Paper Index

| # | Paper | arXiv | Date | Relevance |
|---|-------|-------|------|-----------|
| 1 | Memory in the Age of AI Agents | [2512.13564](https://arxiv.org/abs/2512.13564) | Dec 2025 | Survey/Framework |
| 2 | MemGPT: LLMs as Operating Systems | [2310.08560](https://arxiv.org/abs/2310.08560) | Oct 2023 | Core Architecture |
| 3 | Mem0: Production-Ready Long-Term Memory | [2504.19413](https://arxiv.org/abs/2504.19413) | Apr 2025 | Core Architecture |
| 4 | Memoria: Agentic Memory Framework | [2512.12686](https://arxiv.org/abs/2512.12686) | Dec 2025 | Personalization |
| 5 | A-MEM: Agentic Memory (NeurIPS 2025) | [2502.12110](https://arxiv.org/abs/2502.12110) | Feb 2025 | Memory Organization |
| 6 | ACE: Agentic Context Engineering (ICLR 2026) | [2510.04618](https://arxiv.org/abs/2510.04618) | Oct 2025 | Context Optimization |
| 7 | ACON: Context Compression | [2510.00615](https://arxiv.org/abs/2510.00615) | Oct 2025 | Compression |
| 8 | BEAM: Benchmarking Long-Term Memory | [2510.27246](https://arxiv.org/abs/2510.27246) | Oct 2025 | Evaluation |
| 9 | PersonalAI: KG for Personalized Agents | [2506.17001](https://arxiv.org/abs/2506.17001) | Jun 2025 | Knowledge Graph |
| 10 | AriGraph: KG World Models | [2407.04363](https://arxiv.org/abs/2407.04363) | Jul 2024 | Knowledge Graph |
| 11 | Memory-Augmented Architecture | [2506.18271](https://arxiv.org/abs/2506.18271) | Jun 2025 | Architecture |
| 12 | RCC: Recurrent Context Compression | [2406.06110](https://arxiv.org/abs/2406.06110) | Jun 2024 | Compression |
| 13 | From Human Memory to AI Memory (ACM TOIS) | [ACM](https://dl.acm.org/doi/10.1145/3748302) | Apr 2025 | Survey |
