import time
import requests
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

# ==========================================
# Configuration
# ==========================================
INPUT_FILE  = "movies_graph.ttl"
OUTPUT_FILE = "movies_graph_expanded.ttl"

MV = Namespace("http://example.org/movies#")
WD = Namespace("http://www.wikidata.org/entity/")
WDT= Namespace("http://www.wikidata.org/prop/direct/")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "KBProjectStudent/1.0 (university project)"}

# ==========================================
# Charger le graphe existant
# ==========================================
print("Chargement du graphe existant...")
g = Graph()
g.parse(INPUT_FILE, format="turtle")
g.bind("mv",  MV)
g.bind("wd",  WD)
g.bind("wdt", WDT)
g.bind("owl", OWL)
print(f"  {len(g)} triplets chargés")

# ==========================================
# ÉTAPE 5A — Alignement Wikidata
# Cherche chaque film/réalisateur sur Wikidata
# et ajoute owl:sameAs
# ==========================================
print("\n=== ÉTAPE 5A : Alignement Wikidata ===")

def search_wikidata(name: str, entity_type: str = "film") -> dict | None:
    """
    Cherche une entité sur Wikidata par son nom.
    Retourne {"uri": ..., "wd_id": ..., "confidence": ...} ou None.
    """
    if entity_type == "film":
        query = f"""
        SELECT ?item ?itemLabel WHERE {{
          ?item wdt:P31 wd:Q11424 .
          ?item rdfs:label "{name}"@en .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }} LIMIT 1
        """
    else:  # person
        query = f"""
        SELECT ?item ?itemLabel WHERE {{
          ?item wdt:P31 wd:Q5 .
          ?item rdfs:label "{name}"@en .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }} LIMIT 1
        """
    try:
        r = requests.get(WIKIDATA_SPARQL,
                         params={"query": query, "format": "json"},
                         headers=HEADERS, timeout=15)
        results = r.json().get("results", {}).get("bindings", [])
        if results:
            uri = results[0]["item"]["value"]
            wd_id = uri.split("/")[-1]
            return {"uri": uri, "wd_id": wd_id, "confidence": 0.95}
    except Exception as e:
        pass
    return None

# Aligner les films
movies = list(g.subjects(RDF.type, MV.Movie))
print(f"  {len(movies)} films à aligner...")
aligned_movies = {}
for i, movie_uri in enumerate(movies[:200]):  # limite à 200 pour ne pas surcharger
    title = g.value(movie_uri, MV.hasTitle)
    if not title:
        continue
    result = search_wikidata(str(title), "film")
    if result:
        wd_uri = URIRef(result["uri"])
        g.add((movie_uri, OWL.sameAs, wd_uri))
        g.add((movie_uri, MV.wikidataId, Literal(result["wd_id"])))
        aligned_movies[str(movie_uri)] = result["wd_id"]
    if i % 20 == 0:
        print(f"    Films alignés : {len(aligned_movies)}/{i+1}", end="\r")
    time.sleep(0.5)

print(f"\n  Films alignés : {len(aligned_movies)}")

# Aligner les réalisateurs
directors = list(g.subjects(RDF.type, MV.Director))
print(f"  {len(directors)} réalisateurs à aligner...")
aligned_directors = {}
for i, dir_uri in enumerate(directors[:300]):
    name = g.value(dir_uri, MV.hasName)
    if not name:
        continue
    result = search_wikidata(str(name), "person")
    if result:
        wd_uri = URIRef(result["uri"])
        g.add((dir_uri, OWL.sameAs, wd_uri))
        g.add((dir_uri, MV.wikidataId, Literal(result["wd_id"])))
        aligned_directors[str(dir_uri)] = result["wd_id"]
    if i % 20 == 0:
        print(f"    Réalisateurs alignés : {len(aligned_directors)}/{i+1}", end="\r")
    time.sleep(0.5)

print(f"\n  Réalisateurs alignés : {len(aligned_directors)}")
print(f"  Triplets après alignement : {len(g)}")

# ==========================================
# ÉTAPE 5B — Expansion SPARQL depuis Wikidata
# ==========================================
print("\n=== ÉTAPE 5B : Expansion SPARQL ===")

def sparql_wikidata(query: str) -> list:
    """Lance une requête SPARQL sur Wikidata."""
    try:
        r = requests.get(WIKIDATA_SPARQL,
                         params={"query": query, "format": "json"},
                         headers=HEADERS, timeout=30)
        return r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"    Erreur SPARQL: {e}")
        return []

# --- Expansion 1 : infos supplémentaires sur les films alignés ---
print("  Expansion 1 : infos films depuis Wikidata...")
wd_ids_movies = list(aligned_movies.values())[:100]

for wd_id in wd_ids_movies:
    query = f"""
    SELECT ?prop ?propLabel ?value ?valueLabel WHERE {{
      wd:{wd_id} ?prop ?value .
      FILTER(?prop IN (
        wdt:P57,   # director
        wdt:P58,   # screenwriter
        wdt:P161,  # cast member
        wdt:P136,  # genre
        wdt:P495,  # country of origin
        wdt:P577,  # publication date
        wdt:P2047, # duration
        wdt:P166,  # award received
        wdt:P272,  # production company
        wdt:P364,  # original language
        wdt:P18,   # image
        wdt:P856   # official website
      ))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    results = sparql_wikidata(query)
    for row in results:
        prop  = row.get("prop",  {}).get("value", "")
        value = row.get("value", {}).get("value", "")
        value_label = row.get("valueLabel", {}).get("value", "")
        prop_label  = row.get("propLabel",  {}).get("value", "")
        if prop and value:
            prop_uri  = URIRef(prop)
            value_uri = URIRef(value) if value.startswith("http") else Literal(value)
            movie_uri = URIRef(f"http://www.wikidata.org/entity/{wd_id}")
            g.add((movie_uri, prop_uri, value_uri))
            if value_label and value.startswith("http"):
                g.add((value_uri, RDFS.label, Literal(value_label, lang="en")))
    time.sleep(0.3)

print(f"    Triplets : {len(g)}")

# --- Expansion 2 : infos sur les réalisateurs alignés ---
print("  Expansion 2 : infos réalisateurs depuis Wikidata...")
wd_ids_dirs = list(aligned_directors.values())[:150]

for wd_id in wd_ids_dirs:
    query = f"""
    SELECT ?prop ?value ?valueLabel WHERE {{
      wd:{wd_id} ?prop ?value .
      FILTER(?prop IN (
        wdt:P569,  # date de naissance
        wdt:P570,  # date de décès
        wdt:P27,   # nationalité
        wdt:P21,   # genre
        wdt:P108,  # employeur
        wdt:P166,  # récompenses
        wdt:P19,   # lieu de naissance
        wdt:P800,  # œuvre notable
        wdt:P184,  # directeur de thèse
        wdt:P1412  # langue utilisée
      ))
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    results = sparql_wikidata(query)
    for row in results:
        prop  = row.get("prop",  {}).get("value", "")
        value = row.get("value", {}).get("value", "")
        value_label = row.get("valueLabel", {}).get("value", "")
        if prop and value:
            prop_uri  = URIRef(prop)
            value_uri = URIRef(value) if value.startswith("http") else Literal(value)
            dir_uri   = URIRef(f"http://www.wikidata.org/entity/{wd_id}")
            g.add((dir_uri, prop_uri, value_uri))
            if value_label and value.startswith("http"):
                g.add((value_uri, RDFS.label, Literal(value_label, lang="en")))
    time.sleep(0.3)

print(f"    Triplets : {len(g)}")

# --- Expansion 3 : tous les films d'un genre populaire ---
print("  Expansion 3 : films par genre depuis Wikidata...")
genres_to_expand = ["Q188473", "Q157394", "Q130232"]  # action, comédie, drame

for genre_wd in genres_to_expand:
    query = f"""
    SELECT ?film ?filmLabel ?director ?directorLabel ?year WHERE {{
      ?film wdt:P31 wd:Q11424 ;
            wdt:P136 wd:{genre_wd} ;
            wdt:P57  ?director ;
            wdt:P577 ?date .
      BIND(YEAR(?date) AS ?year)
      FILTER(?year >= 2000 && ?year <= 2024)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 500
    """
    results = sparql_wikidata(query)
    for row in results:
        film_uri = URIRef(row["film"]["value"])
        film_label = row.get("filmLabel", {}).get("value", "")
        dir_uri  = URIRef(row["director"]["value"])
        dir_label= row.get("directorLabel", {}).get("value", "")
        year     = row.get("year", {}).get("value", "")

        g.add((film_uri, RDF.type, MV.Movie))
        g.add((film_uri, WDT.P136, URIRef(f"http://www.wikidata.org/entity/{genre_wd}")))
        g.add((film_uri, WDT.P57, dir_uri))
        if film_label:
            g.add((film_uri, RDFS.label, Literal(film_label, lang="en")))
        if dir_label:
            g.add((dir_uri, RDF.type, MV.Director))
            g.add((dir_uri, RDFS.label, Literal(dir_label, lang="en")))
        if year:
            g.add((film_uri, WDT.P577, Literal(int(year), datatype=XSD.integer)))

    print(f"    Genre {genre_wd} : {len(results)} films ajoutés — total {len(g)} triplets")
    time.sleep(1)

# --- Expansion 4 : acteurs célèbres et leur filmographie ---
print("  Expansion 4 : filmographie des acteurs...")
query = """
SELECT ?actor ?actorLabel ?film ?filmLabel ?year WHERE {
  ?actor wdt:P31 wd:Q5 ;
         wdt:P106 wd:Q33999 .
  ?film wdt:P161 ?actor ;
        wdt:P577 ?date .
  BIND(YEAR(?date) AS ?year)
  FILTER(?year >= 1990 && ?year <= 2024)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 3000
"""
results = sparql_wikidata(query)
for row in results:
    actor_uri = URIRef(row["actor"]["value"])
    film_uri  = URIRef(row["film"]["value"])
    actor_label = row.get("actorLabel", {}).get("value", "")
    film_label  = row.get("filmLabel",  {}).get("value", "")
    year        = row.get("year", {}).get("value", "")

    g.add((actor_uri, RDF.type, MV.Actor))
    g.add((film_uri,  RDF.type, MV.Movie))
    g.add((film_uri, WDT.P161, actor_uri))
    if actor_label:
        g.add((actor_uri, RDFS.label, Literal(actor_label, lang="en")))
    if film_label:
        g.add((film_uri, RDFS.label, Literal(film_label, lang="en")))
    if year:
        g.add((film_uri, WDT.P577, Literal(int(year), datatype=XSD.integer)))

print(f"    Acteurs/films ajoutés — total : {len(g)} triplets")
time.sleep(1)

# --- Expansion 5 : récompenses (Oscars, Palme d'or...) ---
print("  Expansion 5 : films primés...")
awards = {
    "Q19020": "Academy Award for Best Picture",
    "Q41417": "Palme d Or",
    "Q1011547": "Golden Globe Best Motion Picture Drama",
}
for award_wd, award_name in awards.items():
    query = f"""
    SELECT ?film ?filmLabel ?year WHERE {{
      ?film wdt:P31 wd:Q11424 ;
            wdt:P166 wd:{award_wd} ;
            wdt:P577 ?date .
      BIND(YEAR(?date) AS ?year)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 200
    """
    results = sparql_wikidata(query)
    award_uri = URIRef(f"http://www.wikidata.org/entity/{award_wd}")
    g.add((award_uri, RDF.type, MV.Award))
    g.add((award_uri, RDFS.label, Literal(award_name, lang="en")))
    for row in results:
        film_uri   = URIRef(row["film"]["value"])
        film_label = row.get("filmLabel", {}).get("value", "")
        year       = row.get("year", {}).get("value", "")
        g.add((film_uri, RDF.type, MV.Movie))
        g.add((film_uri, WDT.P166, award_uri))
        if film_label:
            g.add((film_uri, RDFS.label, Literal(film_label, lang="en")))
        if year:
            g.add((film_uri, WDT.P577, Literal(int(year), datatype=XSD.integer)))
    print(f"    {award_name} : {len(results)} films — total {len(g)} triplets")
    time.sleep(1)

# ==========================================
# Nettoyage : suppression des doublons
# ==========================================
print("\n=== Nettoyage ===")
print(f"  Triplets avant nettoyage : {len(g)}")
# rdflib gère déjà les doublons nativement (Set), pas besoin de déduplication manuelle
print(f"  Triplets après nettoyage : {len(g)}")

# ==========================================
# Sauvegarde
# ==========================================
print(f"\nSauvegarde dans {OUTPUT_FILE}...")
g.serialize(destination=OUTPUT_FILE, format="turtle")
print(f"\n{'='*50}")
print(f"TERMINÉ !")
print(f"  Triplets total   : {len(g)}")
print(f"  Fichier          : {OUTPUT_FILE}")
print(f"{'='*50}")

if len(g) < 50000:
    print("\n⚠️  Moins de 50 000 triplets — relance le script ou augmente les LIMIT dans les requêtes SPARQL")
else:
    print("\n✅ Volume suffisant pour la session 6 !")