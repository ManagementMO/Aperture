# AUCCTUS_APERTURE_PROTOTYPE_STUDIO.md

# Aperture Prototype Studio  
## Enterprise Idea → Brand-Aware Interactive 3D Prototype Agent

---

## 1. One-Sentence Summary

**Aperture Prototype Studio** is an AI agent built on top of Aperture that turns a Fortune 500 innovation manager’s new product idea, company context, and supporting documents into a research-backed concept brief, visual design direction, and interactive 3D prototype that stakeholders can see, rotate, inspect, and iterate on.

---

## 2. Why This Fits the Aucctus AI Track

The Aucctus challenge asks for:

> An AI system that takes a specific new product idea from an enterprise innovation manager, researches the brand, maps out the idea, sketches the design, and generates an interactive 3D prototype that stakeholders can see and touch.

Aperture Prototype Studio directly matches this.

The user provides:

- Company name
- Product idea
- Supporting documents
  - corporate strategy
  - annual report
  - brand guidelines
  - product portfolio
  - internal innovation brief
  - market research
- Optional constraints
  - target audience
  - budget
  - product category
  - materials
  - sustainability requirements
  - regulatory constraints

The system outputs:

1. Brand and strategy research summary
2. Product concept map
3. Target customer and use-case definition
4. Competitive/market scan
5. Design rationale
6. Sketch/design directions
7. Structured prototype specification
8. Interactive 3D prototype
9. Iteration controls
10. Stakeholder-ready product concept brief
11. Aperture metrics showing token savings and context optimization

---

## 3. Why This Is Perfect on Top of Aperture

Aperture’s core purpose is to reduce token waste and make tool-heavy agents more efficient.

This Aucctus-style agent is an ideal Aperture showcase because the workflow naturally creates huge, noisy context:

- Long corporate strategy documents
- Annual reports
- Brand guidelines
- Market research PDFs
- Competitor websites
- Product pages
- Trend reports
- User feedback
- Design inspiration
- Prototype specifications
- Repeated research calls
- Large multimodal outputs

Without Aperture, the model may be overwhelmed by raw documents, search results, and verbose tool outputs.

With Aperture, the system compresses those into compact, task-useful context packs.

The core thesis:

> Enterprise innovation workflows are context-heavy. Aperture lets the agent absorb much more enterprise context while showing the model only the information needed to create a better prototype.

---

## 4. Project Name Options

Recommended name:

# Aperture Prototype Studio

Other possible names:

- ConceptForge
- Brand-to-Prototype Agent
- Innovation Twin
- VentureSketch
- LaunchLab Agent
- PrototypeOS
- Aucctus Prototype Copilot

Recommended final branding:

> **Aperture Prototype Studio: From enterprise idea to interactive prototype, powered by context compression.**

---

## 5. Example User Scenario

### Input

```text
Company: Red Bull

Product idea:
Caffeinated chewing gum for students, gamers, drivers, and night-shift workers.

Supporting documents:
- Red Bull annual report
- corporate strategy document
- brand guidelines
- product portfolio
- market research on functional gum and energy products

Goal:
Create a stakeholder-ready concept and interactive 3D prototype.
```

### Output

The system generates:

```text
Product concept:
Red Bull Boost Gum

Positioning:
Fast, portable energy without needing to drink a full can.

Target customer:
Students, gamers, drivers, night-shift workers, festival-goers, and athletes who want convenient energy in a small format.

Prototype:
Interactive 3D gum pack with Red Bull-inspired blue/silver/red visual language, flavor variants, caffeine dosage callouts, safety labeling, and stakeholder annotations.
```

---

## 6. High-Level Pipeline

```text
User idea + company + documents
        ↓
Document ingestion and research
        ↓
Aperture compression into brand/context packs
        ↓
Brand strategy and market analysis
        ↓
Product concept mapping
        ↓
Design brief generation
        ↓
Sketch / visual direction generation
        ↓
3D prototype spec generation
        ↓
Interactive 3D prototype rendering
        ↓
Stakeholder brief + iteration UI
        ↓
Aperture metrics and benchmark comparison
```

---

## 7. Core Agent Workflow

## Step 1 — Input Intake

The user fills out a simple form:

```json
{
  "company": "Red Bull",
  "idea": "Caffeinated chewing gum",
  "supporting_documents": [
    "annual_report.pdf",
    "brand_strategy.pdf",
    "product_portfolio.pdf"
  ],
  "target_market": "students, gamers, drivers, night-shift workers",
  "prototype_type": "consumer packaged good",
  "constraints": {
    "must_feel_on_brand": true,
    "must_include_safety_label": true,
    "must_be_pocket_sized": true
  }
}
```

The agent identifies:

- Company
- Product type
- Target user
- Category
- Required research
- Required prototype format
- Missing information

---

## Step 2 — Research and Context Gathering

The agent researches:

- Brand identity
- Visual style
- Corporate strategy
- Existing product portfolio
- Target customer segments
- Market trends
- Competitor products
- Category norms
- Pricing and packaging patterns
- Regulatory or safety considerations
- Strategic fit with the company

Possible sources:

- Uploaded PDFs
- Company website
- Annual reports
- Product pages
- Market articles
- Competitor pages
- Internal strategy docs
- Notes from Notion/Google Drive
- Web search

This stage creates large raw outputs, which is exactly where Aperture helps.

---

## Step 3 — Aperture Context Compression

Aperture compresses raw research and document outputs into focused context packs.

### Raw context may include:

```text
80-page annual report
30-page strategy deck
brand guideline PDF
20 competitor web pages
large product catalog
market trend articles
```

### Aperture turns this into:

```json
{
  "brand_context_pack": {
    "company": "Red Bull",
    "brand_positioning": [
      "energy",
      "performance",
      "youth culture",
      "extreme sports",
      "high-intensity lifestyle"
    ],
    "visual_language": [
      "metallic blue",
      "silver",
      "red/yellow accent",
      "bold contrast",
      "motion/energy cues"
    ],
    "portfolio_fit": "A chewable energy format extends Red Bull beyond beverages while preserving the portable energy ritual.",
    "strategic_risks": [
      "caffeine dosage and labeling",
      "brand dilution if product feels gimmicky",
      "taste and texture expectations",
      "regulatory restrictions by market"
    ],
    "prototype_implications": [
      "should feel premium and energetic",
      "should clearly communicate dosage",
      "should be pocket-sized",
      "should look like a Red Bull product without copying can form too literally"
    ]
  }
}
```

This is the key Aperture layer.

The model does not need every raw paragraph. It needs the compressed insight that supports concept generation and prototyping.

---

## Step 4 — Product Concept Mapping

The agent maps the idea into a structured innovation concept.

Example:

```json
{
  "concept_name": "Red Bull Boost Gum",
  "category": "functional chewing gum",
  "value_proposition": "Portable energy in a chewable format for moments when drinking an energy beverage is inconvenient.",
  "target_customers": [
    "students",
    "gamers",
    "night-shift workers",
    "long-distance drivers",
    "festival-goers"
  ],
  "usage_moments": [
    "late-night studying",
    "gaming sessions",
    "driving",
    "work shifts",
    "pre-workout boost"
  ],
  "format": "slim pocket gum pack",
  "flavor_variants": [
    "Arctic Mint",
    "Tropical Charge",
    "Berry Rush"
  ],
  "differentiator": "Energy ritual in a portable chewable format.",
  "risks": [
    "caffeine safety",
    "regulatory labeling",
    "taste fatigue",
    "consumer skepticism"
  ]
}
```

---

## Step 5 — Design Direction

The agent produces visual and physical design guidance.

Example:

```json
{
  "design_direction": {
    "form_factor": "slim rectangular gum pack",
    "materials": [
      "matte plastic shell",
      "foil blister insert",
      "paperboard sleeve option"
    ],
    "colors": [
      "metallic blue",
      "silver",
      "red accent",
      "yellow energy mark"
    ],
    "front_panel": {
      "logo_area": "center top",
      "product_name": "BOOST GUM",
      "callouts": [
        "Caffeine",
        "Sugar-free",
        "Portable energy"
      ]
    },
    "back_panel": {
      "required_info": [
        "caffeine per piece",
        "serving limit",
        "ingredients",
        "QR code for safety info"
      ]
    },
    "style": "bold, premium, kinetic, energetic"
  }
}
```

---

## Step 6 — Sketch and Concept Visualization

The system generates one or more design sketches.

Possible outputs:

1. Text-based design board
2. Image prompt for product render
3. Generated product concept image
4. Packaging layout mockup
5. Multiple style variants

Example sketch prompt:

```text
Create a premium consumer packaged goods concept render for a Red Bull-inspired caffeinated chewing gum pack. Slim rectangular pocket pack, metallic blue and silver color palette, red/yellow energy accents, bold BOOST GUM typography, caffeine dosage callout, sugar-free label, sporty high-energy aesthetic, clean studio lighting, front and angled view.
```

---

## Step 7 — 3D Prototype Specification

The agent converts the design into a structured 3D spec.

```json
{
  "prototype_type": "gum_pack",
  "geometry": {
    "shape": "rounded rectangular box",
    "width_mm": 85,
    "height_mm": 55,
    "depth_mm": 12,
    "corner_radius_mm": 6
  },
  "materials": {
    "outer_shell": "matte plastic",
    "label": "slightly glossy printed wrap",
    "inner_blister": "metallic foil"
  },
  "branding": {
    "front_text": "BOOST GUM",
    "subtext": "Portable Energy",
    "callouts": [
      "Caffeine",
      "Sugar-free",
      "12 pieces"
    ],
    "color_palette": [
      "metallic blue",
      "silver",
      "red",
      "yellow"
    ]
  },
  "annotations": [
    {
      "label": "Caffeine dosage",
      "position": "front lower-right",
      "description": "Clearly communicates caffeine amount per piece."
    },
    {
      "label": "Pocket-sized pack",
      "position": "side",
      "description": "Designed for students, commuters, gamers, and night-shift workers."
    },
    {
      "label": "Flavor stripe",
      "position": "top edge",
      "description": "Color-coded by flavor variant."
    }
  ]
}
```

---

## Step 8 — Interactive 3D Prototype

The prototype should be built in a reliable way for the demo.

Recommended approach:

### Use deterministic 3D rendering first

Build with:

- React
- Three.js
- React Three Fiber
- Drei
- simple geometry
- procedural materials
- labels/annotations
- orbit controls
- variant toggles

Why this is better than relying only on text-to-3D:

- More reliable for demos
- Easy to control
- Easy to brand
- Easy to annotate
- Easy to iterate
- Easier to guarantee working output during judging

Optional enhancement:

- Use image generation for texture concepts
- Use text-to-3D APIs for additional generated assets
- Export to `.glb` or `.obj` if possible

---

## 9. Demo UI Concept

The demo should look like a polished innovation command center.

```text
┌───────────────────────────────────────────────────────────┐
│ Aperture Prototype Studio                                 │
│ Enterprise Idea → Interactive 3D Prototype                │
└───────────────────────────────────────────────────────────┘

Input:
Company: Red Bull
Idea: Caffeinated chewing gum

[Upload Docs] [Generate Prototype]

┌──────────────────────────────┬────────────────────────────┐
│ Concept Brief                │ Interactive 3D Prototype    │
│                              │                            │
│ Product: Red Bull Boost Gum  │      [Rotating 3D Pack]     │
│ Audience: students/gamers    │                            │
│ Positioning: portable energy │   clickable annotations     │
│ Risks: caffeine labeling     │   flavor variant toggles    │
└──────────────────────────────┴────────────────────────────┘

┌──────────────────────────────┬────────────────────────────┐
│ Brand Context Pack           │ Aperture Efficiency Metrics │
│                              │                            │
│ Brand fit                    │ Raw tokens: 96,000          │
│ Market scan                  │ Compressed: 18,400          │
│ Design rationale             │ Saved: 76,600               │
│ Prototype implications       │ Compression: 81%            │
└──────────────────────────────┴────────────────────────────┘
```

---

## 10. Visual Features

The 3D prototype should include:

- Orbit/rotate controls
- Zoom
- Clickable annotations
- Material variants
- Flavor variants
- Color palette switcher
- Packaging copy editor
- Side-by-side concept alternatives
- Exportable design spec
- Raw vs compressed context inspector

Example annotation labels:

- “Caffeine dosage label”
- “Pocket-sized format”
- “Flavor indicator stripe”
- “QR code for safety info”
- “Brand color system”
- “Premium matte finish”

---

## 11. Aperture Metrics Panel

The UI should show why Aperture matters.

Metrics:

```text
Raw document/research tokens: 96,000
Compressed brand context tokens: 18,400
Tokens saved: 76,600
Compression ratio: 81%

Tool output compression:
- Annual report: 42,000 → 8,500
- Strategy doc: 18,000 → 3,200
- Web research: 24,000 → 5,700
- Competitor scan: 12,000 → 3,000

Cache:
- Repeated company research calls avoided: 7
- Cache hits: 12
- API calls avoided: 7

Schema optimization:
- Tool schema tokens reduced where applicable
```

Important: actual numbers should come from the benchmark, not be invented in the final report.

---

## 12. How Aperture Improves This Agent

## 12.1 Token Attribution

Aperture measures:

- raw uploaded document tokens
- raw research output tokens
- raw tool output tokens
- compressed context tokens
- prototype spec tokens
- tokens saved by compression
- repeated-call savings from cache

This lets us show exactly where token cost was reduced.

---

## 12.2 Tool Output Compression

The agent will call tools that return large outputs:

- document parsers
- web search
- company research tools
- file search
- market research tools
- design inspiration tools
- prototype generation tools

Aperture compresses those outputs into structured context packs:

- brand context pack
- market context pack
- competitor context pack
- prototype requirements pack
- risk/compliance pack
- design language pack

This prevents the model from drowning in raw text.

---

## 12.3 Safe Tool-Call Caching

The agent may repeatedly research the same company or market.

Cacheable examples:

- company profile lookup
- product portfolio lookup
- competitor search
- brand guideline extraction
- previously processed annual report summary
- market trend search

Caching avoids repeated tool/API calls and repeated token-heavy outputs.

---

## 12.4 Schema Optimization

This workflow may use many tools:

- file extraction
- web search
- image generation
- 3D rendering
- document search
- note creation
- artifact export

Schema optimization can reduce the cost of tool discovery and schema exposure.

---

## 13. Why This Is Not Just a Simple Prototype Generator

A simple system might do:

```text
idea → image prompt → generic 3D object
```

Aperture Prototype Studio does:

```text
idea + company + enterprise docs
        ↓
brand research
        ↓
strategy extraction
        ↓
market and competitor analysis
        ↓
Aperture context compression
        ↓
product concept map
        ↓
design rationale
        ↓
prototype specification
        ↓
interactive 3D prototype
        ↓
stakeholder-ready innovation brief
```

The difference is that this system is **enterprise-context-aware**.

It does not just make a random prototype. It makes a prototype that is grounded in:

- company strategy
- brand identity
- product portfolio
- market conditions
- customer segments
- risks and constraints

---

## 14. MVP Build

## MVP Goal

Build a working end-to-end prototype for one example:

> Red Bull → caffeinated chewing gum → interactive 3D gum pack

## MVP Inputs

- Company name
- Product idea
- 1–3 uploaded docs or mock docs
- Optional target audience

## MVP Outputs

- Brand context pack
- Product concept map
- Design brief
- 3D prototype spec
- Interactive 3D pack
- Aperture metrics panel
- Final stakeholder brief

## MVP Tooling

Recommended:

- Frontend: React / Next.js
- 3D: Three.js / React Three Fiber / Drei
- Backend: Python or Node
- LLM: GPT/Claude-compatible
- Documents: PDF/text extraction
- Search: web search tool
- Storage: local/S3-style raw output store
- Aperture: compression/token measurement/cache layer

---

## 15. MVP Agent Architecture

```text
Frontend
  ├── input form
  ├── document uploader
  ├── concept brief panel
  ├── 3D prototype viewer
  └── Aperture metrics panel

Backend
  ├── document ingestion
  ├── research agent
  ├── Aperture compression layer
  ├── concept mapper agent
  ├── design spec agent
  ├── 3D spec generator
  ├── benchmark runner
  └── artifact exporter

Aperture Core
  ├── token measurement
  ├── output compression
  ├── safe caching
  └── schema optimization
```

---

## 16. Agent Roles

This can be implemented as a multi-agent pipeline.

## 16.1 Research Agent

Purpose:

- Collect brand/company/product/market information.

Outputs:

- raw research
- company facts
- product portfolio notes
- competitor scan

Aperture role:

- compress raw research into context packs

---

## 16.2 Brand Strategist Agent

Purpose:

- Interpret brand identity and strategic fit.

Outputs:

- brand context pack
- strategic fit analysis
- risks
- target audience insights

---

## 16.3 Concept Architect Agent

Purpose:

- Convert idea into a coherent product concept.

Outputs:

- value proposition
- use cases
- feature list
- product format
- variants
- differentiation

---

## 16.4 Design Director Agent

Purpose:

- Translate concept into design direction.

Outputs:

- color palette
- form factor
- packaging copy
- material suggestions
- visual style
- sketch prompts

---

## 16.5 Prototype Engineer Agent

Purpose:

- Convert design spec into interactive 3D prototype.

Outputs:

- 3D geometry spec
- materials
- labels
- annotations
- React Three Fiber component
- prototype variants

---

## 16.6 Evaluation Agent

Purpose:

- Score whether the prototype matches the brand, idea, and provided docs.

Outputs:

- brand fit score
- idea fidelity score
- stakeholder clarity score
- missing requirements
- suggested iterations

---

## 17. Benchmark Plan

The benchmark should compare:

```text
Baseline agent without Aperture
vs.
Same agent with Aperture
```

## Benchmark Tasks

Example tasks:

1. Generate product concept from company + idea.
2. Extract brand identity from uploaded docs.
3. Find market competitors.
4. Create design direction.
5. Generate prototype spec.
6. Produce 3D prototype.
7. Revise prototype based on feedback.
8. Explain strategic fit.
9. Identify risks.
10. Create stakeholder brief.

## Metrics

| Metric | Meaning |
|---|---|
| Raw tokens | Tokens from raw docs/research/tool outputs |
| Compressed tokens | Tokens after Aperture compression |
| Tokens saved | Raw minus compressed |
| Compression ratio | Compressed / raw |
| Task success | Did the agent complete the requested task? |
| Brand fit score | Does output match company brand? |
| Idea fidelity | Does prototype reflect the original idea? |
| Prototype usability | Can stakeholder understand and inspect it? |
| Iteration quality | Does feedback produce meaningful changes? |
| Extra tool calls | Did compression force more retrieval? |
| Latency | Time to complete pipeline |
| Cache hits | Repeated reads avoided |

## Target

Initial target:

```text
40%+ token reduction
<5% quality degradation
clear interactive prototype generated
stakeholder-ready concept brief produced
```

Final numbers must be measured, not guessed.

---

## 18. Example Final Stakeholder Brief

```md
# Red Bull Boost Gum

## Concept

Red Bull Boost Gum is a pocket-sized caffeinated chewing gum designed for moments where consumers want energy but do not want a full beverage.

## Target Users

- Students
- Gamers
- Night-shift workers
- Drivers
- Festival-goers
- Athletes

## Brand Fit

The concept extends Red Bull’s energy positioning into a portable, chewable format while preserving the brand’s association with performance, intensity, and active lifestyles.

## Product Format

Slim rectangular gum pack with a metallic blue and silver visual system, bold energy typography, flavor stripe, and caffeine dosage callout.

## Key Features

- Caffeinated gum pieces
- Sugar-free option
- Pocket-sized pack
- Flavor variants
- Clear caffeine labeling
- QR code for safety and usage information

## Risks

- Caffeine dosage and regulatory labeling
- Taste/texture expectations
- Possible brand dilution if product feels novelty-only
- Need to differentiate from existing functional gum products

## Recommended Next Experiments

1. Test consumer interest with concept boards.
2. Validate caffeine dosage and regulatory requirements.
3. Prototype three flavor variants.
4. Run packaging preference test.
5. Conduct quick survey with students/gamers/night-shift workers.
```

---

## 19. Why This Should Impress Aucctus

This project is highly aligned with Aucctus because it supports enterprise innovation managers in moving from:

```text
abstract idea
    ↓
researched concept
    ↓
brand-aligned design
    ↓
interactive prototype
    ↓
stakeholder-ready artifact
```

It also fits the kind of enterprise innovation workflow Aucctus appears to care about:

- idea generation
- validation
- testing
- business strategy
- innovation acceleration
- stakeholder communication
- faster movement from idea to launch

The important differentiator is that this system does not only create a prototype. It creates a prototype grounded in enterprise context.

---

## 20. Why This Should Impress Composio / Aperture Reviewers

This agent also perfectly showcases Aperture.

It uses:

- document tools
- search tools
- file tools
- design tools
- generation tools
- storage tools

It creates exactly the kind of long, messy, repeated outputs that Aperture is designed to optimize.

The demo can show:

```text
Without Aperture:
Huge raw docs and research outputs hit the model.

With Aperture:
Compressed context packs hit the model, raw outputs are preserved by reference, and the prototype quality remains strong.
```

That makes Aperture measurable and visually understandable.

---

## 21. Demo Script

## Step 1 — Input

Presenter enters:

```text
Company: Red Bull
Idea: Caffeinated chewing gum
Docs: annual report, product portfolio, brand strategy notes
Target audience: students, gamers, drivers, night-shift workers
```

## Step 2 — Research

System shows:

```text
Researching brand...
Reading uploaded docs...
Scanning product portfolio...
Searching competitor products...
Compressing context with Aperture...
```

## Step 3 — Concept

System displays:

- product name
- value proposition
- target users
- brand fit
- risks

## Step 4 — Prototype

System renders:

- interactive gum pack
- rotating 3D view
- clickable annotations
- flavor variants

## Step 5 — Aperture Metrics

System shows:

- raw tokens
- compressed tokens
- tokens saved
- cache hits
- API calls avoided
- compression ratio

## Step 6 — Iteration

Presenter says:

```text
Make it more premium and less like a sports supplement.
```

System updates:

- colors
- typography
- packaging copy
- design rationale
- 3D prototype

---

## 22. Strong Demo Features

Add these if time allows:

1. **Before/after context inspector**
   - shows raw research output vs compressed context pack

2. **Prototype variant toggle**
   - Standard Pack
   - Premium Tin
   - Eco Paper Sleeve

3. **Flavor variants**
   - Arctic Mint
   - Tropical Charge
   - Berry Rush

4. **Stakeholder mode**
   - hides technical details
   - shows only concept/prototype/business case

5. **Aperture mode toggle**
   - Composio/base agent
   - Composio + Aperture

6. **Export button**
   - download concept brief
   - export design spec
   - export 3D prototype metadata

---

## 23. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 3D generation is unreliable | Use deterministic React Three Fiber prototype first; use text-to-3D optionally. |
| Brand research is too broad | Compress into structured brand context packs. |
| Prototype feels generic | Ground design in uploaded docs and brand signals. |
| Too much time spent on visuals | Build simple but polished 3D shape with annotations. |
| Aperture value gets hidden | Include visible metrics panel and raw vs compressed inspector. |
| Compression loses important info | Preserve raw references and use benchmark/evaluation agent. |
| Sponsor wants end-to-end pipeline | Show full flow from input to research to design to 3D prototype. |

---

## 24. MVP Implementation Plan

## Day/Phase 1 — Build Aperture Core

- token measurement
- output compression
- raw reference storage
- basic cache
- benchmark metrics

## Day/Phase 2 — Build Product Concept Pipeline

- input form
- document upload
- research summary
- brand context pack
- product concept map

## Day/Phase 3 — Build Design and 3D Prototype

- design spec generator
- React Three Fiber 3D pack
- annotations
- flavor variants
- iteration controls

## Day/Phase 4 — Build Demo Dashboard

- concept brief panel
- 3D prototype panel
- Aperture metrics panel
- raw vs compressed inspector

## Day/Phase 5 — Benchmark and Polish

- run baseline vs Aperture
- record token savings
- fix failure cases
- polish demo script

---

## 25. Final Positioning

The final project should be presented as:

# Aperture Prototype Studio

> An enterprise innovation agent that turns a company-specific product idea and supporting documents into a research-backed, brand-aligned, interactive 3D prototype — powered by Aperture’s token-efficient context compression layer.

This hits both sides:

## For Aucctus

It delivers the challenge:

```text
Idea → research → concept → design → interactive 3D prototype
```

## For Aperture

It showcases the infrastructure:

```text
large docs/tool outputs → compressed context → lower token cost → same/better agent output
```

## Final thesis

Enterprise innovation managers need to move from ideas to tangible prototypes quickly, but enterprise context is too large and messy for naive agents. Aperture Prototype Studio solves this by compressing company research and tool outputs into compact context packs that let the agent generate better prototypes with fewer tokens.

---

## 26. Final Recommendation

This is one of the best possible showcase agents for Aperture because it is:

- sponsor-aligned
- visually impressive
- genuinely useful
- enterprise-focused
- context-heavy
- tool-heavy
- benchmarkable
- easy to explain
- perfect for showing token savings

Recommended final build:

> Build Aperture as the infrastructure layer, then build Aperture Prototype Studio as the polished challenge-facing agent on top of it.
