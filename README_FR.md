# comptaPerso — Gestionnaire de finances personnelles multi-utilisateurs

*[Read this in English](README.md)*

Application Flask auto-hébergée : comptes multi-devises, catégories/sous-catégories,
transactions, virements entre comptes (multi-devises), dépenses/recettes récurrentes
avec validation mensuelle ajustable, et rapports (comparaison de périodes, mois par
mois, année par année). Interface disponible en français / anglais.

## Migrations de base de données (Alembic / Flask-Migrate)

Le schéma est géré via des migrations Alembic (`migrations/`), plutôt qu'un simple
`db.create_all()`. Cela permet de faire évoluer les tables plus tard (ajout d'une
colonne, etc.) sans perdre les données existantes.

**Avec Docker** : les migrations sont appliquées automatiquement au démarrage du
conteneur (`entrypoint.sh` lance `flask db upgrade` avant de démarrer gunicorn). Rien
à faire manuellement pour un déploiement standard.

**Sans Docker (dev local)**, après avoir cloné/modifié le projet :

```bash
export FLASK_APP=run.py
flask db upgrade        # applique les migrations existantes (premier lancement : crée les tables)
```

**Quand vous modifiez un modèle** (`app/models.py`), générez une nouvelle migration
et appliquez-la :

```bash
export FLASK_APP=run.py
flask db migrate -m "description du changement"   # génère migrations/versions/xxx.py
# → relisez le fichier généré (Alembic ne détecte pas tout : renommages de colonnes,
#   changements de type sous SQLite, etc. peuvent nécessiter un ajustement manuel)
flask db upgrade                                    # applique le changement
```

Avec Docker, pour générer une migration après avoir modifié les modèles :

```bash
docker compose exec comptaperso flask db migrate -m "description du changement"
docker compose exec comptaperso flask db upgrade
# puis copiez le fichier généré dans migrations/versions/ sur votre machine hôte
# (il est déjà dans le volume monté si vous montez le code en dev ; sinon
# docker cp comptaperso:/app/migrations/versions/xxx.py migrations/versions/)
```

## Démarrage rapide (Docker, SQLite)

```bash
docker compose up -d --build
```

Ouvrez ensuite http://votre-serveur:5000 et créez un compte utilisateur.

Les données SQLite persistent dans le volume Docker `comptaperso_data`
(`/app/data/compta.db` dans le conteneur).

**Pensez à changer `SECRET_KEY`** dans `docker-compose.yml` avant de passer en
production.

**Définir des variables d'environnement avec Docker** : éditez directement la liste
`environment:` dans `docker-compose.yml` — c'est ce qui définit déjà `SECRET_KEY`,
`DB_ENGINE`, `DATA_DIR`. Le fichier contient des exemples commentés pour les
paramètres SMTP (décommentez et renseignez ceux dont vous avez besoin) ; après
modification, réappliquez avec :

```bash
docker compose up -d
```

(pas besoin de `--build` pour un changement qui ne touche que l'environnement).

**Changer le port avec Docker** : `PORT` est la seule variable également lue par
Compose lui-même (pour le mapping `ports:`), pas seulement transmise au conteneur —
elle fonctionne donc différemment des autres variables ci-dessus : définissez-la dans
le shell ou dans un fichier `.env` à côté de `docker-compose.yml` (Compose charge
automatiquement celui-ci ; il n'a rien à voir avec le `.env.local` propre à ce
projet) :

```bash
echo "PORT=8080" > .env
docker compose up -d
```

## Variante MariaDB

```bash
docker compose -f docker-compose.mariadb.yml up -d --build
```

Changez les mots de passe dans ce fichier avant de démarrer.

## Sans Docker (dev / test rapide)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

L'application démarre sur http://localhost:5000 (SQLite dans `./data/compta.db`),
avec le débogueur/auto-reload de Flask désactivé par défaut — définissez
`FLASK_DEBUG=true` (voir ci-dessous) si vous le souhaitez pendant le développement.

**Définir des variables d'environnement sans Docker** : c'est `docker-compose.yml`
qui les injecte dans le parcours Docker — en lançant `python run.py` directement, il
n'y a pas un tel mécanisme, donc vous les définissez vous-même dans le shell. Copiez
le fichier d'exemple et chargez-le avant de démarrer l'application :

```bash
cp .env.local.example .env.local
# éditez .env.local avec vos propres valeurs
source .env.local && python run.py
```

`.env.local` est destiné à contenir vos vrais secrets locaux — ne le committez pas.
(Il n'y a pas de chargement automatique via `python-dotenv` ici ; c'est le `source`
du fichier qui exporte les variables dans votre shell avant que `run.py` ne démarre.)

## Configuration (variables d'environnement)

- `SECRET_KEY` — secret de session Flask, à changer en production.
- `DB_ENGINE` — `sqlite` (par défaut) ou `mariadb`.
- `DATA_DIR` — répertoire de données SQLite (par défaut `./data`).
- `ALLOW_REGISTRATION` — mettre à `false` pour désactiver l'inscription libre une
  fois vos utilisateurs mis en place (par défaut : activée). Le tout premier compte
  créé sur une installation obtient automatiquement les droits d'administrateur,
  quel que soit ce réglage — les administrateurs peuvent toujours inviter de
  nouveaux utilisateurs par e-mail depuis le menu « Administration », même quand
  l'inscription libre est désactivée.
- `PORT` — port sur lequel l'application écoute (par défaut `5000`). Utilisé par
  `python run.py` directement, ainsi que par l'entrypoint Docker (gunicorn) et le
  mapping `ports:` dans `docker-compose*.yml`.
- `FLASK_DEBUG` — mettre à `true` pour activer le débogueur/auto-reload de Flask en
  développement local (par défaut : `false`). **Doit rester à `false` en
  production** — le débogueur permet l'exécution de code arbitraire s'il est jamais
  accessible depuis l'extérieur. N'affecte que `python run.py` ; le parcours Docker
  utilise toujours gunicorn et ne l'active jamais, quel que soit ce réglage.
- `SKIP_DB_UPGRADE` — mettre à `true` pour sauter la vérification/mise à jour
  automatique du schéma au démarrage (utile pour les commandes `flask db ...`
  elles-mêmes, ou pour du dépannage).
- `BACKUP_DIR` / `BACKUP_KEEP` — où sont écrites les sauvegardes SQLite avant chaque
  migration au démarrage, et combien en conserver (par défaut : `./data/backups`,
  20).
- `ATTACHMENTS_DIR` — où sont stockées les pièces jointes des transactions (reçus,
  images ou PDF, 10 Mo max) (par défaut `./data/attachments`).
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` — serveur de
  messagerie sortant, utilisé pour les e-mails de « mot de passe oublié ». Laissez
  `SMTP_HOST` vide pour désactiver l'envoi (les demandes de réinitialisation
  réussissent toujours sans erreur visible, mais l'e-mail n'est que journalisé côté
  serveur, pas envoyé — pratique pour le dev local).
- `SMTP_USE_TLS` (par défaut `true`) / `SMTP_USE_SSL` (par défaut `false`) —
  choisissez selon votre fournisseur (STARTTLS sur le port 587 vs TLS implicite sur
  le port 465).
- `MAIL_FROM` — l'adresse « De » sur les e-mails sortants (par défaut
  `no-reply@comptaperso.local`).
- `PASSWORD_RESET_TOKEN_MAX_AGE` — durée de validité d'un lien de réinitialisation de
  mot de passe, en secondes (par défaut 3600 = 1 heure).

## Comment fonctionnent les règles récurrentes (le point important)

1. Onglet **Récurrences** → créez une règle (libellé, compte, catégorie, montant
   approximatif, périodicité, date de début).
2. Onglet **Budget mensuel** : chaque règle active dont la prochaine échéance tombe
   dans le mois affiché (ou est en retard) apparaît en haut, modifiable ligne par
   ligne (montant + date exacte).
3. Cliquer sur **Valider** crée la transaction réelle avec les valeurs ajustées et
   calcule automatiquement la prochaine échéance selon la périodicité.
4. Les occurrences non validées restent visibles (marquées « en retard ») jusqu'à
   leur traitement — rien n'est généré automatiquement en arrière-plan.

## Virements multi-devises

Dans **Virements → Ajouter**, choisissez le compte source et le compte destination :
si les devises diffèrent, saisissez séparément le montant envoyé et le montant reçu
(pour refléter le taux de change réel / les frais). Si c'est la même devise, le
montant reçu est recopié automatiquement (modifiable si besoin).

## Ce qui est volontairement simplifié dans cette v1

- Pas d'import CSV/OFX bancaire (peut être ajouté si utile).
- Pas de conversion vers une « devise de référence » unique (les soldes/rapports
  restent par compte/devise ; pas de conversion multi-devises agrégée pour
  l'instant).
- Pas encore de graphiques (les rapports sont sous forme de tableaux).

## Structure du projet

```
app/
  config.py           configuration (SQLite / MariaDB via variables d'environnement)
  models.py            User, Account, Category, Transaction, RecurringRule
  utils.py              calculs des dates d'échéance récurrentes
  translations.py        dictionnaire fr/en
  routes/                un blueprint par domaine fonctionnel
  templates/              Jinja2, CSS personnalisé (aucune dépendance CDN)
Dockerfile
docker-compose.yml            SQLite
docker-compose.mariadb.yml    MariaDB
```
