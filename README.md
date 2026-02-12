# 🤖 SureBet Bot - Automatisation de Paris Sportifs

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Development-orange)

## 📖 Description

**SureBet Bot** est un outil avancé d'automatisation conçu pour détecter des opportunités d'arbitrage (surebets) dans les paris sportifs. Il surveille en temps réel les cotes de plusieurs bookmakers via **The Odds API**, analyse les différends de marché, et notifie l'utilisateur via Telegram lorsqu'une opportunité profitable est identifiée.

Le bot est conçu pour être résilient, avec une gestion automatique des erreurs, un contournement des protections (Cloudflare, Captcha), et un système de rotation de clés API.

## ✨ Fonctionnalités Principales

-   **🔍 Scanner en Temps Réel** : Surveille les cotes pour de nombreux sports (Football, Tennis, Basketball, etc.).
-   **📈 Détection de Surebets** : Identifie les écarts de cotes garantissant un profit mathématique.
-   **🔔 Notifications Instantanées** : Alertes Telegram détaillées avec le match, les cotes, et le profit estimé.
-   **🛡️ Contournement Anti-Bot** : Utilisation de `Scrapling` et gestion avancée des sessions pour éviter les blocages.
-   **🔄 Rotation de Clés API** : Bascule automatiquement sur une nouvelle clé API en cas d'épuisement du quota.
-   **📊 Dashboard (En Dev)** : Interface de visualisation des statistiques et des logs.

## 📂 Structure du Projet

```tree
.
├── .gitignore               # Fichiers à ignorer par Git
├── PROJECT_STATUS.md        # État du développement et limitations connues
├── README.md                # Documentation principale (ce fichier)
├── main.py                  # Point d'entrée principal du bot
├── requirements.txt         # Dépendances Python
├── scripts/                 # Scripts utilitaires et outils
│   ├── check_db.py          # Vérification de la base de données
│   ├── check_sports.py      # Vérification des sports disponibles
│   └── odds_api_register.py # Script d'enregistrement (WIP)
└── surebet_bot/             # Code source du bot
    ├── config.py            # Configuration globale
    ├── core/                # Cœur du système (Scanner, Fetcher)
    ├── dashboard/           # Interface Dashboard (Flask/Streamlit)
    ├── data/                # Gestion des données (Base de données)
    ├── notifications/       # Gestion des notifications (Telegram)
    └── utils/               # Fonctions utilitaires
```

## 🚀 Installation

1.  **Cloner le dépôt :**
    ```bash
    git clone https://github.com/votre-utilisateur/surebet-bot.git
    cd surebet-bot
    ```

2.  **Créer un environnement virtuel :**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate
    ```

3.  **Installer les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration :**
    -   Renommez `.env.example` en `.env` (si disponible) ou créez-en un.
    -   Ajoutez vos clés API (The Odds API, Telegram Bot Token, etc.) dans `surebet_bot/config.py` ou via les variables d'environnement.

## 💻 Utilisation

Pour lancer le bot :

```bash
python main.py
```

Le bot commencera à scanner les cotes selon la configuration définie.

## ⚠️ Avertissement

Ce projet est à but éducatif uniquement. L'utilisation de bots pour les paris sportifs peut être interdite par certains bookmakers. L'auteur n'est pas responsable des pertes financières ou des bannissements de compte.

Consultez `PROJECT_STATUS.md` pour connaître les limitations actuelles du projet.
