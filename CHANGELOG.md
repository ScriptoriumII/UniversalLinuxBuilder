# Journal des versions

## 2.0
- **Organisation** : code découpé en package `ulb/` (constantes, WSL, builders, interface…), lanceur `main.py`, anciennes versions déplacées dans `archive/` (et étiquetées `v1.20`, `v1.21`, `v1.22`), fichiers `.pyc` retirés du suivi Git, tests `pytest` et CI.
- **Opérations longues** : journal en direct (WSL, installation d'outils, actualisation des dépôts, construction ISO), barre de progression, bouton **Annuler**, fermeture sécurisée pendant une opération.
- **Construction** : contrôle de l'espace disque (WSL + Windows), micrologiciels non libres Debian (`non-free-firmware`), copie de l'ISO via `\\wsl.localhost` (repli `cat`), `SHA256SUMS`, nettoyage de l'espace de travail, rapport complet même en cas d'échec ou d'annulation.
- **Profil Léger** : Xfce, sans impression ni Bluetooth par défaut, Debian sans paquets « recommandés ».
- **Projet** : sauvegarde automatique de tous les choix, restauration au démarrage, import d'un projet (`universal_linux_project.json`) ou de l'ancien `distribution.json`.
- **Logos** : chargés en arrière-plan, plus de blocage au démarrage ; pastille de repli hors ligne.
- **Test de démarrage** : QEMU headless (UEFI ou BIOS), capture d'écran et verdict « écran affiché / vide ». Ne valide ni l'installateur ni Ventoy.

## 1.22
- Fedora : Anaconda (live) via `livemedia-creator --no-virt`.

## 1.21
- Retour de Budgie, paquets GRUB selon UEFI/BIOS, tableau « Chaîne d'installation ».

## 1.20
- Interface de la 1.16 + gestion WSL2 de la 1.18.
