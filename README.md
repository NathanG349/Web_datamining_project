# Knowledge Graph Construction · Alignment · Reasoning & KGE · RAG

A full pipeline project for Knowledge Graph construction, alignment with Wikidata, reasoning (SWRL + KGE), and Retrieval-Augmented Generation (RAG) over RDF/SPARQL using a local LLM.

**Domain:** Movies & Directors  
**Data source:** TMDB API + Wikidata SPARQL  
**Final KB size:** ~52,000 triplets · 12,192 entities · 25 relations

---

## Project Structure

```
Web_datamining_project/
├── src/
│   ├── crawl/
│   │   └── session4_build_graph.py       # Session 4: collect data from TMDB API → RDF
│   ├── kg/
│   │   ├── session5_align_expand.py      # Session 5: Wikidata alignment + SPARQL expansion
│   │   └── session5_boost.py             # Session 5: extra expansion to reach 50k triples
│   ├── reason/
│   │   └── session5b_swrl.py             # Session 5b: SWRL reasoning with OWLReady2
│   ├── kge/
│   │   └── session5b_kge.py              # Session 5b: KGE with PyKEEN (TransE + DistMult)
│   └── rag/
│       └── lab_rag_sparql_gen.py         # Session 6: RAG chatbot (NL → SPARQL + self-repair)
├── data/
│   ├── family.owl                        # Family ontology for SWRL reasoning
│   ├── family_reasoned.owl               # Family ontology after inference
│   └── samples/
│       └── movies_graph_sample.ttl       # Sample of the RDF graph (100 triples)
├── kg_artifacts/
│   ├── ontology.ttl                      # Movie ontology (classes + properties)
│   ├── alignment.ttl                     # Wikidata alignment (owl:sameAs)
│   └── expanded.ttl                      # Full expanded KB (~52k triples)
├── kge_output/
│   ├── train.txt                         # 80% split
│   ├── valid.txt                         # 10% split
│   └── test.txt                          # 10% split
├── reports/
│   └── final_report.pdf
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/NathanG349/Web_datamining_project.git
cd Web_datamining_project
```

### 2. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 3. Install and start Ollama
Download Ollama from https://ollama.com then run:
```bash
ollama pull gemma3:4b
ollama run gemma3:4b
```
Leave this terminal open.

---

## How to Run Each Module

### Session 4 — Build the RDF graph from TMDB
```bash
# Add your TMDB API key in the script first
py src/crawl/session4_build_graph.py
# Output: movies_graph.ttl
```

### Session 5 — Wikidata alignment + expansion
```bash
py src/kg/session5_align_expand.py
py src/kg/session5_boost.py
# Output: movies_graph_expanded.ttl (~52k triples)
```

### Session 5b — SWRL reasoning
```bash
py src/reason/session5b_swrl.py
# Requires: family.owl in the same folder
# Output: family_reasoned.owl
```

### Session 5b — Knowledge Graph Embedding
```bash
py src/kge/session5b_kge.py
# Output: kge_output/ (train/valid/test splits, models, tsne_plot.png)
# Warning: takes 20-40 minutes on CPU
```

### Session 6 — RAG Chatbot Demo
Open **two terminals**:

**Terminal 1:**
```bash
ollama run gemma3:4b
```

**Terminal 2:**
```bash
py src/rag/lab_rag_sparql_gen.py
```

Then ask questions like:
- `Which movies were directed by Christopher Nolan?`
- `Which films won the Palme d Or?`
- `Which movies were released after 2015?`

Type `quit` to exit.

---

## Hardware Requirements

| Component | Minimum |
|-----------|---------|
| RAM | 8 GB (16 GB recommended) |
| CPU | Any modern CPU |
| GPU | Not required (CPU mode) |
| Disk | ~2 GB for models + data |
| OS | Windows / Linux / macOS |

---

## Screenshot

![RAG Demo](data/samples/screenshot_demo.png)

---

## Key Results

| Model | MRR | Hits@1 | Hits@3 | Hits@10 |
|-------|-----|--------|--------|---------|
| TransE | 0.0603 | 0.0104 | 0.0770 | 0.1601 |
| DistMult | 0.0333 | 0.0204 | 0.0359 | 0.0568 |

TransE outperforms DistMult on MRR and Hits@3/10. Low scores are expected given the KB size and CPU training constraints.
