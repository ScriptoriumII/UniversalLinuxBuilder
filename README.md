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

## Gentoo et Slackware : ISO officielle puis remaster

Ces deux familles n'ont **pas de construction** et n'ont pas besoin de leur propre WSL. Dans l'onglet
**ISO**, après avoir choisi Gentoo ou Slackware :

1. **Source** : *Télécharger l'ISO officielle* (miroirs officiels, reprise possible, empreinte SHA256/SHA512
   vérifiée, ISO refusée si elle ne correspond pas) ou *Importer une ISO…* déjà présente sur le disque.
   L'adresse reste modifiable si un miroir change.
2. **WSL d'assemblage** : un WSL Debian, Fedora ou Arch Linux ; bouton *Installer xorriso* si besoin.
3. **Personnaliser** : *Fichiers à ajouter* (le contenu d'un dossier Windows est copié à la racine de l'ISO) ;
   pour Slackware, *Séries à retirer* (`kde`, `y`…) et retrait de `source/` pour gagner de la place.
4. **Créer l'ISO personnalisée** : Gentoo reprend l'amorçage de l'ISO d'origine (`xorriso -boot_image any replay`) ;
   Slackware extrait l'arbre puis régénère l'ISO avec la commande officielle du `isolinux/README.TXT`
   (BIOS + UEFI). Dans les deux cas l'application **vérifie que les entrées d'amorçage sont présentes** et échoue sinon.
5. **Tester** dans l'onglet Virtualisation (disque virtuel), puis démarrer sur ce disque.

Limites : les paquets ne sont pas recompilés ni ajoutés au système installé (ajoute des fichiers, des scripts ou
retire des séries) ; le retrait de séries Slackware n'a pas été validé avec l'installateur `setup`.

Pour **chercher des applications** (onglet Applications) sans WSL Gentoo/Slackware, l'association
« Dépôt internet (sans WSL) » lit le catalogue en ligne : `PACKAGES.TXT` du miroir Slackware, Repology pour Gentoo.
L'analyse des dépendances reste réservée à un vrai WSL.

## Clé USB Ventoy et options avancées

L'onglet **Ventoy** (Windows) : 1) télécharger Ventoy, 2) choisir la clé (liste des disques USB) et installer ou mettre à jour,
3) copier les ISO (et créer la persistance Debian). L'installation **efface la clé** ; Windows demande l'autorisation
administrateur. Options absentes (non documentées en ligne de commande) : alignement 4 Ko, « Effacer Ventoy », nom du volume.

Le groupe **Avancé** (onglet Système) règle langue/clavier/fuseau, nom d'hôte, utilisateur et mot de passe du live,
persistance (Debian), LUKS, système de fichiers et instantanés btrfs, Secure Boot, pilotes NVIDIA/codecs, miroir/proxy et,
pour Arch Linux seulement, dépôts pacman et paquets AUR. Son tableau d'état dit ce qui est réellement appliqué par famille.
Limites : options générées mais **jamais validées** sur une vraie construction ; Secure Boot = paquets signés seulement ;
LUKS non forçable sous Fedora (case dans Anaconda) ; Arch n'a pas d'installateur graphique ; la persistance n'est prévue
que pour Debian ; les paquets ajoutés par Avancé ne passent pas par l'analyse des dépendances.

## Thème

Sélecteur **Thème** en haut à droite : *Système* (suit Windows, y compris en cours d'exécution), *Clair* ou *Sombre*.
Le choix est mémorisé.

## Parcours

1. **Distribution** – famille et version.
2. **Système** – bureau, noyau, audio, GRUB (UEFI ou BIOS) et options.
3. **Applications** – recherche de paquets dans le gestionnaire de l'environnement WSL.
4. **Vérification** – outils, puis analyse des dépendances (simulation).
5. **ISO** – profil Standard/Léger, options, **Créer l'ISO**, **Tester le démarrage (QEMU)**. La barre de construction affiche un pourcentage et une estimation du temps restant (affinée à chaque construction réussie).

Trois onglets d'outils, volontairement à l'extrême droite pour ne pas se mélanger avec la création d'ISO :

6. **Virtualisation** – essayer une ISO dans QEMU/KVM (web noVNC, fenêtre WSLg ou VNC), installer sur un disque virtuel puis démarrer sur ce disque.
7. **Ventoy** – clé USB bootable, copie d'ISO, persistance.
8. **WSL2** – distributions, outils de construction, dépôts.

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
