# Journal des versions

## 2.0.6
- **Pourcentage et temps restant** pendant la construction de l'ISO : la barre affiche « 42 % · Installation des paquets · reste ~8 min (estimation) ». Étapes détectées dans la sortie de la construction (debootstrap, apt, pacman, squashfs, ISO, copie vers Windows) avec compteurs de paquets quand ils existent.
- Les durées de chaque étape sont mémorisées après chaque construction réussie (`build_history`) : les estimations suivantes sont plus justes. Première construction : poids par défaut. Fedora : pas de compteur, estimation par le temps seulement (temps écoulé à la première construction).
- Le pourcentage ne recule jamais et reste sous 100 % tant que la construction n'est pas finie.

## 2.0.5
- **Flathub** pour les 5 familles : option « Flathub » (paquet flatpak + fichier du dépôt déposé dans `/etc/flatpak/remotes.d` de l'image Debian, Fedora, Arch) et bouton « Ajouter Flathub » dans WSL2 (installe flatpak si absent ; Slackware : instruction manuelle, flatpak n'étant pas dans les paquets officiels).
- **Fedora, dépôts tiers non libres** : option qui ajoute RPM Fusion libre + non libre et `fedora-workstation-repositories` à l'image (section `%post` du kickstart), et bouton « Dépôts tiers Fedora » dans WSL2.
- `curl` ajouté aux outils de construction (Debian, Fedora, Arch).

## 2.0.4
- **Onglet Virtualisation** (avant ISO) : machine QEMU/KVM réglée d'après le projet (UEFI/BIOS, RAM selon le bureau, virtio), démarrage sur une ISO ou sur le disque virtuel persistant (test d'installation puis de GRUB), variables UEFI conservées, affichage web noVNC, fenêtre WSLg ou client VNC, arrêt propre, installation des outils.

## 2.0.3
- Fedora : si aucun paquet de kickstarts (`fedora-kickstarts` / `spin-kickstarts`) n'existe dans les dépôts, installation de git et clonage de `pagure.io/fedora-kickstarts` (branche `fN`) à la construction.

## 2.0.2
- Fedora : le paquet des kickstarts est résolu dynamiquement (`fedora-kickstarts` ou `spin-kickstarts` selon la version) au lieu d'échouer avec « No match for argument ».

## 2.0.1
- Arch : initialisation du trousseau pacman (`pacman-key --init && --populate archlinux`) avant l'installation des outils et l'actualisation des dépôts (corrige « keyring is not writable »).

## 2.0
- **Organisation** : code découpé en package `ulb/` (constantes, WSL, builders, interface…), lanceur `main.py`, anciennes versions déplacées dans `archive/` (et étiquetées `v1.20`, `v1.21`, `v1.22`), fichiers `.pyc` retirés du suivi Git, tests `pytest` et CI.
- **Opérations longues** : journal en direct (WSL, installation d'outils, actualisation des dépôts, construction ISO), barre de progression, bouton **Annuler**, fermeture sécurisée pendant une opération.
- **Construction** : contrôle de l'espace disque (WSL + Windows), micrologiciels non libres Debian (`non-free-firmware`), copie de l'ISO via `\\wsl.localhost` (repli `cat`), `SHA256SUMS`, nettoyage de l'espace de travail, rapport complet même en cas d'échec ou d'annulation.
- **Profil Léger** : Xfce, sans impression ni Bluetooth par défaut, Debian sans paquets « recommandés ».
- **Projet** : sauvegarde automatique de tous les choix, restauration au démarrage, import d'un projet (`universal_linux_project.json`) ou de l'ancien `distribution.json`.
- **Logos** : vrais logos des distributions embarqués (Simple Icons, CC0, couleurs officielles) — plus aucun accès réseau, affichage immédiat et hors ligne.
- **Test de démarrage** : QEMU headless (UEFI ou BIOS), capture d'écran et verdict « écran affiché / vide ». Ne valide ni l'installateur ni Ventoy.

## 1.22
- Fedora : Anaconda (live) via `livemedia-creator --no-virt`.

## 1.21
- Retour de Budgie, paquets GRUB selon UEFI/BIOS, tableau « Chaîne d'installation ».

## 1.20
- Interface de la 1.16 + gestion WSL2 de la 1.18.
