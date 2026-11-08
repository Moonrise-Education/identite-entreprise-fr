# Identité d'entreprise française — référentiels et normalisation

Ce dépôt rassemble ce qui nous a servi à redonner une **identité légale** à une base
de 47 000 entreprises françaises qui n'en avait aucune, et à y retrouver les doublons
sans en fabriquer de faux.

Il ne contient ni connecteur CRM, ni règle métier propre à une organisation : seulement
la partie générique, utile à qui travaille sur des données d'entreprises françaises.

Python 3.9+, **aucune dépendance externe**, aucun accès réseau à l'import.

## Ce qu'il y a dedans

| Fichier | Contenu |
| --- | --- |
| `annuaire.py` | Client de `recherche-entreprises.api.gouv.fr` : gratuit, sans clé, cadencé, avec reprise sur `429` et respect de `Retry-After` |
| `normaliser.py` | Domaines, téléphones en E.164, noms d'entreprise, et les contrôles qui s'appuient sur les référentiels |
| `referentiels.json` | 713 entrées mesurées, décrites ci-dessous |
| `test_normaliser.py` | 16 tests, chacun bâti sur un cas réellement rencontré |

## Les référentiels, et pourquoi ils existent

Chaque liste vient d'une mesure sur une base réelle, pas d'une intuition. Les notes
`*_note` du JSON portent le détail et l'incident qui a produit chaque liste.

| Liste | Entrées | À quoi elle sert |
| --- | --- | --- |
| `ambiguous_single_word_names` | 304 | Noms d'un seul mot trop courants pour identifier une société (`GUSTAVE`, `ATLAS`, `HORIZON`). Deux fiches qui partagent ce nom ne partagent rien |
| `frequent_company_words` | 265 | Mots trop répandus pour servir de clé de recherche ou de comparaison. `INTERNATIONAL CHAMBER OF COMMERCE` et `INTERNATIONAL COACHING FEDERATION` obtenaient 0,871 de similarité ; neuf domaines viticoles s'appariaient sur le seul mot `DOMAINE` |
| `third_party_web_hosts` | 65 | Hébergeurs, annuaires légaux, réseaux sociaux, raccourcisseurs. Un tel hôte dans un champ « site web » dit **où trouver** l'entreprise, pas **qui elle est** |
| `generic_email_domains` | 41 | Messageries grand public : une adresse personnelle n'identifie pas un employeur |
| `non_identifying_linkedin_slugs` | 13 | Slugs qui ne désignent aucune entreprise (`company`, `google`, `helloasso`) |
| `brand_network_domains` | 14 | Domaines d'**enseigne** : le site d'une marque, d'un réseau ou d'une franchise, porté par des entités juridiquement distinctes |
| `non_identifying_linkedin_pages` | 11 | Pages LinkedIn portées par trop de sociétés différentes pour prouver quoi que ce soit |

### La distinction qui nous a coûté le plus cher

`third_party_web_hosts` et `brand_network_domains` se ressemblent et demandent un
traitement **opposé**.

- Un **hébergeur tiers** n'est le domaine de personne. Il doit être **retiré** avant
  toute comparaison : deux fiches dont c'est le seul domaine n'ont aucun domaine, et
  l'absence n'est pas une divergence. Sans ce retrait, deux sociétés de la même
  entreprise paraissaient « diverger » parce que l'une avait sa fiche Pappers comme
  site.
- Un **domaine d'enseigne** est bien le domaine propre de l'entreprise, mais il
  identifie le réseau et non l'entité. Le retirer casserait les vrais doublons d'un
  même réseau. Il reste donc en place, et perd seulement le droit de **prouver** une
  identité.

Mesure qui a produit cette liste : trois caisses régionales du Crédit Agricole, trois
hôtels d'un même groupe et un franchisé face à son siège sortaient tous en
« même entreprise, certain », sur le seul partage d'un domaine de marque.

## Trois enseignements, chiffrés

**Le SIRET est la clé d'unicité, pas le SIREN.** Un SIREN désigne l'unité légale ;
tous ses établissements le partagent. Deux fiches de même SIREN peuvent être deux
sites bien réels. Seul le SIRET distingue un établissement.

**Les mentions légales sont la meilleure preuve disponible.** Toute entreprise
française doit y publier son SIREN ou son SIRET. Ce numéro ne vient ni d'un
rapprochement par le nom, ni d'un référentiel tiers, mais de l'entreprise elle-même :
c'est la provenance la plus indépendante qu'on puisse obtenir sans rien payer.

**Le téléphone n'identifie rien sans corroboration.** Sur 22 paires tirées au hasard
et rapprochées par le seul numéro, **aucune** n'était un vrai doublon : les plages
`+33 9 72`, `+33 1 88` et `+33 9 73` sont des standards mutualisés. Sur 73 groupes
formés par un numéro étranger, 53 n'avaient aucun autre lien — dont deux numéros en
`555`, préfixe réservé à la fiction en Amérique du Nord.

**Une abstention vaut mieux qu'une réponse fausse.** En cherchant 1 650 sites
d'entreprises, nous nous sommes abstenus 1 158 fois, sept fois sur dix. C'est ce taux
qui a rendu les 492 réponses exploitables : l'audit de 469 d'entre elles n'a trouvé
aucun hébergeur tiers et aucun faux positif.

## Usage

Tout ce qui suit est hors réseau, sauf `annuaire.API`.

```python
from normaliser import (domaine, identifiant_faible, telephone,
                        telephone_suspect, siren_depuis_url, nom_ambigu)

domaine("https://www.Exemple.fr/contact")   # 'exemple.fr'
domaine("192.168.1.1")                      # '' — une IP n'est pas un domaine

# « pourquoi ce domaine ne prouve rien », ou None s'il est exploitable
identifiant_faible("toucantoco.com")        # None
identifiant_faible("linkedin.com")          # 'hebergeur tiers : dit ou trouver, pas qui'
identifiant_faible("credit-agricole.fr")    # "domaine d'enseigne : identifie un reseau..."

telephone("01 88 32 10 00")                 # '+33188321000'
telephone_suspect("09 72 10 20 30")         # 'plage VoIP mutualisee : standard partage'
telephone_suspect("+18005551234")           # 'numero de fiction (prefixe 555...)'

# les annuaires légaux terminent leur URL par les 9 chiffres du SIREN
siren_depuis_url("pappers.fr/entreprise/lavauto-91-900526062")   # '900526062'

nom_ambigu("GUSTAVE")                       # True — plusieurs sociétés le portent
```

L'annuaire officiel, lui, sort sur le réseau :

```python
from annuaire import API
api = API()                 # cadence 0,30 s, reprise sur 429, cache en mémoire
```

`CADENCE` dans l'environnement permet de la changer, avec un plancher à 0,15 s pour
rester correct vis-à-vis d'une API publique et gratuite.

```sh
python3 test_normaliser.py      # 16 tests
```

## Licence

MIT. Les référentiels sont publiés dans le même esprit : réutilisables, à condition de
se souvenir qu'ils sont **empiriques**. Ils décrivent ce que nous avons rencontré, pas
l'ensemble des cas possibles. Une liste de ce genre se complète, elle ne se termine pas.
