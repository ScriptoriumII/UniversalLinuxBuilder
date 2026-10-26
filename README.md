# Universal Linux Builder

Application Windows (PySide6) qui prépare et construit des ISO Linux personnalisées dans **WSL2** :
Debian (live-build + Calamares), Fedora (livemedia-creator + Anaconda), Arch Linux (archiso).
Gentoo et Slackware : projet exportable, **pas de construction ISO**.

> ⚠️ Statut honnête : la construction est **expérimentale**. Aucune ISO produite n'a encore été validée
> de bout en bout (démarrage Ventoy → installateur → GRUB sur disque). Le test QEMU intégré vérifie
> seulement qu'un écran s'affiche.

## Lancer

```powershell
py -m pip install -r requirements.txt
py main.py
```

Prérequis : Windows 10/11 avec WSL2 et une distribution de la même famille que la cible
(Debian pour Debian, Fedora de la **même version** pour Fedora, Arch pour Arch).
L'onglet **WSL2** détecte les distributions, vérifie/installe les outils de construction.

## Parcours

1. **Distribution** – famille et version.
2. **Système** – bureau, noyau, audio, GRUB (UEFI ou BIOS) et options.
3. **Applications** – recherche de paquets dans le gestionnaire de l'environnement WSL.
4. **Vérification** – outils, puis analyse des dépendances (simulation).
5. **Virtualisation** – essayer une ISO dans QEMU/KVM (web noVNC, fenêtre WSLg ou VNC), installer sur un disque virtuel puis démarrer sur ce disque.
6. **ISO** – profil Standard/Léger, options, **Créer l'ISO**, **Tester le démarrage (QEMU)**.

Un dossier de sortie contient : `ULB_<famille>_1.iso`, `SHA256SUMS`, `build_report.txt`
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
