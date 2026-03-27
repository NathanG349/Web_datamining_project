from owlready2 import *

# ==========================================
# Charger le fichier family.owl
# ==========================================
print("Chargement de family.owl...")
onto = get_ontology("family.owl").load()
print(f"  Ontologie chargée : {onto.base_iri}")
print(f"  Classes     : {[c.name for c in onto.classes()]}")
print(f"  Propriétés  : {[p.name for p in onto.properties()]}")

# ==========================================
# Afficher les individus existants
# ==========================================
print("\nIndividus dans l'ontologie :")
for individual in onto.individuals():
    age = getattr(individual, "age", None)
    if isinstance(age, list):
        age = age[0] if age else None
    print(f"  {individual.name} — age: {age}")

# ==========================================
# Créer la classe oldPerson
# ==========================================
with onto:
    class oldPerson(onto.Person):
        """Personne de plus de 60 ans (inférée par règle SWRL)."""
        pass
print("\nClasse 'oldPerson' créée")

# ==========================================
# Règle SWRL (appliquée manuellement en Python)
# Person(?p) ∧ age(?p, ?a) ∧ swrlb:greaterThan(?a, 60) → oldPerson(?p)
# ==========================================
print("\nApplication de la règle SWRL :")
print("  Person(?p) ∧ age(?p, ?a) ∧ greaterThan(?a, 60) → oldPerson(?p)")
print()

inferred = []
with onto:
    for individual in onto.individuals():
        if not isinstance(individual, onto.Person):
            continue
        age = getattr(individual, "age", None)
        if isinstance(age, list):
            age = age[0] if age else None
        if age is None:
            continue
        if int(age) > 60:
            individual.is_a.append(oldPerson)
            inferred.append((individual.name, int(age)))
            print(f"  → Inféré : {individual.name} (age={age}) est une oldPerson")

# ==========================================
# Résultats
# ==========================================
print(f"\n=== RÉSULTATS ===")
print(f"Individus classés oldPerson : {len(inferred)}")
for name, age in inferred:
    print(f"  ✅ {name} — age {age} > 60")

if not inferred:
    print("  ⚠️  Aucun individu avec age > 60 trouvé dans family.owl")
    print("\n  Individus et leurs âges :")
    for individual in onto.individuals():
        age = getattr(individual, "age", None)
        if isinstance(age, list):
            age = age[0] if age else None
        print(f"    {individual.name} → age = {age}")

# ==========================================
# Sauvegarder
# ==========================================
onto.save(file="family_reasoned.owl", format="rdfxml")
print("\nOntologie enrichie sauvegardée → family_reasoned.owl")

print("\n=== RÉSUMÉ POUR LE RAPPORT ===")
print("Règle SWRL définie :")
print("  Person(?p) ∧ age(?p, ?a) ∧ swrlb:greaterThan(?a, 60) → oldPerson(?p)")
print(f"Individus inférés comme oldPerson : {len(inferred)}")
for name, age in inferred:
    print(f"  - {name} (age={age})")