# Agent3D: A Neuro-Symbolic Multi-Agent System for Physics-Grounded 3D Scene Generation

**计算机图形学 Project 3** — 基于多智能体协作与几何物理反馈的 Blender 程序化场景生成系统

Agent3D is a multi-agent system that generates physically valid 3D scenes from natural language descriptions using Blender. It combines LLM-driven semantic understanding with deterministic geometric solvers, replacing expensive VLM-based visual critique with exact AABB collision detection.

**Key Innovation**: Instead of using a Vision-Language Model (VLM) as a critic (like LL3M), Agent3D leverages Blender's native geometry APIs (AABB intersection tests) as a closed-loop physics verification mechanism — achieving higher precision at near-zero computational cost.

## System Architecture

The system operates as a closed-loop multi-agent pipeline. A natural language description is iteratively processed through four agents until a physically valid scene is produced:

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Request                             │
│   "a table 1.2m wide with four chairs, two in front"            │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────────────┐  Planner Agent (LLM)                      │
│  │ Scene Semantics  │  • Identifies objects & types             │
│  │  + Spatial Hints │  • Estimates dimensions & materials       │
│  └────────┬─────────┘  • Parses spatial relationships           │
└───────────┼─────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────────────┐  Coder Agent (LLM + Deterministic Solver) │
│  │ JSON Spec + bpy  │  • LLM: object list, materials, hints     │
│  │     Code         │  • **Solver**: overrides coordinates —    │
│  └────────┬─────────┘    4-side greedy placement (no collisions)│
└───────────┼─────────────────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────────────────────────────┐
│            ┌───────────────────────────┐                         │
│  ┌─────┐   │ Environment Verifier      │   ← **Core Innovation** │
│  │bpy  │──→│   (Blender Headless)      │                         │
│  │Code │   │                           │   • AABB collision test │
│  └─────┘   │ • Ground penetration?     │   • Structured text     │
│            │ • Object floating? (>15cm)│     error report        │
│            │ • Proximity violations?   │                         │
│            └────────────┬──────────────┘                         │
│                         │                                        │
│              ┌──────────┴──────────┐                             │
│              ▼                     ▼                             │
│       ⚠ Has Errors           ✅ No Errors                       │
│              │                     │                             │
│    ┌─────────┴─────────┐           │                             │
│    │    Fixer Agent    │           │                             │
│    │  (Iterative Loop) │           │                             │
│    │                   │           │                             │
│    │ Tier 1: Deterministic         │                             │
│    │   Global Relayout (compute_   │                             │
│    │   positions from error report)│                             │
│    │ Tier 2: LLM Re-understanding  │                             │
│    │ Tier 3: Direct Code Patch     │                             │
│    └─────────┬─────────┘           │                             │
│              │ ← ← ← ← ← ← ← ← ←   │ (Re-enter Coder)            │
│              ▼                     ▼                             │
│         ┌─────────────────────────────────────────────────┐      │
│         │         ✅ final_scene.blend (Physics OK)       │      │
│         └─────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-Agent Pipeline**: Planner → Coder → Verifier → Fixer closed-loop system
- **Physics-Grounded Verification**: Exact AABB collision detection via Blender API (0.03m tolerance)
- **Deterministic Spatial Solver**: Greedy 4-side placement algorithm for collision-free layouts
- **Neuro-Symbolic Design**: LLM handles semantics; deterministic math handles coordinates
- **Multi-Language Support**: English and Chinese natural language descriptions
- **36 Object Types**: Chairs, tables, sofas, beds, lamps, TVs, bathroom fixtures, etc.
- **Composite Geometry**: Procedurally assembled objects (chairs from parts, tables with legs, etc.)
- **Orientation Control**: Per-side facing direction parsing with typo-tolerant regex
- **Consumer Hardware**: Runs on CPU-only with a 7B-parameter LLM (no GPU required)

## Requirements

- Python 3.10+
- [Blender](https://www.blender.org/) 5.1+ (for headless scene verification)
- [Ollama](https://ollama.com/) (for local LLM deployment)
- LLM model: `qwen2.5-coder:7b` (or other OpenAI-compatible API)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Ollama with a Code LLM

```bash
ollama run qwen2.5-coder:7b
```

Or use any OpenAI-compatible API by modifying the endpoint in `agents.py`.

### 3. Run Scene Generation

Edit `main.py` to set your desired scene description:

```python
user_request = "a table 1.2m wide 0.8m deep 0.75m tall with four chairs"
```

Then run:

```bash
python main.py
```

### 4. View the Result

Open `outputs/final_scene.blend` in Blender to inspect the generated scene.

## Example Scenes

```bash
# Dining table with chairs
"a table 1.2m wide 0.8m deep 0.75m tall with four chairs"

# Living room
"a sofa with a coffee table and two armchairs"

# Bedroom
"a bed 2m wide 1.6m deep 0.6m tall with two nightstands"

# Bathroom
"a toilet and a bathtub and a sink"

# Chinese input
"一张桌子宽1.2米深0.8米高0.75米 四把椅子 两把在桌子前面 两把在桌子后面"
```

See [USAGE.md](USAGE.md) for detailed documentation of all supported object types, dimension formats, and spatial commands.

## Project Structure

```
Agent3D/
├── main.py                  # Main entry point
├── agents.py                # LLM Agent classes (Planner / Coder / Fixer)
├── spatial_planner.py       # Deterministic spatial solver (4-side placement)
├── code_generator.py        # Deterministic bpy code generator
├── deterministic_fixer.py   # Error parsing and coordinate correction
├── blender_env.py           # Blender headless execution + AABB verification
├── object_types.py          # Object registry (36 types)
├── physics_verifier.py      # Physics verification wrapper
├── prompts.py               # LLM system prompts
├── demo_case.py             # Demo scene runner
├── requirements.txt         # Python dependencies
├── USAGE.md                 # Detailed usage documentation
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## Ablation Study Results

| Condition | Avg. Iterations | Failure Rate |
|-----------|:---:|:---:|
| Full System (Deterministic Fixer) | 1.0 | 0% |
| LLM + Structured Physics Feedback | 1.7 | 0% |
| LLM Fallback Only (No Feedback) | 3.0 | 17% |

The full system resolves all test scenes within 1 correction iteration, while the pure-LLM baseline struggles significantly — confirming that physics-grounded geometric feedback is essential for reliable spatial correction.


## License

This project is developed for educational purposes as part of the Computer Graphics course.
