# État du Projet (Development Status)

Ce document recense les limitations actuelles, les fonctionnalités en cours de développement, et les bugs connus du projet **SureBet Bot**.

## 🚧 Fonctionnalités en Cours de Validation

### Routes API
- Les routes API définies dans le projet n'ont **pas encore été testées**.
- Leur comportement peut être instable ou incorrect.
- **Action requise :** Valider chaque endpoint avec des tests unitaires et d'intégration.

### Système de Détection d'Arbitrage (Surebet)
- L'algorithme de détection d'arbitrage est implémenté mais **non validé** en conditions réelles.
- Il peut produire des faux positifs ou manquer des opportunités.
- **Action requise :** Tester avec des données réelles sur une période prolongée et affiner les seuils de détection.

### Script d'Enregistrement (`scripts/odds_api_register.py`)
- Ce script est actuellement **excessivement long** et **non optimisé**.
- Il n'est pas encore finalisé et doit être refactorisé pour être efficace.
- **Action requise :** Optimiser le processus d'enregistrement et nettoyer le code.

## 🐛 Problèmes Connus

- La gestion des CAPTCHA audio peut parfois échouer selon la latence du réseau.
- Le failover des clés API nécessite une vérification plus approfondie pour assurer une transition sans coupure.

## 📅 Roadmap (À faire)

- [ ] Tester et valider les routes API.
- [ ] Valider le moteur de détection de surebets.
- [ ] Refactoriser et optimiser `odds_api_register.py`.
- [ ] Mettre en place des tests automatisés (CI/CD).
