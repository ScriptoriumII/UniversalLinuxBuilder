# Universal Linux Builder

Application Windows (PySide6) qui prépare et construit des ISO Linux personnalisées dans **WSL2** :
Debian (live-build + Calamares), Fedora (livemedia-creator + Anaconda), Arch Linux (archiso).
Gentoo et Slackware : projet exportable, **pas de construction ISO**.

> ⚠️ Statut honnête : la construction est **expérimentale**. Aucune ISO produite n'a encore été validée
> de bout en bout (démarrage Ventoy → installateur → GRUB sur disque). Le test QEMU intégré vérifie
> seulement qu'un écran s'affiche.

## Lancer

**Poste neuf (recommandé)** : double-clic sur `lancer.bat`. Il vérifie Python (3.10+), l'installe
avec winget si besoin, crée un environnement isolé `.venv`, installe PySide6, contrôle WSL2 et
lance l'application.

```powershell
py main.py --check        # diagnostic seul : Python, PySide6, WSL2, distributions, virtualisation, disque
py main.py                # contrôle, installe PySide6 si absent, puis ouvre l'interface
py main.py --no-install   # contrôle sans rien installer
```

Ce que le pré-contrôle ne peut pas faire à ta place : activer la virtualisation dans le BIOS/UEFI,
installer WSL2 (`wsl --install --no-distribution` dans PowerShell administrateur, puis redémarrage)
et installer une distribution (onglet **WSL2**). Il affiche la commande exacte pour chaque cas.

Prérequis : Windows 10/11 avec WSL2 et une distribution de la même famille que la cible
(Debian pour Debian, Fedora de la **même version** pour Fedora, Arch pour Arch).
L'onglet **WSL2** détecte les distributions, vérifie/installe les outils de construction.

## Parcours

1. **Distribution** – famille et version.
2. **Système** – bureau, noyau, audio, GRUB (UEFI ou BIOS) et options.
3. **Applications** – recherche de paquets dans le gestionnaire de l'environnement WSL.
4. **Vérification** – outils, puis analyse des dépendances (simulation).
5. **Virtualisation** – essayer une ISO dans QEMU/KVM (web noVNC, fenêtre WSLg ou VNC), installer sur un disque virtuel puis démarrer sur ce disque.
6. **ISO** – profil Standard/Léger, options, **Créer l'ISO**, **Tester le démarrage (QEMU)**. La barre de construction affiche un pourcentage et une estimation du temps restant (affinée à chaque construction réussie).

Un dossier de sortie contient : `ULB_<famille>_<version>_<date-heure>.iso`, `SHA256SUMS` (complété, jamais écrasé), `build_report_<date-heure>.txt`. Le dossier peut déjà contenir d'autres ISO : tes ISO existantes ne sont jamais écrasées
(et `boot_test_uefi.png` après un test de démarrage).

## Limites connues

- Arch Linux : ISO live **sans installateur graphique** (Calamares n'est que dans l'AUR).
- Fedora : `--no-virt` exécute Anaconda dans l'environnement WSL ; utiliser un WSL Fedora dédié.
- Les noms de paquets sont validés par l'étape « Analyser les paquets » ; certains (ex. `lightdm-gtk` sous Fedora) restent à confirmer.
- Le test QEMU sans KVM (WSL imbriqué) est lent : prévoir 120–240 s.
- L'exécutable (`tools/build_exe.bat`, PyInstaller) n'est pas testé automatiquement.

## Développement

```bash
pip install -r requirements-dev.txt
python -m pyflakes ulb tests main.py
python -m pytest -q          # utilise un faux wsl.exe (tests/fakes), Linux/macOS
```

Structure : `ulb/constants.py` (données), `wsl.py` (exécution, flux, annulation), `environments.py`,
`packages.py`, `checklist.py`, `builders.py`, `vmtest.py`, `projects.py`, `ui.py`.
Anciennes versions monolithiques : `archive/`.
