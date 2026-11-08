"""Client public paginé ; transport et horloge injectables."""
import datetime
import email.utils
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
URL = "https://recherche-entreprises.api.gouv.fr/search"

class API:
    """Client séquentiel limité par CADENCE (0,30 s par défaut), nouvelles tentatives incluses.

    Une instance doit être partagée pour le lot ; pas d'usage concurrent.
    Le cache reste en mémoire, uniquement pendant l'exécution.
    """

    def __init__(self, opener=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic, cadence=None):
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.cadence = float(os.environ.get("CADENCE", "0.30") if cadence is None else cadence)
        if not math.isfinite(self.cadence) or self.cadence < 0.15:
            raise ValueError("CADENCE doit être finie et >= 0.15 s")
        self.dernier_depart = 0.0
        self.cache = {}

    def page(self, params):
        url = URL + "?" + urllib.parse.urlencode(params)
        for tentative in range(5):
            self.sleep(max(0, self.dernier_depart + self.cadence - self.clock()))
            self.dernier_depart = self.clock()
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with self.opener(req, timeout=30) as reponse:
                    return json.load(reponse)
            except urllib.error.HTTPError as erreur:
                if erreur.code not in (429, 500, 502, 503, 504) or tentative == 4:
                    raise
                attente = 2 ** tentative
                retry = erreur.headers.get("Retry-After", "")
                try:
                    attente = max(attente, float(retry))
                except ValueError:
                    try:
                        date = email.utils.parsedate_to_datetime(retry)
                        attente = max(attente, (date - datetime.datetime.now(
                            datetime.timezone.utc)).total_seconds())
                    except (ValueError, TypeError, OverflowError):
                        pass
                erreur.close()
                self.sleep(attente)
            except (urllib.error.URLError, TimeoutError):
                if tentative == 4:
                    raise
                self.sleep(2 ** tentative)

    def rechercher(self, nom, cp):
        cle = (nom, cp)
        if cle in self.cache:
            return self.cache[cle]
        params = {"q": nom, "per_page": 25, "page": 1}
        if cp:
            params["code_postal"] = cp
        candidats = {}
        total_attendu = None
        # Ne jamais décider sur une première page seulement.
        for numero in range(1, 101):
            params["page"] = numero
            data = self.page(params)
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise ValueError("réponse API invalide")
            total = data.get("total_results")
            pages = data.get("total_pages")
            if type(total) is not int or type(pages) is not int or total < 0 or pages < 0:
                raise ValueError("pagination API absente ou invalide")
            if total_attendu is None:
                total_attendu = total
            if total != total_attendu or pages > 100:
                raise ValueError("recherche trop large ou résultats changeants")
            for candidat in data["results"]:
                if not isinstance(candidat, dict):
                    raise ValueError("Candidat API invalide")
                siren = candidat.get("siren", "")
                if not isinstance(siren, str) or not re.fullmatch(r"[0-9]{9}", siren):
                    raise ValueError("SIREN API invalide")
                candidats[siren] = candidat
            if numero >= pages:
                if len(candidats) != total:
                    raise ValueError("résultats incomplets : unicité non vérifiable")
                resultat = list(candidats.values())
                self.cache[cle] = resultat
                return resultat
        raise ValueError("pagination incomplète")

    def par_siren(self, siren):
        if not re.fullmatch(r"[0-9]{9}", siren):
            raise ValueError("SIREN invalide")
        return next((r for r in self.rechercher(siren, "") if r["siren"] == siren), None)
