"""Chaque cas vient d'une fiche reelle rencontree pendant le chantier."""
import unittest

from normaliser import (domaine, enseigne, hote_tiers, identifiant_faible,
                        messagerie_grand_public, mots_distinctifs, nom_ambigu,
                        nom_normalise, nom_sans_forme_juridique,
                        siren_depuis_url, telephone, telephone_suspect)


class Domaines(unittest.TestCase):
    def test_formes_dun_meme_domaine(self):
        for brut in ('https://www.Exemple.fr/contact', 'WWW.EXEMPLE.FR',
                     'exemple.fr.', '//exemple.fr'):
            self.assertEqual(domaine(brut), 'exemple.fr', brut)

    def test_rejets(self):
        for brut in ('', '   ', 'deux mots.fr', 'ftp://exemple.fr', '192.168.1.1',
                     'http://user:pass@exemple.fr', 'localhost', None):
            self.assertEqual(domaine(brut), '', repr(brut))

    def test_hote_tiers_et_sous_domaine(self):
        self.assertTrue(hote_tiers('linkedin.com'))
        self.assertTrue(hote_tiers('https://www.pappers.fr/entreprise/x-900526062'))
        self.assertTrue(hote_tiers('alpha.wixsite.com'))
        self.assertFalse(hote_tiers('monsieur-lucien.fr'))

    def test_enseigne_et_sous_domaine(self):
        # Trois caisses regionales distinctes partagent ce domaine.
        self.assertTrue(enseigne('credit-agricole.fr'))
        # Un sous-domaine d'enseigne en est un aussi.
        self.assertTrue(enseigne('all.accor.com'))
        self.assertTrue(enseigne('bmw-bordeaux.edenauto.com'))
        self.assertFalse(enseigne('toucantoco.com'))

    def test_une_enseigne_nest_pas_un_hote_tiers(self):
        # La distinction qui a coute le plus cher : un hote tiers n'est le
        # domaine de personne, une enseigne est bien celui de l'entreprise.
        self.assertTrue(enseigne('mcdonalds.fr'))
        self.assertFalse(hote_tiers('mcdonalds.fr'))

    def test_messagerie(self):
        self.assertTrue(messagerie_grand_public('gmail.com'))
        self.assertFalse(messagerie_grand_public('toucantoco.com'))

    def test_motif_dexclusion(self):
        self.assertIsNone(identifiant_faible('toucantoco.com'))
        self.assertIn('hebergeur tiers', identifiant_faible('linkedin.com'))
        self.assertIn('enseigne', identifiant_faible('credit-agricole.fr'))
        self.assertIn('messagerie', identifiant_faible('gmail.com'))
        self.assertIn('illisible', identifiant_faible('pas un domaine'))


class Noms(unittest.TestCase):
    def test_normalisation(self):
        self.assertEqual(nom_normalise('Crédit Agricole  d’Aquitaine'),
                         'credit agricole d aquitaine')

    def test_forme_juridique_retiree(self):
        self.assertEqual(nom_sans_forme_juridique('MARTIN SAS'), 'martin')
        self.assertEqual(nom_sans_forme_juridique('SARL Dupont'), 'dupont')

    def test_mots_distinctifs_ecarte_les_frequents(self):
        mots = mots_distinctifs('INTERNATIONAL COACHING FEDERATION')
        self.assertNotIn('international', mots)

    def test_nom_dun_mot_ambigu(self):
        self.assertTrue(nom_ambigu('GUSTAVE'))
        self.assertTrue(nom_ambigu('Gustave SAS'))   # la forme juridique ne compte pas
        self.assertFalse(nom_ambigu('GUSTAVE EIFFEL FORMATION'))


class Telephones(unittest.TestCase):
    def test_formats_francais(self):
        for brut in ('01 88 32 10 00', '0188321000', '+33 1 88 32 10 00',
                     '0033188321000'):
            self.assertEqual(telephone(brut), '+33188321000', brut)

    def test_rejets(self):
        for brut in ('', 'pas un numero', '0000000000', '1234', None):
            self.assertEqual(telephone(brut), '', repr(brut))

    def test_motifs_de_suspicion(self):
        self.assertIn('mutualisee', telephone_suspect('09 72 10 20 30'))
        self.assertIn('fiction', telephone_suspect('+18005551234'))
        self.assertIn('etranger', telephone_suspect('+442079460000'))
        self.assertIsNone(telephone_suspect('01 45 67 89 10'))


class SirenDansUrl(unittest.TestCase):
    def test_annuaires_legaux(self):
        self.assertEqual(
            siren_depuis_url('https://www.pappers.fr/entreprise/lavauto-91-900526062'),
            '900526062')
        self.assertEqual(
            siren_depuis_url('societe.com/societe/elkano-capital-911382513.html'),
            '911382513')

    def test_rien_a_extraire(self):
        self.assertEqual(siren_depuis_url('https://exemple.fr/contact'), '')


if __name__ == '__main__':
    unittest.main()
