# Contrôle périodique – option 3 (auto GitHub)

Cette version charge automatiquement le référentiel de contrôle depuis **`./data/controles.json`** hébergé dans le même dépôt GitHub Pages. Tu n'as donc plus besoin de charger les fichiers Excel à chaque ouverture.

## Structure recommandée du dépôt

```text
/               
├── index.html
├── README.md
├── generate_controles_json.py
├── /sources
│   ├── TEST Batteries BJONG.xlsx
│   ├── bjong.xlsx
│   └── batteries.xlsx
├── /data
│   └── controles.json
└── /.github/workflows
    └── build-controles-json.yml
```

## Principe

1. Tu déposes tes fichiers source dans **`/sources`**.
2. Le script **`generate_controles_json.py`** consolide tous les SN dans **`/data/controles.json`**.
3. L'application **`index.html`** charge automatiquement ce JSON au démarrage.
4. En option, le workflow GitHub Actions reconstruit automatiquement `controles.json` à chaque push sur `/sources`.

## Déploiement

### Option simple
- mets `index.html`, `README.md`, `generate_controles_json.py`, `data/controles.json` dans le repo
- active GitHub Pages sur la branche souhaitée
- ouvre le site GitHub Pages

### Option automatisée
- laisse aussi le fichier `.github/workflows/build-controles-json.yml`
- à chaque push sur `/sources`, GitHub Actions régénère `data/controles.json`

## Générer / mettre à jour le JSON localement

### Pré-requis
- Python 3.11+
- paquets : `pandas`, `openpyxl`, `xlrd`

### Commandes

```bash
pip install pandas openpyxl xlrd
python generate_controles_json.py
```

Le script lit tous les fichiers supportés présents dans **`/sources`** :
- `.xlsx`
- `.xls`
- `.csv`
- `.txt`

## Détection automatique des colonnes

Le script et l'app essaient d'identifier automatiquement :
- colonne **SN** : `NS Batterie`, `NS`, `NS (V)`, `SN`, `SN (V)`...
- colonne **date** : `Heure de début`, `DATE`, `Date contrôle`...

## Format de `data/controles.json`

Exemple :

```json
{
  "generatedAt": "2026-04-27T12:00:00Z",
  "count": 2,
  "items": {
    "202100132125": {
      "display": "202100132125",
      "source": "BATTERIE",
      "controlDateIso": "2026-03-09T15:40:03",
      "controlDateText": "09/03/2026 15:40:03",
      "sheet": "Sheet1",
      "file": "TEST Batteries BJONG.xlsx"
    }
  }
}
```

## Ce que fait l'app

- charge automatiquement `./data/controles.json`
- applique le **seuil personnalisable**
- scan **Code 128**
- affiche **OK** / **A CONTRÔLER**
- exporte l'historique en CSV
- permet de **recharger le référentiel** à la demande
- permet de **décharger le référentiel**
- permet de **flush** la base scannée

## Important

La caméra fonctionne uniquement si le site est ouvert en :
- **HTTPS**
- ou **localhost**

## Conseils pratiques

- conserve les fichiers Excel dans `/sources`
- n'expose publiquement dans l'app que le JSON consolidé
- si tu modifies souvent les fichiers source, garde le workflow GitHub Actions
- si tu veux rester simple, supprime le workflow et lance juste le script localement avant de pousser
