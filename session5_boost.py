import time
import requests
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

# ==========================================
# Configuration
# ==========================================
INPUT_FILE  = "movies_graph_expanded.ttl"
OUTPUT_FILE = "movies_graph_expanded.ttl"  # on écrase le même fichier

MV  = Namespace("http://example.org/movies#")
WD  = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "KBProjectStudent/1.0 (university project)"}

print("Chargement du graphe existant...")
g = Graph()
g.parse(INPUT_FILE, format="turtle")
g.bind("mv", MV)
g.bind("wd", WD)
g.bind("wdt", WDT)
print(f"  {len(g)} triplets chargés")

def sparql_wikidata(query: str) -> list:
    try:
        r = requests.get(WIKIDATA_SPARQL,
                         params={"query": query, "format": "json"},
                         headers=HEADERS, timeout=30)
        return r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"    Erreur: {e}")
        return []

# --- Boost 1 : plus de films par genre (plus de genres) ---
print("\nBoost 1 : plus de genres...")
genres = {
    "Q188473": "action",
    "Q157394": "comedy",
    "Q130232": "drama",
    "Q200092": "horror",
    "Q24955": "thriller",
    "Q471839": "science fiction",
    "Q52162262": "romance",
    "Q1535153": "animation",
    "Q2484376": "documentary",
}
for genre_wd, genre_name in genres.items():
    query = f"""
    SELECT ?film ?filmLabel ?director ?directorLabel ?year ?country ?countryLabel WHERE {{
      ?film wdt:P31 wd:Q11424 ;
            wdt:P136 wd:{genre_wd} ;
            wdt:P577 ?date .
      OPTIONAL {{ ?film wdt:P57 ?director . }}
      OPTIONAL {{ ?film wdt:P495 ?country . }}
      BIND(YEAR(?date) AS ?year)
      FILTER(?year >= 1980 && ?year <= 2024)
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 800
    """
    results = sparql_wikidata(query)
    genre_uri = URIRef(f"http://www.wikidata.org/entity/{genre_wd}")
    g.add((genre_uri, RDF.type, MV.Genre))
    g.add((genre_uri, RDFS.label, Literal(genre_name, lang="en")))
    for row in results:
        film_uri = URIRef(row["film"]["value"])
        g.add((film_uri, RDF.type, MV.Movie))
        g.add((film_uri, WDT.P136, genre_uri))
        if row.get("filmLabel"):
            g.add((film_uri, RDFS.label, Literal(row["filmLabel"]["value"], lang="en")))
        if row.get("director"):
            dir_uri = URIRef(row["director"]["value"])
            g.add((film_uri, WDT.P57, dir_uri))
            g.add((dir_uri, RDF.type, MV.Director))
            if row.get("directorLabel"):
                g.add((dir_uri, RDFS.label, Literal(row["directorLabel"]["value"], lang="en")))
        if row.get("country"):
            country_uri = URIRef(row["country"]["value"])
            g.add((film_uri, WDT.P495, country_uri))
            if row.get("countryLabel"):
                g.add((country_uri, RDF.type, MV.Country))
                g.add((country_uri, RDFS.label, Literal(row["countryLabel"]["value"], lang="en")))
        if row.get("year"):
            g.add((film_uri, WDT.P577, Literal(int(row["year"]["value"]), datatype=XSD.integer)))
    print(f"  {genre_name} : {len(results)} films — total {len(g)} triplets")
    time.sleep(1)

# --- Boost 2 : réalisateurs célèbres et toute leur filmographie ---
print("\nBoost 2 : filmographies complètes...")
query = """
SELECT ?director ?directorLabel ?film ?filmLabel ?year ?rating WHERE {
  ?director wdt:P31 wd:Q5 ;
            wdt:P106 wd:Q2526255 .
  ?film wdt:P57 ?director ;
        wdt:P577 ?date .
  OPTIONAL { ?film wdt:P444 ?rating . }
  BIND(YEAR(?date) AS ?year)
  FILTER(?year >= 1970 && ?year <= 2024)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 5000
"""
results = sparql_wikidata(query)
for row in results:
    dir_uri  = URIRef(row["director"]["value"])
    film_uri = URIRef(row["film"]["value"])
    g.add((dir_uri,  RDF.type, MV.Director))
    g.add((film_uri, RDF.type, MV.Movie))
    g.add((film_uri, WDT.P57, dir_uri))
    if row.get("directorLabel"):
        g.add((dir_uri, RDFS.label, Literal(row["directorLabel"]["value"], lang="en")))
    if row.get("filmLabel"):
        g.add((film_uri, RDFS.label, Literal(row["filmLabel"]["value"], lang="en")))
    if row.get("year"):
        g.add((film_uri, WDT.P577, Literal(int(row["year"]["value"]), datatype=XSD.integer)))
print(f"  Filmographies — total {len(g)} triplets")
time.sleep(1)

# --- Boost 3 : acteurs avec nationalité, naissance, films ---
print("\nBoost 3 : acteurs détaillés...")
query = """
SELECT ?actor ?actorLabel ?film ?filmLabel ?nationality ?nationalityLabel ?birthYear WHERE {
  ?actor wdt:P31 wd:Q5 ;
         wdt:P106 wd:Q33999 .
  OPTIONAL { ?actor wdt:P27 ?nationality . }
  OPTIONAL { ?actor wdt:P569 ?birth . BIND(YEAR(?birth) AS ?birthYear) }
  ?film wdt:P161 ?actor ;
        wdt:P577 ?date .
  FILTER(YEAR(?date) >= 2000)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 5000
"""
results = sparql_wikidata(query)
for row in results:
    actor_uri = URIRef(row["actor"]["value"])
    film_uri  = URIRef(row["film"]["value"])
    g.add((actor_uri, RDF.type, MV.Actor))
    g.add((film_uri,  RDF.type, MV.Movie))
    g.add((film_uri, WDT.P161, actor_uri))
    if row.get("actorLabel"):
        g.add((actor_uri, RDFS.label, Literal(row["actorLabel"]["value"], lang="en")))
    if row.get("filmLabel"):
        g.add((film_uri, RDFS.label, Literal(row["filmLabel"]["value"], lang="en")))
    if row.get("nationality"):
        nat_uri = URIRef(row["nationality"]["value"])
        g.add((actor_uri, WDT.P27, nat_uri))
        g.add((nat_uri, RDF.type, MV.Country))
        if row.get("nationalityLabel"):
            g.add((nat_uri, RDFS.label, Literal(row["nationalityLabel"]["value"], lang="en")))
    if row.get("birthYear"):
        g.add((actor_uri, WDT.P569, Literal(int(row["birthYear"]["value"]), datatype=XSD.integer)))
print(f"  Acteurs détaillés — total {len(g)} triplets")
time.sleep(1)

# --- Boost 4 : sociétés de production ---
print("\nBoost 4 : sociétés de production...")
query = """
SELECT ?company ?companyLabel ?film ?filmLabel ?country ?countryLabel WHERE {
  ?company wdt:P31 wd:Q18127 .
  ?film wdt:P272 ?company ;
        wdt:P577 ?date .
  OPTIONAL { ?company wdt:P17 ?country . }
  FILTER(YEAR(?date) >= 1990)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 3000
"""
results = sparql_wikidata(query)
for row in results:
    company_uri = URIRef(row["company"]["value"])
    film_uri    = URIRef(row["film"]["value"])
    g.add((company_uri, RDF.type, MV.ProductionCompany))
    g.add((film_uri,    RDF.type, MV.Movie))
    g.add((film_uri, WDT.P272, company_uri))
    if row.get("companyLabel"):
        g.add((company_uri, RDFS.label, Literal(row["companyLabel"]["value"], lang="en")))
    if row.get("filmLabel"):
        g.add((film_uri, RDFS.label, Literal(row["filmLabel"]["value"], lang="en")))
    if row.get("country"):
        country_uri = URIRef(row["country"]["value"])
        g.add((company_uri, WDT.P17, country_uri))
        if row.get("countryLabel"):
            g.add((country_uri, RDF.type, MV.Country))
            g.add((country_uri, RDFS.label, Literal(row["countryLabel"]["value"], lang="en")))
print(f"  Sociétés de prod — total {len(g)} triplets")
time.sleep(1)

# --- Boost 5 : plus de récompenses ---
print("\nBoost 5 : récompenses détaillées...")
awards = {
    "Q19020":   "Academy Award for Best Picture",
    "Q41417":   "Palme d Or",
    "Q1011547": "Golden Globe Best Motion Picture Drama",
    "Q103916":  "BAFTA Award for Best Film",
    "Q212871":  "César Award for Best Film",
    "Q40285":   "Academy Award for Best Director",
    "Q103618":  "Academy Award for Best Actor",
    "Q106278":  "Academy Award for Best Actress",
}
for award_wd, award_name in awards.items():
    query = f"""
    SELECT ?film ?filmLabel ?director ?directorLabel ?year WHERE {{
      ?film wdt:P166 wd:{award_wd} .
      OPTIONAL {{ ?film wdt:P57 ?director . }}
      OPTIONAL {{ ?film wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 300
    """
    results = sparql_wikidata(query)
    award_uri = URIRef(f"http://www.wikidata.org/entity/{award_wd}")
    g.add((award_uri, RDF.type, MV.Award))
    g.add((award_uri, RDFS.label, Literal(award_name, lang="en")))
    for row in results:
        film_uri = URIRef(row["film"]["value"])
        g.add((film_uri, RDF.type, MV.Movie))
        g.add((film_uri, WDT.P166, award_uri))
        if row.get("filmLabel"):
            g.add((film_uri, RDFS.label, Literal(row["filmLabel"]["value"], lang="en")))
        if row.get("director"):
            dir_uri = URIRef(row["director"]["value"])
            g.add((film_uri, WDT.P57, dir_uri))
            g.add((dir_uri, RDF.type, MV.Director))
            if row.get("directorLabel"):
                g.add((dir_uri, RDFS.label, Literal(row["directorLabel"]["value"], lang="en")))
        if row.get("year"):
            g.add((film_uri, WDT.P577, Literal(int(row["year"]["value"]), datatype=XSD.integer)))
    print(f"  {award_name} : {len(results)} films — total {len(g)} triplets")
    time.sleep(0.8)

# ==========================================
# Sauvegarde finale
# ==========================================
print(f"\nSauvegarde dans {OUTPUT_FILE}...")
g.serialize(destination=OUTPUT_FILE, format="turtle")
print(f"\n{'='*50}")
print(f"TERMINÉ !")
print(f"  Triplets total : {len(g)}")
print(f"  Fichier        : {OUTPUT_FILE}")
print(f"{'='*50}")

if len(g) < 50000:
    print(f"\n⚠️  Encore {50000 - len(g)} triplets manquants pour atteindre 50k")
else:
    print("\n✅ Objectif 50k atteint ! Prêt pour la session 6.")