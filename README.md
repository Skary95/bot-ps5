# Bot de surveillance de sites web

Vérifie une zone précise de chaque page (un prix, une liste d'annonces…) toutes les
5 minutes via GitHub Actions et t'envoie un message Telegram quand elle change,
avec les lignes ajoutées ➕ et retirées ➖.

## Mise en place (≈ 10 minutes)

### 1. Créer le bot Telegram

1. Dans Telegram, ouvre une conversation avec **@BotFather** et envoie `/newbot`.
2. Choisis un nom puis un identifiant (finissant par `bot`).
3. BotFather te donne un **token** du type `123456789:AAH...` → garde-le.
4. Ouvre la conversation avec ton nouveau bot et envoie-lui n'importe quel message (ex. `salut`).
5. Dans ton navigateur, ouvre `https://api.telegram.org/bot<TON_TOKEN>/getUpdates`
   et repère `"chat":{"id": 123456789 ...}` → c'est ton **chat ID**.

### 2. Mettre le code sur GitHub

1. Crée un nouveau dépôt **public** sur GitHub (indispensable pour vérifier toutes les
   5 minutes gratuitement). Tout le monde pourra voir `sites.yaml` et `state.json`, mais
   ton token Telegram reste caché dans les secrets.
2. Envoie-y ces fichiers :

   ```bash
   git init && git add . && git commit -m "Bot de surveillance"
   git branch -M main
   git remote add origin https://github.com/<toi>/<depot>.git
   git push -u origin main
   ```

### 3. Ajouter les secrets

Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**

| Nom                  | Valeur              |
|----------------------|---------------------|
| `TELEGRAM_BOT_TOKEN` | le token de l'étape 1 |
| `TELEGRAM_CHAT_ID`   | le chat ID de l'étape 1 |

### 4. Lancer

Onglet **Actions → Surveillance des sites → Run workflow**. Tu dois recevoir un message
« 👀 Surveillance démarrée » par site. Ensuite, ça tourne tout seul.

## Ajouter un site

Modifie [sites.yaml](sites.yaml) (directement sur GitHub si tu veux) :

```yaml
  - name: Prix de la PS5
    url: https://www.exemple.fr/ps5
    selector: .product-price
```

Pour trouver le `selector` : clic droit sur la zone → **Inspecter**, puis clic droit sur
l'élément HTML surligné → **Copier → Copier le sélecteur**. Préfère un sélecteur court et
stable (`.product-price`, `#annonces`) plutôt qu'une longue chaîne `div > div:nth-child(3)…`.

Si une zone contient du texte qui change tout le temps (« il y a 5 minutes »), ajoute une
liste `ignore` d'expressions régulières pour l'exclure de la comparaison.

## Tester en local

```bash
pip install -r requirements.txt
python watcher.py --dry-run
```

`--dry-run` affiche les messages au lieu de les envoyer et ne touche pas à `state.json`.

## Les alertes

| Message | Signification |
|---------|---------------|
| 👀 Surveillance démarrée | nouveau site, contenu de référence enregistré |
| 🔔 Changement sur … | la zone a changé (détail des lignes) |
| ⚠️ Vérification impossible | site inaccessible ou sélecteur introuvable (envoyé une seule fois) |
| ✅ De nouveau accessible | le site répond à nouveau |

## Bon à savoir

- **Fréquence** : réglée dans [.github/workflows/watch.yml](.github/workflows/watch.yml)
  (`cron: "*/5 * * * *"`, le minimum de GitHub). En pratique, GitHub retarde souvent les
  exécutions de plusieurs minutes et en saute parfois quand il est chargé : compte plutôt
  sur une vérification toutes les 5 à 15 minutes.
- **Repasser en privé** : possible, mais remets alors `cron: "*/30 * * * *"`. Le quota
  gratuit des dépôts privés (2 000 minutes/mois) ne suffit pas pour toutes les 5 minutes.
- **Sites en JavaScript** : le bot lit le HTML envoyé par le serveur. Si la zone n'apparaît
  qu'après chargement JavaScript (alerte « sélecteur introuvable » alors qu'elle est visible
  dans le navigateur), dis-le moi : on peut ajouter un mode navigateur (Playwright).
- **Inactivité** : GitHub met en pause les tâches planifiées d'un dépôt sans activité
  pendant 60 jours. Les mises à jour de `state.json` comptent comme activité, mais si rien
  ne change pendant 2 mois, un mail de GitHub te proposera de les réactiver.
- Certains sites bloquent les robots ou l'interdisent dans leurs conditions : vérifie-les
  et garde une fréquence raisonnable.
