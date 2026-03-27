import re
import subprocess
from typing import List, Tuple
from rdflib import Graph
import requests
import json

# ==========================================
# Configuration
# ==========================================
# Remplace par le nom de ton vrai fichier RDF
TTL_FILE = "movies_graph_expanded.ttl" 

OLLAMA_URL = "http://localhost:11434/api/generate"
# Assure-toi que ce nom correspond au modèle que tu as téléchargé sur Ollama
GEMMA_MODEL = "gemma3:4b" 

MAX_PREDICATES = 80
MAX_CLASSES = 40
SAMPLE_TRIPLES = 20

# ==========================================
# 0) Utilitaire : Appeler le LLM local (Ollama)
# ==========================================
def ask_local_llm(prompt: str, model: str = GEMMA_MODEL) -> str:
    """
    Envoie un prompt à un modèle Ollama local via l'API REST.
    Retourne la réponse complète sous forme de chaîne de caractères.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False # Important : désactiver le streaming pour une intégration plus simple
    }
    
    response = requests.post(OLLAMA_URL, json=payload)
    
    if response.status_code != 200:
        raise RuntimeError(f"Erreur de l'API Ollama {response.status_code}: {response.text}")
        
    data = response.json()
    return data.get("response", "")


# ==========================================
# 1) Charger le graphe RDF
# ==========================================
def load_graph(ttl_path: str) -> Graph:
    g = Graph()
    g.parse(ttl_path, format="turtle")
    print(f"Graphe chargé avec {len(g)} triplets depuis {ttl_path}")
    return g

# ==========================================
# 2) Construire un résumé du schéma (Schema Summary)
# ==========================================
def get_prefix_block(g: Graph) -> str:
    """Récupère les préfixes pour aider le LLM."""
    defaults = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "owl": "http://www.w3.org/2002/07/owl#",
    }
    ns_map = {p: str(ns) for p, ns in g.namespace_manager.namespaces()}
    for k, v in defaults.items():
        ns_map.setdefault(k, v)
        
    lines = [f"PREFIX {p}: <{ns}>" for p, ns in ns_map.items()]
    return "\n".join(sorted(lines))

def list_distinct_predicates(g: Graph, limit=MAX_PREDICATES) -> List[str]:
    q = f"SELECT DISTINCT ?p WHERE {{ ?s ?p ?o . }} LIMIT {limit}"
    return [str(row.p) for row in g.query(q)]

def list_distinct_classes(g: Graph, limit=MAX_CLASSES) -> List[str]:
    q = f"SELECT DISTINCT ?cls WHERE {{ ?s a ?cls . }} LIMIT {limit}"
    return [str(row.cls) for row in g.query(q)]

def sample_triples(g: Graph, limit=SAMPLE_TRIPLES) -> List[Tuple[str, str, str]]:
    q = f"SELECT ?s ?p ?o WHERE {{ ?s ?p ?o . }} LIMIT {limit}"
    return [(str(r.s), str(r.p), str(r.o)) for r in g.query(q)]

def build_schema_summary(g: Graph) -> str:
    prefixes = get_prefix_block(g)
    preds = list_distinct_predicates(g)
    clss = list_distinct_classes(g)
    samples = sample_triples(g)
    
    pred_lines = "\n".join(f"- {p}" for p in preds)
    cls_lines = "\n".join(f"- {c}" for c in clss)
    sample_lines = "\n".join(f"- {s} {p} {o}" for s, p, o in samples)
    
    summary = f"""
{prefixes}

# Predicates (sampled, unique up to {MAX_PREDICATES})
{pred_lines}

# Classes / rdf:type (sampled, unique up to {MAX_CLASSES})
{cls_lines}

# Sample triples (up to {SAMPLE_TRIPLES})
{sample_lines}
"""
    return summary.strip()



SPARQL_INSTRUCTIONS = """
You are a SPARQL generator. Convert the user QUESTION into a valid SPARQL 1.1 SELECT query
for the given RDF graph schema. Follow strictly:
- Use ONLY the IRIs/prefixes visible in the SCHEMA SUMMARY.
- Prefer readable SELECT projections with variable names.
- Do NOT invent new predicates/classes.
- Return ONLY the SPARQL query in a single fenced code block labeled ```sparql
- No explanations or extra text outside the code block.
"""

def make_sparql_prompt(schema_summary: str, question: str) -> str:
    return f"""{SPARQL_INSTRUCTIONS}
SCHEMA SUMMARY:
{schema_summary}

QUESTION:
{question}

Return only the SPARQL query in a code block.
"""

CODE_BLOCK_RE = re.compile(r"```(?:sparql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)

def extract_sparql_from_text(text: str) -> str:
    """Extract the first code block content; fallback to whole text."""
    m = CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()

def generate_sparql(question: str, schema_summary: str) -> str:
    raw = ask_local_llm(make_sparql_prompt(schema_summary, question))
    query = extract_sparql_from_text(raw)
    return query



REPAIR_INSTRUCTIONS = """
The previous SPARQL failed. Using the SCHEMA SUMMARY and the ERROR MESSAGE,
return a corrected SPARQL 1.1 SELECT query. Use only known prefixes/IRIs.
Return only a single code block with the corrected SPARQL.
"""

def repair_sparql(schema_summary, question, bad_query, error_msg):
    prompt = f"""{REPAIR_INSTRUCTIONS}
SCHEMA SUMMARY: {schema_summary}
ORIGINAL QUESTION: {question}
BAD SPARQL: {bad_query}
ERROR MESSAGE: {error_msg}
Return only the corrected SPARQL in a code block.
"""
    raw = ask_local_llm(prompt)
    return extract_sparql_from_text(raw)



def answer_with_sparql_generation(g, schema_summary, question, try_repair=True):
    sparql = generate_sparql(question, schema_summary)
    try:
        vars_, rows = run_sparql(g, sparql)
        return {"query": sparql, "vars": vars_, "rows": rows, "repaired": False, "error": None}
    except Exception as e:
        if try_repair:
            repaired = repair_sparql(schema_summary, question, sparql, str(e))
            try:
                vars_, rows = run_sparql(g, repaired)
                return {"query": repaired, "vars": vars_, "rows": rows, "repaired": True, "error": None}
            except Exception as e2:
                return {"query": repaired, "vars": [], "rows": [], "repaired": True, "error": str(e2)}
        return {"query": sparql, "vars": [], "rows": [], "repaired": False, "error": str(e)}
    



def answer_no_rag(question: str) -> str:
    prompt = f"Answer the following question as best as you can:\n\n{question}"
    return ask_local_llm(prompt)



def pretty_print_result(result: dict):
    if result.get("error"):
        print("\n[Execution Error]", result["error"])
    print("\n[SPARQL Query Used]\n", result["query"])
    print("\n[Repaired?]", result["repaired"])
    rows = result.get("rows", [])
    vars_ = result.get("vars", [])
    if not rows:
        print("\n[No rows returned]")
        return
    print("\n[Results]")
    print(" | ".join(vars_))
    for r in rows[:20]:
        print(" | ".join(r))

if __name__ == "__main__":
    g = load_graph(TTL_FILE)
    schema = build_schema_summary(g)
    while True:
        q = input("\nQuestion (or 'quit'): ").strip()
        if q.lower() == "quit":
            break
        print("\n--- Baseline (No RAG) ---")
        print(answer_no_rag(q))
        print("\n--- SPARQL-generation RAG ---")
        result = answer_with_sparql_generation(g, schema, q, try_repair=True)
        pretty_print_result(result)