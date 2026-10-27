# Journal des versions

## 2.0.27
- **Cases à cocher invisibles** (Wi-Fi, Bluetooth, Impression, Firmware, Flathub, Dépôts tiers, Bureau vanille) : sous Windows, une fois la feuille de style appliquée, la case n'avait ni cadre ni coche tant qu'elle n'était pas dans un cadre (seul « Avancé » s'affichait bien). Les cases ont maintenant un indicateur explicite : cadre aux couleurs du thème, remplissage accent et coche blanche quand elles sont cochées, état grisé distinct. Thème clair et sombre ; rendu vérifié en capture hors écran, pas sur votre Windows.

## 2.0.26
- **Fedora : la construction va maintenant jusqu'à Anaconda, mais l'échec final est opaque.** Journal reçu : clonage (f43 en repli) OK, 1839 RPM téléchargés (2,18 Gio), puis « An error occurred during the transaction: The transaction process has ended with errors » ; le « No such file or directory: '/usr/sbin/load_policy' » qui suit n'est qu'un symptôme de sortie, pas la cause.
- La cause réelle (paquet, scriptlet, conflit) est dans les journaux d'Anaconda/dnf5, pas dans `lmc.log`. En cas d'échec, la construction affiche maintenant un **« Diagnostic Fedora »** : lignes d'erreur de `packaging.log`, `program.log`, `anaconda.log`, `dnf5.log`… puis la fin de `lmc.log`. La queue de sortie conservée dans le message d'échec passe de 1800 à 6000 caractères.
- Outil de construction Fedora ajouté : `load_policy` (paquet `policycoreutils`), pour supprimer l'erreur de sortie secondaire. À réinstaller via « Installer les outils ».
- **Non résolu** : la cause de la transaction échouée est inconnue tant que le diagnostic n'a pas été lu. Hypothèse la plus probable : kickstart f43 utilisé avec `--releasever 44` (paquets renommés ou retirés). Voie propre : kiwi (non implémentée).

## 2.0.25
- **Destination et nom de l'ISO au choix** (onglet ISO, groupe « Destination de l'ISO »). Un dossier (bouton Parcourir) et un nom de fichier, mémorisés d'un lancement à l'autre. Dossier vide : la boîte de dialogue habituelle s'ouvre à chaque construction. Nom vide : nom automatique `ULB_<distribution>_<version>_<date>.iso`.
- Valable pour Debian, Fedora, Arch Linux et pour le remaster Gentoo/Slackware. Le nom est nettoyé (caractères interdits sous Windows remplacés par `_`, noms réservés comme CON évités, `.iso` ajouté) ; si plusieurs ISO sont produites, `_1`, `_2`… sont ajoutés ; un fichier existant n'est **jamais écrasé** (`-2`, `-3`…). Un dossier mémorisé qui n'existe plus provoque un avertissement.
- Limite : la destination est un dossier Windows ; le renommage ne change pas le volume interne de l'ISO.

## 2.0.24
- **Option « Bureau vanille »** (onglet Système, à droite du choix du bureau). Elle remplace le méta-paquet habituel (`gnome-core`, `kde-plasma-desktop`, `xfce4`…) par la session, le gestionnaire de connexion, le gestionnaire de fichiers et les réglages seulement, sans applications ni réglages ajoutés par la distribution. Pour Debian, `--apt-recommends false` est aussi appliqué.
- Disponible pour GNOME, KDE Plasma et Xfce sur Debian, Fedora et Arch Linux ; désactivée pour Budgie (déjà en paquets unitaires), « Aucun », Gentoo et Slackware. L'info-bulle et une ligne d'aide indiquent les paquets exacts.
- **Non vérifié sur une vraie construction** : les noms de paquets sont ceux que je connais ; lancez « Analyser les paquets ». Un paquet de marque de la distribution peut rester s'il est exigé par une dépendance. Un GNOME vanille n'inclut pas de terminal.

## 2.0.23
- **Fedora : « dumb http transport does not support shallow capabilities »**. Le choix de la branche (f43 en repli) fonctionnait, mais pagure.io répond en HTTP « dumb », qui n'accepte pas `git clone --depth 1`. Le clonage retente maintenant **sans `--depth`** (clone complet, plus long) quand le clone superficiel est refusé, après avoir supprimé le dossier partiel.
- Testé avec un faux `git` qui refuse `--depth` ; non testé contre le vrai pagure.io.

## 2.0.22
- **Fedora 44 : « Remote branch f44 not found »** (construction échouée dès le clonage des kickstarts). Cause, vérifiée dans la discussion Fedora « Custom live iso F44? » : les images officielles de Fedora 44 ne sont plus construites avec des kickstarts mais avec **kiwi** ; le dépôt `fedora-kickstarts` n'a donc pas de branche `f44`.
- La construction liste les branches `fNN` du dépôt et choisit **la branche exacte si elle existe, sinon la plus récente inférieure** (tri numérique), en affichant un avertissement explicite. Réseau en panne ou aucune branche : message distinct et clair au lieu d'un « clonage impossible » générique.
- La confirmation de construction prévient pour Fedora 44 et plus que le repli n'est pas validé.
- **Non résolu : ce repli n'est pas une garantie.** Un kickstart de la version précédente avec `--releasever 44` peut échouer plus loin (paquets renommés) ou produire une image incomplète. La voie officielle pour Fedora 44 est kiwi (profil `Workstation-Live` des descriptions kiwi de Fedora) : non implémentée, à faire dans une version dédiée.

## 2.0.21
- **Fedora : l'analyse des paquets n'était jamais validée, donc « Créer l'ISO » restait bloqué** (« L'analyse des paquets doit être validée avant la construction »). Cause : `dnf5 --assumeno` calcule la transaction puis répond « non » à la confirmation, ce qui se termine par le **code 1** (« Operation aborted by the user »). L'application exigeait le code 0. Le verdict regarde maintenant le contenu : transaction calculée (tableau lu ou « Transaction Summary ») sans message d'échec ; code 0 ou 1 acceptés pour Fedora.
- Les vrais échecs restent refusés et expliqués : `Problem`, `Failed to resolve`, `No match for argument`, `Cannot find a package`, code autre que 0/1, ou aucune transaction calculée. Le message d'avertissement et le journal indiquent désormais la raison.
- Debian, Arch et Gentoo : comportement inchangé (code 0 exigé ; Debian refuse aussi une erreur `E:`).
- Non vérifié sur un vrai Fedora 44 : le format exact des messages d'échec de dnf5 est celui que je connais ; si un cas réel est refusé à tort, la sortie native indique la ligne en cause.

## 2.0.20
- **Test du gestionnaire précis** (Configuration > Outils et dépôts > « Tester le gestionnaire ») : le test vérifie chaque outil réellement utilisé par l'application pour la famille (Debian : apt-get et apt-cache ; Fedora : dnf5 ; Arch : pacman ; Gentoo : emerge ; Slackware : slackpkg), affiche son chemin et sa version, et conclut par un message clair « Gestionnaire opérationnel : <outil> — <famille> (WSL « nom »)  » ou « Gestionnaire incomplet : <outil manquant> ».
- En cas d'échec : indice utile (dnf4 présent mais dnf5 attendu sous Fedora ; apt incomplet sous Debian), erreur WSL le cas échéant, et conseil (« Installer les outils »).
- Le test ne contacte pas les dépôts ; « Actualiser les dépôts » sert à cela.
- Testé en exécutant la vraie commande avec de faux outils pour les 5 familles (présents, absents, partiels). Non testé avec de vrais Debian, Fedora, Arch, Gentoo, Slackware.

## 2.0.19
- L'onglet **WSL2** devient **Configuration** (les messages qui y renvoient sont mis à jour).
- Sous-onglet « Outils et dépôts » : « Environnement WSL » devient **« Environnement »**.
- Retrait des boutons **« Ajouter Flathub »** et **« Dépôts tiers Fedora »** : ces options se règlent dans Système (case cochée = incluse dans l'ISO, décochée = absente). Les fonctions restent dans le code et ses tests.
- **Gentoo et Slackware** : le sélecteur Environnement propose « <famille> — dépôt internet (pas un WSL) », visible seulement quand l'une de ces deux familles est choisie. « Actualiser les dépôts » (Configuration, et onglet Applications) retélécharge `PACKAGES.TXT` (Slackware) ou sonde Repology (Gentoo, interrogé en direct) ; vérifier ou installer des outils n'a pas de sens pour ces entrées et le dit.
- Non vérifié en réel : adresses et formats des catalogues (réseau restreint ici).

## 2.0.18
- **Nouvel onglet Ventoy** (avant WSL2) : télécharge la dernière version officielle de Ventoy (empreinte SHA-256 vérifiée), liste les clés USB (les disques système et de démarrage sont exclus, le disque 0 aussi), installe ou met à jour Ventoy par `Ventoy2Disk.exe VTOYCLI` (style MBR/GPT, Secure Boot, espace réservé, système de fichiers exFAT/NTFS/FAT32 ; autorisation UAC demandée par Windows), puis copie des ISO sans jamais écraser l'existant. La clé est revérifiée juste avant l'écriture.
- **Persistance Debian** : fichier ext4 « persistence » créé dans un WSL Debian, copié sur la clé et déclaré dans `ventoy/ventoy.json` (fichier existant fusionné, refusé s'il est invalide).
- **Groupe « Avancé »** (onglet Système, décoché par défaut) : langue, clavier, fuseau horaire, nom d'hôte, utilisateur et mot de passe du live, persistance, chiffrement LUKS, système de fichiers (ext4/btrfs/xfs) et instantanés, Secure Boot (paquets signés), pilotes NVIDIA et codecs, miroir et proxy, et pour Arch Linux seulement : dépôts pacman et paquets AUR. Un tableau indique, pour la famille choisie, ce qui est Appliqué, Partiel, Non applicable ou Désactivé.
- Le mot de passe n'est jamais enregistré (ni réglages, ni projet, ni rapport) ; seule son empreinte SHA-512 est placée dans l'image.
- L'onglet Système défile pour rester utilisable avec le groupe Avancé.
- Non vérifié en réel : aucune de ces options n'a été éprouvée sur une vraie construction ni sur une vraie clé (voir README).

## 2.0.17
- **Gentoo et Slackware : association « Dépôt internet (sans WSL) »** (onglet WSL2, Associations). Choisie automatiquement quand aucun WSL de la famille n'existe ; un WSL Gentoo/Slackware reste prioritaire s'il est détecté. Indicateur « ● Internet ».
- **Recherche d'applications sans WSL** : Slackware lit `PACKAGES.TXT` du miroir officiel (version 15.0 ou current choisie dans l'onglet Distribution) ; Gentoo interroge l'API Repology (dépôt `gentoo`). Résultats : nom, version, description.
- En mode Internet, l'analyse des dépendances et la vérification des outils restent indisponibles (elles demandent le gestionnaire de paquets réel) ; un message l'explique.
- Non vérifié : les adresses et formats n'ont pas pu être testés en réel (réseau restreint ici) ; les analyseurs sont testés sur des échantillons conformes à la documentation.

## 2.0.16
- **Onglet Système** : la case « Dépôts tiers non libres (Fedora) » n'apparaît plus que si la famille Fedora est choisie (elle était seulement grisée avant). Elle n'est de toute façon jamais appliquée aux autres familles.
- Le bouton « Dépôts tiers Fedora » de l'onglet WSL2 reste disponible : il agit sur un WSL Fedora, quelle que soit la famille de l'ISO.

## 2.0.15
- **Ordre des onglets** : Distribution, Système, Applications, Vérification, **ISO**, puis **Virtualisation** et **WSL2** à l'extrême droite. Le parcours de création d'ISO n'est plus coupé par les onglets d'outils (test en VM, gestion WSL2). Le bouton « Continuer » de Vérification mène désormais à ISO.

## 2.0.14
- **Fedora : la recherche de paquets ne trouvait rien** (firefox, vlc : « 0 résultats », seule la ligne « Repositories loaded » s'affichait). L'analyseur n'attendait que le format dnf4 (`nom.arch : résumé`). La recherche interroge maintenant `dnf5 repoquery` avec un format maîtrisé (nom|version|résumé, version affichée), complété par `dnf5 search -q` ; l'analyseur accepte les deux présentations et ignore les lignes de progression.
- Si rien n'est trouvé sous Fedora, le message explique que vlc et les codecs viennent de RPM Fusion (option « Dépôts tiers Fedora »).
- Non vérifié sur un vrai Fedora 44 : le format exact de dnf5 n'a pas pu être observé ici.

## 2.0.13
- **Thèmes** : Système, Clair, Sombre (sélecteur « Thème » en haut à droite, choix mémorisé). « Système » suit le réglage de Windows et change à chaud quand il change.
- Toutes les couleurs viennent de `ulb/theme.py` (palettes sombre et claire, contrastes vérifiés par un test) ; les styles en dur ont été remplacés par des rôles, y compris les cartes de distribution, les états colorés et les indicateurs WSL.
- Le logo Slackware (gris clair) est assombri sur le thème clair pour rester visible.
- Qt 6.8 ou plus : les barres de titre et boîtes de dialogue natives suivent aussi le choix.

## 2.0.12
- **Messages cohérents par distribution** : la confirmation « Actualiser les dépôts » citait Arch Linux pour tous les WSL. Elle décrit maintenant l'effet réel de la commande de la famille (Debian : index seulement ; Fedora : métadonnées ; Arch : mise à niveau complète ; Gentoo : synchronisation ; Slackware : liste). Le statut de vérification nomme la distribution et le WSL. Un test vérifie qu'aucun de ces textes ne cite une autre famille.
- **Onglet Vérification** : bandeau de contexte (famille, version, gestionnaire, installateur, WSL) et quatre sous-onglets pleine hauteur : Outils, Paquets cibles, Résolution, Sortie native. Chaque titre rappelle la famille et le gestionnaire.
- **Résolution lisible** : la sortie de la simulation (dnf5, apt, pacman, emerge) est lue et affichée en colonnes Paquet / Version / Dépôt / Taille / Rôle (demandé, dépendance, dépendance faible) ; la sortie brute reste disponible en police fixe.
- **Origine des paquets précise** : Système de base, Bureau X, Audio X, Chargeur GRUB, Option X, Application choisie, Noyau (avant : tout était « Bureau / option / application »).
- **Plus de résultats mélangés** : changer de famille efface les résultats de la précédente ; changer un réglage les marque « obsolète, à relancer ». Colonnes ajustées au contenu, dernière colonne toujours visible.
- Correctif : le bouton « Créer l'ISO personnalisée » restait grisé pour Gentoo et Slackware.

## 2.0.11
- **Gentoo et Slackware : ISO officielle puis remaster**, sans WSL dédié. Téléchargement depuis les miroirs officiels (reprise, vérification SHA256/SHA512, refus si l'empreinte diffère) ou import d'une ISO locale ; personnalisation avec xorriso dans n'importe quel WSL Debian/Fedora/Arch (`ulb/sources.py`, `ulb/remaster.py`, `ulb/ui_remaster.py`).
- Gentoo : reprise de l'amorçage de l'ISO d'origine (`-boot_image any replay`) ; Slackware : arbre extrait puis commande officielle du README d'isolinux (BIOS + UEFI), séries retirables (`kde`, `y`…).
- **Contrôle d'amorçage** après création : les entrées BIOS/UEFI doivent être identiques à l'ISO d'origine (Gentoo) ou présentes (Slackware), sinon la création échoue.
- Onglet Virtualisation utilisable pour Gentoo et Slackware (essai de l'ISO remasterisée).
- Tests avec le vrai xorriso (installé en CI). Un test a révélé que `-rm_r` doit être terminé par `--`.

## 2.0.10
- **Poste neuf** : `lancer.bat` (Python via winget si absent, environnement `.venv`, PySide6, contrôle WSL2, lancement) et pré-contrôle intégré à `main.py` (`ulb/preflight.py`, bibliothèque standard uniquement).
- `py main.py --check` : rapport Python ≥ 3.10, PySide6, fichiers de l'application, WSL2 (présence, version par défaut, distributions), virtualisation BIOS/UEFI, espace disque, avec la commande de correction pour chaque point.
- PySide6 manquant : installation automatique (`pip`, `--user` hors environnement virtuel), sauf avec `--no-install`. Les points bloquants arrêtent le démarrage avec un message clair ; les autres sont affichés puis l'application démarre.

## 2.0.9
- **Dossier de destination déjà utilisé** : l'ISO peut être créée dans un dossier qui contient d'autres ISO ou fichiers. Nom daté (`ULB_Debian_trixie_20261026-173000.iso`), jamais d'écrasement (suffixe `-2`, `-3` si le nom existe), `SHA256SUMS` complété sans effacer les anciennes lignes, rapport `build_report_<date-heure>.txt`.
- Le dossier doit toujours exister ; l'espace libre Windows est vérifié avant la construction.

## 2.0.8
- **Correctif Debian : ISO qui démarre sans interface (« Authentication failure »)**. Cause trouvée dans le code de `live-config` : le composant `0030-user-setup` ne crée l'utilisateur live que si le paquet `user-setup` est installé, or ce paquet (comme `sudo`, `locales`, `keyboard-configuration`, `live-tools`) n'est qu'une *recommandation* de `live-config`. Sans utilisateur, la connexion automatique échoue et l'écran de connexion n'a personne à connecter.
- Paquets indispensables ajoutés explicitement à l'image Debian (`ulb/precheck.py`) : session live, serveur graphique (Xorg, libinput, pilotes) et greeter `lightdm-gtk-greeter`.
- **Contrôle après construction** : chaque paquet demandé est vérifié dans le chroot de live-build ; la construction échoue (« ISO INCOMPLÈTE, paquets absents… ») au lieu de livrer une ISO inutilisable.
- La chaîne d'installation affiche les nouvelles lignes (session live, serveur graphique, contrôle après construction).

## 2.0.7
- **Virtualisation, affichage** : la machine est lancée en arrière-plan et l'application vérifie que l'affichage répond (« Machine démarrée, affichage prêt ») avant d'ouvrir l'adresse web. Si le paquet noVNC est absent, il est téléchargé depuis GitHub (git) au lieu d'échouer.
- Mode « VNC (client externe) » : le journal rappelle qu'il faut un client VNC (adresse `localhost:5900`) et conseille le mode Web sinon. Mode WSLg : avertissement si aucun affichage n'est détecté.
- Messages PipeWire inoffensifs (`pw.conf ... client.conf`) masqués dans le journal.

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
