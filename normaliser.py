"""Normalisation de domaines, telephones et noms d'entreprises francaises.

Module PUR : aucun acces reseau, aucune dependance externe, rien a l'import que
la lecture de `referentiels.json` pose a cote de ce fichier.

Les regles implementees ici ne sont pas des conventions : chacune vient d'une
mesure sur une base reelle de 47 000 entreprises, et le README donne l'incident
qui l'a produite.
"""
import ipaddress
import json
import pathlib
import re
import unicodedata
from urllib.parse import urlsplit

_R = json.loads((pathlib.Path(__file__).resolve().with_name('referentiels.json')).read_text(encoding='utf-8'))

HOTES_TIERS = frozenset(_R['third_party_web_hosts'])
ENSEIGNES = frozenset(_R['brand_network_domains'])
MESSAGERIES = frozenset(_R['generic_email_domains'])
MOTS_FREQUENTS = frozenset(_R['frequent_company_words'])
NOMS_AMBIGUS = frozenset(_R['ambiguous_single_word_names'])
SLUGS_NON_IDENTIFIANTS = frozenset(_R['non_identifying_linkedin_slugs'])


def _texte(value):
    return '' if value is None else str(value).strip()


def nom_normalise(value):
    """Minuscules, accents retires, ponctuation reduite a des espaces."""
    value = unicodedata.normalize('NFKD', _texte(value).casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', value))


FORMES_JURIDIQUES = frozenset(nom_normalise(v) for v in (
    'SAS', 'SARL', 'SASU', 'EURL', 'SA', 'association', 'micro-entreprise',
    'auto entrepreneur', 'EI', 'EIRL', 'SCI', 'SNC', 'SCS', 'SCA', 'SCOP',
    'SCIC', 'SEL', 'SELARL', 'SELAS', 'GIE',
    'société par actions simplifiée',
    'société par actions simplifiée unipersonnelle',
    'société à responsabilité limitée',
    'entreprise unipersonnelle à responsabilité limitée',
    'société anonyme', 'entreprise individuelle', 'société civile immobilière',
    'société en nom collectif', 'société en commandite simple',
    'société en commandite par actions', "groupement d'intérêt économique",
))


def nom_sans_forme_juridique(value):
    """Le nom une fois la forme juridique retiree. « MARTIN SAS » -> « martin »."""
    return ' '.join(m for m in nom_normalise(value).split() if m not in FORMES_JURIDIQUES)


def mots_distinctifs(value):
    """Les mots du nom qui identifient vraiment, formes juridiques et mots
    trop frequents retires. C'est sur eux que deux noms se comparent.

    « INTERNATIONAL CHAMBER OF COMMERCE » et « INTERNATIONAL COACHING FEDERATION »
    obtenaient 0,871 de similarite par Jaro-Winkler ; neuf domaines viticoles
    s'appariaient sur le seul mot « DOMAINE ».
    """
    frequents = {nom_normalise(m) for m in MOTS_FREQUENTS}
    return [m for m in nom_sans_forme_juridique(value).split()
            if m not in frequents and len(m) > 2]


def nom_ambigu(value):
    """Un nom d'un seul mot trop repandu pour designer une entreprise.

    « GUSTAVE », « ATLAS », « HORIZON » : plusieurs societes sans lien le portent.
    Deux fiches qui partagent un tel nom ne partagent rien.
    """
    normalises = {nom_normalise(n) for n in NOMS_AMBIGUS}
    reste = nom_sans_forme_juridique(value)
    return bool(reste) and ' ' not in reste and reste in normalises


def domaine(value):
    """Hote normalise, ou chaine vide. Rejette les IP, les URL malformees,
    les schemas non http(s) et tout ce qui porte des identifiants."""
    value = _texte(value)
    if not value or re.search(r'\s', value):
        return ''
    try:
        parsed = urlsplit(value if '://' in value or value.startswith('//') else '//' + value)
        if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
            return ''
        if parsed.username is not None or parsed.password is not None:
            return ''
        host = (parsed.hostname or '').rstrip('.').lower().encode('idna').decode()
        if host.startswith('www.'):
            host = host[4:]
    except (ValueError, UnicodeError):
        return ''
    try:
        ipaddress.ip_address(host)
        return ''  # une IP n'est pas un domaine d'entreprise
    except ValueError:
        pass
    if not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}', host):
        return ''
    return host


def _dans(host, liste):
    host = (host or '').lower().lstrip('.')
    return any(host == d or host.endswith('.' + d) for d in liste)


def hote_tiers(value):
    """Hebergeur, annuaire legal, reseau social, raccourcisseur : il dit OU
    trouver l'entreprise, pas QUI elle est. A retirer avant toute comparaison."""
    return _dans(domaine(value) or _texte(value).lower(), HOTES_TIERS)


def enseigne(value):
    """Domaine de marque, de reseau ou de franchise, porte par des entites
    juridiquement distinctes. A garder, mais il ne prouve aucune identite."""
    return _dans(domaine(value) or _texte(value).lower(), ENSEIGNES)


def messagerie_grand_public(value):
    """Domaine de messagerie personnelle : il n'identifie aucun employeur."""
    return _dans(domaine(value) or _texte(value).lower(), MESSAGERIES)


def identifiant_faible(value):
    """Le domaine est-il inutilisable comme preuve d'identite, et pourquoi ?

    Renvoie None quand le domaine est exploitable, sinon le motif.
    """
    d = domaine(value)
    if not d:
        return 'domaine illisible'
    if hote_tiers(d):
        return 'hebergeur tiers : dit ou trouver, pas qui'
    if messagerie_grand_public(d):
        return 'messagerie grand public'
    if enseigne(d):
        return "domaine d'enseigne : identifie un reseau, pas une entite"
    return None


# Plages VoIP mutualisees : un standard partage par des dizaines de societes.
# Mesure : sur 22 paires rapprochees par le seul numero, 0 doublon reel.
PLAGES_MUTUALISEES = ('+33972', '+33188', '+33973')


def telephone(value):
    """Numero en E.164, ou chaine vide. Deterministe, sans reseau."""
    brut = re.sub(r'[^0-9+]', '', _texte(value))
    if not brut:
        return ''
    if brut.startswith('00'):
        brut = '+' + brut[2:]
    if brut.startswith('0') and len(brut) == 10:
        brut = '+33' + brut[1:]
    if not brut.startswith('+'):
        return ''
    chiffres = brut[1:]
    if not chiffres.isdigit() or not 8 <= len(chiffres) <= 15:
        return ''
    # Un numero a un seul chiffre repete n'identifie rien (0000000000).
    if len(set(chiffres)) <= 2:
        return ''
    return '+' + chiffres


def telephone_suspect(value):
    """Le numero est-il inutilisable comme signal d'identite, et pourquoi ?

    Renvoie None quand il est exploitable, sinon le motif.
    """
    t = telephone(value)
    if not t:
        return 'numero illisible'
    if t.startswith(PLAGES_MUTUALISEES):
        return 'plage VoIP mutualisee : standard partage'
    # Prefixe 555 en Amerique du Nord : reserve a la fiction. Deux numeros de
    # cette forme ont ete trouves en base, dont +18005551234.
    if re.fullmatch(r'\+1\d{3}555\d{4}', t):
        return 'numero de fiction (prefixe 555 nord-americain)'
    if not t.startswith('+33'):
        return 'numero etranger : 53 groupes sur 73 sans aucun autre lien'
    return None


def siren_depuis_url(value):
    """Le SIREN cache dans une URL d'annuaire legal, ou chaine vide.

    `pappers.fr/entreprise/lavauto-91-900526062` -> `900526062`. Les annuaires
    francais terminent leur adresse par les 9 chiffres du SIREN : inutile
    d'ouvrir la page.
    """
    m = re.search(r'(?<!\d)(\d{9})(?!\d)', re.sub(r'\.html?$', '', _texte(value)))
    return m.group(1) if m else ''
