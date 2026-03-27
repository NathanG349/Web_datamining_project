import requests
import time
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

# ==========================================
# Configuration
# ==========================================
TMDB_API_KEY = "Here i just masked my key"  # <-- remplace ici
TMDB_BASE    = "https://api.themoviedb.org/3"
OUTPUT_FILE  = "movies_graph.ttl"

# Nombre de pages de films populaires à récupérer (1 page = 20 films)
# 25 pages = ~500 films, suffisant pour la session 4
NB_PAGES = 25

# ==========================================
# Namespaces RDF
# ==========================================
MV = Namespace("http://example.org/movies#")
WD = Namespace("http://www.wikidata.org/entity/")

g = Graph()
g.bind("mv",  MV)
g.bind("wd",  WD)
g.bind("owl", OWL)
g.bind("rdf", RDF)
g.bind("rdfs",RDFS)
g.bind("xsd", XSD)

# ==========================================
# Définition des classes et propriétés
# ==========================================
for cls in ["Movie", "Director", "Actor", "Genre", "ProductionCompany", "Country"]:
    g.add((MV[cls], RDF.type, OWL.Class))
    g.add((MV[cls], RDFS.label, Literal(cls)))

props = {
    "hasTitle":    (MV.Movie, XSD.string),
    "directedBy":  (MV.Movie, MV.Director),
    "hasActor":    (MV.Movie, MV.Actor),
    "hasGenre":    (MV.Movie, MV.Genre),
    "releasedIn":  (MV.Movie, XSD.integer),
    "hasRating":   (MV.Movie, XSD.float),
    "hasVoteCount":(MV.Movie, XSD.integer),
    "hasBudget":   (MV.Movie, XSD.float),
    "hasRevenue":  (MV.Movie, XSD.float),
    "hasOverview": (MV.Movie, XSD.string),
    "hasDuration": (MV.Movie, XSD.integer),
    "hasLanguage": (MV.Movie, XSD.string),
    "hasName":     (None,     XSD.string),
    "bornIn":      (MV.Director, XSD.string),
    "nationality": (MV.Director, MV.Country),
    "producedBy":  (MV.Movie, MV.ProductionCompany),
    "hasPopularity":(MV.Movie, XSD.float),
}
for prop, (domain, range_) in props.items():
    g.add((MV[prop], RDF.type, OWL.DatatypeProperty if range_ in [XSD.string, XSD.integer, XSD.float] else OWL.ObjectProperty))

# ==========================================
# Helpers
# ==========================================
def safe_uri(name: str) -> str:
    """Convertit un nom en URI valide."""
    return name.strip().replace(" ", "_").replace("/", "_").replace("'", "").replace(":", "").replace(".", "")

def add_genre(genre_id: int, genre_name: str):
    uri = MV[f"Genre_{genre_id}"]
    g.add((uri, RDF.type, MV.Genre))
    g.add((uri, MV.hasName, Literal(genre_name)))
    return uri

def add_company(company_id: int, company_name: str):
    uri = MV[f"Company_{company_id}"]
    g.add((uri, RDF.type, MV.ProductionCompany))
    g.add((uri, MV.hasName, Literal(company_name)))
    return uri

def add_country(iso: str, name: str):
    uri = MV[f"Country_{iso}"]
    g.add((uri, RDF.type, MV.Country))
    g.add((uri, MV.hasName, Literal(name)))
    return uri

def add_person(person_id: int, person_name: str, role: str):
    uri = MV[f"{role}_{person_id}"]
    g.add((uri, RDF.type, MV[role]))
    g.add((uri, MV.hasName, Literal(person_name)))
    return uri

# ==========================================
# Récupérer les genres TMDB
# ==========================================
print("Récupération des genres...")
r = requests.get(f"{TMDB_BASE}/genre/movie/list", params={"api_key": TMDB_API_KEY, "language": "en-US"})
genre_map = {g_["id"]: g_["name"] for g_ in r.json().get("genres", [])}
print(f"  {len(genre_map)} genres trouvés")

# ==========================================
# Récupérer les films populaires (pagination)
# ==========================================
movie_ids = []
print(f"Récupération des films populaires ({NB_PAGES} pages)...")
for page in range(1, NB_PAGES + 1):
    r = requests.get(f"{TMDB_BASE}/movie/popular", params={
        "api_key": TMDB_API_KEY,
        "language": "en-US",
        "page": page
    })
    data = r.json()
    for movie in data.get("results", []):
        movie_ids.append(movie["id"])
    print(f"  Page {page}/{NB_PAGES} — {len(movie_ids)} films collectés", end="\r")
    time.sleep(0.25)  # respect rate limit

print(f"\nTotal films à traiter : {len(movie_ids)}")

# ==========================================
# Pour chaque film : détails + crédits
# ==========================================
processed = 0
for idx, movie_id in enumerate(movie_ids):
    try:
        # Détails du film
        r = requests.get(f"{TMDB_BASE}/movie/{movie_id}", params={
            "api_key": TMDB_API_KEY,
            "language": "en-US"
        })
        if r.status_code != 200:
            continue
        m = r.json()

        movie_uri = MV[f"Movie_{movie_id}"]
        g.add((movie_uri, RDF.type, MV.Movie))

        # Propriétés de base
        if m.get("title"):
            g.add((movie_uri, MV.hasTitle, Literal(m["title"])))
        if m.get("release_date") and len(m["release_date"]) >= 4:
            g.add((movie_uri, MV.releasedIn, Literal(int(m["release_date"][:4]), datatype=XSD.integer)))
        if m.get("vote_average"):
            g.add((movie_uri, MV.hasRating, Literal(float(m["vote_average"]), datatype=XSD.float)))
        if m.get("vote_count"):
            g.add((movie_uri, MV.hasVoteCount, Literal(int(m["vote_count"]), datatype=XSD.integer)))
        if m.get("budget") and m["budget"] > 0:
            g.add((movie_uri, MV.hasBudget, Literal(float(m["budget"]), datatype=XSD.float)))
        if m.get("revenue") and m["revenue"] > 0:
            g.add((movie_uri, MV.hasRevenue, Literal(float(m["revenue"]), datatype=XSD.float)))
        if m.get("runtime") and m["runtime"] > 0:
            g.add((movie_uri, MV.hasDuration, Literal(int(m["runtime"]), datatype=XSD.integer)))
        if m.get("original_language"):
            g.add((movie_uri, MV.hasLanguage, Literal(m["original_language"])))
        if m.get("popularity"):
            g.add((movie_uri, MV.hasPopularity, Literal(float(m["popularity"]), datatype=XSD.float)))
        if m.get("overview"):
            g.add((movie_uri, MV.hasOverview, Literal(m["overview"])))

        # Genres
        for genre in m.get("genres", []):
            genre_uri = add_genre(genre["id"], genre["name"])
            g.add((movie_uri, MV.hasGenre, genre_uri))

        # Sociétés de production
        for company in m.get("production_companies", []):
            company_uri = add_company(company["id"], company["name"])
            g.add((movie_uri, MV.producedBy, company_uri))

        # Pays de production
        for country in m.get("production_countries", []):
            country_uri = add_country(country["iso_3166_1"], country["name"])
            g.add((movie_uri, MV.hasCountry, country_uri))

        # Crédits (réalisateur + acteurs)
        time.sleep(0.1)
        r2 = requests.get(f"{TMDB_BASE}/movie/{movie_id}/credits", params={"api_key": TMDB_API_KEY})
        if r2.status_code == 200:
            credits = r2.json()

            # Réalisateur(s)
            for crew in credits.get("crew", []):
                if crew["job"] == "Director":
                    dir_uri = add_person(crew["id"], crew["name"], "Director")
                    g.add((movie_uri, MV.directedBy, dir_uri))
                    if crew.get("known_for_department"):
                        g.add((dir_uri, MV.department, Literal(crew["known_for_department"])))

            # Acteurs principaux (top 5)
            for actor in credits.get("cast", [])[:5]:
                actor_uri = add_person(actor["id"], actor["name"], "Actor")
                g.add((movie_uri, MV.hasActor, actor_uri))

        processed += 1
        if processed % 50 == 0:
            print(f"  Traités : {processed}/{len(movie_ids)} films — {len(g)} triplets")

        time.sleep(0.25)

    except Exception as e:
        print(f"  Erreur film {movie_id}: {e}")
        continue

# ==========================================
# Sauvegarde
# ==========================================
print(f"\nSauvegarde dans {OUTPUT_FILE}...")
g.serialize(destination=OUTPUT_FILE, format="turtle")
print(f"Terminé ! {len(g)} triplets sauvegardés dans {OUTPUT_FILE}")
print(f"Films traités : {processed}")