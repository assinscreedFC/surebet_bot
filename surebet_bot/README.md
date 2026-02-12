# 🎯 Bot Surebet VDO Group

Bot automatisé de détection d'arbitrage (Surebet) multi-sports avec notifications Telegram en temps réel.

## ✨ Fonctionnalités

- **Scan automatique** toutes les 10 secondes
- **Multi-sports** : Football (17 ligues), NBA, Tennis, NFL
- **Multi-bookmakers** : Betclic, Winamax, Unibet, PMU, Pinnacle, etc.
- **Détection d'arbitrage** : h2h, totals (Over/Under), spreads
- **Notifications Telegram** instantanées avec mises optimales
- **Dashboard Streamlit** temps réel
- **Failover automatique** entre clés API
- **Base de données SQLite** pour l'historique

---

## 📁 Structure

```
surebet_bot/
├── main.py              # Point d'entrée
├── config.py            # Configuration
├── test_bot.py          # Tests
├── api_keys.txt         # Clés API (email:key)
│
├── core/
│   ├── api_manager.py   # Gestion multi-clés
│   ├── calculator.py    # Calcul d'arbitrage
│   ├── odds_client.py   # Client The Odds API
│   └── scanner.py       # Scanner async
│
├── data/
│   └── database.py      # SQLite
│
├── notifications/
│   └── telegram_bot.py  # Alertes
│
├── dashboard/
│   └── app.py           # Streamlit
│
└── utils/
    └── logger.py        # Logging
```

---

## 🚀 Installation

```bash
# Cloner le projet
cd d:\disc_E\vscode_pyhton\python\test\surebet_bot

# Installer les dépendances
pip install -r requirements.txt
```

### Dépendances

```
aiohttp>=3.9.0
aiosqlite>=0.19.0
streamlit>=1.30.0
pandas>=2.0.0
plotly>=5.18.0
requests>=2.31.0
python-dotenv>=1.0.0
```

---

## ⚙️ Configuration

### 1. Clés API The Odds API

Ajouter vos clés dans `api_keys.txt` :

```
email@exemple.com:votre_cle_api_32_caracteres
```

Obtenir une clé gratuite : https://the-odds-api.com

### 2. Telegram

Dans `config.py` ou via variables d'environnement :

```python
TELEGRAM_BOT_TOKEN = "votre_token"
TELEGRAM_CHAT_ID = "votre_chat_id"
```

---

## 🎮 Utilisation

### Lancer le bot

```bash
python main.py
```

### Lancer le dashboard

```bash
python main.py --dashboard
```

Puis ouvrir http://localhost:8501

### Tester l'API

```bash
python test_bot.py
```

---

## 📊 Comment ça marche ?

### Détection d'arbitrage

Un **surebet** existe quand la somme des probabilités implicites < 1 :

```
L = 1/cote_over + 1/cote_under

Si L < 1 → SUREBET détecté!
Profit = (1 - L) × 100%
```

**Exemple** :
- Over 2.5 @ 2.10 (Betclic)
- Under 2.5 @ 2.10 (Winamax)
- L = 0.476 + 0.476 = 0.952 < 1
- **Profit garanti : 5%**

### Format des alertes Telegram

```
🚀 OPPORTUNITÉ SUREBET DETECTÉE 🚀
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 Sport : Football - Ligue 1
⚽ Match : PSG vs Marseille
📊 Marché : Totals 2.5

✅ Betclic | Over 2.5 | 2.10 | Mise: 47.62€
✅ Winamax | Under 2.5 | 2.10 | Mise: 52.38€

📈 Profit : 5.04%
💰 Gain base 100€ : 5.04€
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VDO Group
```

---

## 🏆 Sports Supportés

### Football (17 ligues)
| Ligue | Clé API |
|-------|---------|
| Ligue 1 | `soccer_france_ligue_one` |
| Premier League | `soccer_epl` |
| La Liga | `soccer_spain_la_liga` |
| Serie A | `soccer_italy_serie_a` |
| Bundesliga | `soccer_germany_bundesliga` |
| Champions League | `soccer_uefa_champs_league` |
| ... | ... |

### Autres
- **NBA** : `basketball_nba`
- **NFL** : `americanfootball_nfl`
- **Tennis** : Grand Chelems

---

## 📈 Dashboard

Le dashboard Streamlit affiche :

- **Métriques** : Surebets détectés, profit total, quota API
- **Historique** : Tableau des opportunités
- **Statistiques** : Graphiques par sport/marché
- **Logs** : Console en temps réel

---

## 🔧 API The Odds

| Endpoint | Usage |
|----------|-------|
| `GET /sports` | Liste des sports |
| `GET /sports/{sport}/odds` | Cotes de base (h2h, totals) |
| `GET /sports/{sport}/events` | Liste événements |
| `GET /events/{id}/odds` | Player Props |

Documentation : https://the-odds-api.com/liveapi/guides/v4/

---

## 📝 Licence

VDO Group - Usage interne

---

## 🤝 Support

Pour toute question, contactez l'équipe VDO Group.
