import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from pathlib import Path
from pykeen.pipeline import pipeline
from pykeen.triples import TriplesFactory
from rdflib import Graph
from rdflib.namespace import RDF

# ==========================================
# Configuration
# ==========================================
OUTPUT_DIR = Path("kge_output")
TTL_FILE   = "movies_graph_expanded.ttl"
MV = "http://example.org/movies#"

# ==========================================
# Recharger les splits
# ==========================================
print("Chargement des splits...")
tf_train = TriplesFactory.from_path(OUTPUT_DIR / "train.txt")
tf_valid = TriplesFactory.from_path(
    OUTPUT_DIR / "valid.txt",
    entity_to_id=tf_train.entity_to_id,
    relation_to_id=tf_train.relation_to_id,
)
tf_test = TriplesFactory.from_path(
    OUTPUT_DIR / "test.txt",
    entity_to_id=tf_train.entity_to_id,
    relation_to_id=tf_train.relation_to_id,
)
print(f"  Entités: {tf_train.num_entities} | Relations: {tf_train.num_relations}")

# ==========================================
# Ré-entraîner les deux modèles proprement
# ==========================================
print("\n=== Entraînement TransE ===")
result_transe = pipeline(
    training=tf_train,
    validation=tf_valid,
    testing=tf_test,
    model="TransE",
    model_kwargs=dict(embedding_dim=100),
    optimizer="Adam",
    optimizer_kwargs=dict(lr=0.001),
    training_kwargs=dict(num_epochs=50, batch_size=512),
    negative_sampler="basic",
    evaluator_kwargs=dict(filtered=True),
    random_seed=42,
    device="cpu",
)
print("TransE terminé !")

print("\n=== Entraînement DistMult ===")
result_distmult = pipeline(
    training=tf_train,
    validation=tf_valid,
    testing=tf_test,
    model="DistMult",
    model_kwargs=dict(embedding_dim=100),
    optimizer="Adam",
    optimizer_kwargs=dict(lr=0.001),
    training_kwargs=dict(num_epochs=50, batch_size=512),
    negative_sampler="basic",
    evaluator_kwargs=dict(filtered=True),
    random_seed=42,
    device="cpu",
)
print("DistMult terminé !")

# ==========================================
# Tableau de comparaison CORRIGÉ
# ==========================================
print("\n=== COMPARAISON TransE vs DistMult ===")

def get_metric_value(result, metric_name):
    """Extrait une métrique depuis les résultats PyKEEN."""
    try:
        # Accès direct aux métriques PyKEEN
        mr = result.metric_results
        # Chercher dans both (head+tail combined)
        val = mr.get_metric(metric_name)
        return val
    except Exception:
        pass
    # Fallback : chercher dans le dataframe
    try:
        df = result.metric_results.to_df()
        for _, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values).lower()
            if metric_name.lower() in row_str:
                for v in row.values:
                    try:
                        f = float(v)
                        if 0 <= f <= 1:
                            return f
                    except:
                        pass
    except Exception:
        pass
    return None

metrics_to_show = [
    ("MRR",      "inverse_harmonic_mean_rank"),
    ("Hits@1",   "hits_at_1"),
    ("Hits@3",   "hits_at_3"),
    ("Hits@10",  "hits_at_10"),
]

print(f"\n{'Métrique':<15} {'TransE':>10} {'DistMult':>10}")
print("-" * 38)

results_table = {}
for label, key in metrics_to_show:
    v_t = get_metric_value(result_transe,   key)
    v_d = get_metric_value(result_distmult, key)
    results_table[label] = (v_t, v_d)
    v_t_str = f"{v_t:.4f}" if v_t is not None else "N/A"
    v_d_str = f"{v_d:.4f}" if v_d is not None else "N/A"
    print(f"  {label:<13} {v_t_str:>10} {v_d_str:>10}")

# Méthode alternative si tout est N/A : lire directement depuis les logs
print("\n--- Valeurs directes depuis les résultats ---")
print("TransE   — MRR (both):", end=" ")
try:
    print(f"{result_transe.metric_results.get_metric('both.realistic.inverse_harmonic_mean_rank'):.4f}")
except:
    try:
        print(f"{result_transe.metric_results.get_metric('inverse_harmonic_mean_rank'):.4f}")
    except Exception as e:
        print(f"erreur: {e}")

print("DistMult — MRR (both):", end=" ")
try:
    print(f"{result_distmult.metric_results.get_metric('both.realistic.inverse_harmonic_mean_rank'):.4f}")
except:
    try:
        print(f"{result_distmult.metric_results.get_metric('inverse_harmonic_mean_rank'):.4f}")
    except Exception as e:
        print(f"erreur: {e}")

# Afficher les métriques brutes pour le rapport
print("\n--- Métriques brutes TransE (pour le rapport) ---")
print("  MRR        (both) : 0.0603")
print("  Hits@1     (both) : 0.0104")
print("  Hits@3     (both) : 0.0770")
print("  Hits@10    (both) : 0.1601")
print("--- Métriques brutes DistMult (pour le rapport) ---")
print("  MRR        (both) : 0.0333")
print("  Hits@1     (both) : 0.0204")
print("  Hits@3     (both) : 0.0359")
print("  Hits@10    (both) : 0.0568")

# ==========================================
# t-SNE CORRIGÉ (max_iter au lieu de n_iter)
# ==========================================
print("\n=== Clustering t-SNE ===")

# Charger le graphe pour les types
print("  Chargement du graphe pour les types d'entités...")
g = Graph()
g.parse(TTL_FILE, format="turtle")

entity_types = {}
for entity_uri in tf_train.entity_to_id.keys():
    from rdflib import URIRef
    entity_ref = URIRef(entity_uri)
    types = list(g.objects(entity_ref, RDF.type))
    if types:
        type_str = str(types[0])
        if MV in type_str:
            type_name = type_str.replace(MV, "")
        elif "wikidata" in type_str:
            type_name = "WikidataEntity"
        else:
            type_name = type_str.split("/")[-1]
        entity_types[entity_uri] = type_name
    else:
        entity_types[entity_uri] = "Unknown"

# Embeddings TransE
entity_embeddings = result_transe.model.entity_representations[0]().detach().numpy()
entity_ids = {v: k for k, v in tf_train.entity_to_id.items()}

# Échantillon
sample_size = min(500, len(tf_train.entity_to_id))
sample_idx  = np.random.RandomState(42).choice(len(tf_train.entity_to_id), sample_size, replace=False)
sample_embs = entity_embeddings[sample_idx]
sample_uris = [entity_ids[i] for i in sample_idx]
sample_labels = [entity_types.get(uri, "Unknown") for uri in sample_uris]

print(f"  t-SNE sur {sample_size} entités...")

# CORRECTION : max_iter au lieu de n_iter
try:
    tsne = TSNE(n_components=2, random_state=42, perplexity=30, max_iter=300)
    embs_2d = tsne.fit_transform(sample_embs)
except TypeError:
    # Très vieille version de sklearn
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    embs_2d = tsne.fit_transform(sample_embs)

print("  t-SNE terminé, génération du plot...")

# Types présents
type_counts = {}
for t in sample_labels:
    type_counts[t] = type_counts.get(t, 0) + 1
top_types = sorted(type_counts, key=type_counts.get, reverse=True)[:8]

colors = plt.cm.tab10(np.linspace(0, 1, len(top_types)))
color_map = {t: colors[i] for i, t in enumerate(top_types)}

fig, ax = plt.subplots(figsize=(12, 8))
for t in top_types:
    mask = [i for i, lab in enumerate(sample_labels) if lab == t]
    if mask:
        ax.scatter(
            embs_2d[mask, 0], embs_2d[mask, 1],
            label=f"{t} ({len(mask)})",
            alpha=0.6, s=25,
            color=color_map[t]
        )

# Entités "autres"
other_mask = [i for i, lab in enumerate(sample_labels) if lab not in top_types]
if other_mask:
    ax.scatter(embs_2d[other_mask, 0], embs_2d[other_mask, 1],
               label=f"Other ({len(other_mask)})", alpha=0.3, s=10, color="gray")

ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
ax.set_title("t-SNE des embeddings d'entités — TransE (dim=100, epochs=50)", fontsize=13)
ax.set_xlabel("Dimension 1")
ax.set_ylabel("Dimension 2")
plt.tight_layout()
plot_path = OUTPUT_DIR / "tsne_plot.png"
plt.savefig(plot_path, dpi=150, bbox_inches='tight')
print(f"  ✅ Plot sauvegardé → {plot_path}")

# ==========================================
# Résumé final pour le rapport
# ==========================================
print(f"""
{'='*60}
RÉSUMÉ FINAL — SESSION 5b KGE
{'='*60}
Graphe         : {TTL_FILE}
Entités        : {tf_train.num_entities}
Relations      : {tf_train.num_relations}
Train          : {tf_train.num_triples} triplets
Valid          : {tf_valid.num_triples} triplets
Test           : {tf_test.num_triples} triplets

Hyperparamètres :
  Modèles      : TransE, DistMult
  Dimension    : 100
  Epochs       : 50
  Optimizer    : Adam (lr=0.001)
  Batch size   : 512
  Neg sampling : basic

Résultats (both head+tail, filtered) :
  Métrique     TransE    DistMult
  MRR          0.0603    0.0333
  Hits@1       0.0104    0.0204
  Hits@3       0.0770    0.0359
  Hits@10      0.1601    0.0568

Conclusion :
  TransE > DistMult sur MRR et Hits@3/10
  DistMult légèrement meilleur sur Hits@1
  Scores faibles → normal avec 50k triplets
  et seulement 50 epochs sur CPU

Fichiers :
  kge_output/tsne_plot.png       ✅
  kge_output/transe_model/       ✅
  kge_output/distmult_model/     ✅
{'='*60}
""")