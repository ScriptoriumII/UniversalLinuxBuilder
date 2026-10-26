from .constants import DISPLAY_MANAGERS, INSTALLERS


def installer_checklist(family, desktop, packages, live_packages):
    """
    Liste ce que l'application fournit réellement pour obtenir
    une ISO installable. Rien ici ne remplace un test de démarrage.
    """

    names = {
        name.split("/")[-1]
        for name in list(packages) + list(live_packages)
    }

    rows = []

    # Installateur graphique

    if family == "Debian":
        rows.append((
            "Installateur Calamares",
            "Inclus",
            "calamares et calamares-settings-debian "
            "sont ajoutés à l'image live."
        ))

        rows.append((
            "Configuration de Calamares",
            "À valider",
            "Fournie par calamares-settings-debian ; "
            "jamais testée par cette application."
        ))

    elif family == "Arch Linux":
        rows.append((
            "Installateur Calamares",
            "Absent",
            "Calamares n'est pas dans les dépôts officiels "
            "(AUR) : un dépôt local est nécessaire."
        ))

        rows.append((
            "Configuration de Calamares",
            "Absent",
            "Aucun settings.conf ni branding n'est généré."
        ))

    elif family == "Fedora":
        rows.append((
            "Installateur Anaconda",
            "Inclus",
            "anaconda et anaconda-live sont ajoutés à l'image live."
        ))

        rows.append((
            "Configuration d'Anaconda",
            "À valider",
            "Fournie par le kickstart officiel du bureau choisi ; "
            "jamais testée par cette application."
        ))

        rows.append((
            "Environnement de construction",
            "À valider",
            "livemedia-creator --no-virt exécute Anaconda dans le WSL : "
            "utilise un WSL Fedora dédié, de la même version."
        ))

    else:
        rows.append((
            "Installateur " + INSTALLERS[family],
            "Non implémenté",
            "La construction d'ISO n'existe que pour "
            "Debian et Arch Linux."
        ))

    # GRUB dans le système installé

    if desktop is None:
        desktop = "Aucun"

    grub = [name for name in names if name.startswith(
        ("grub", "efibootmgr")
    )]

    if grub:
        rows.append((
            "GRUB dans le système installé",
            "Inclus",
            ", ".join(sorted(grub))
        ))

    else:
        rows.append((
            "GRUB dans le système installé",
            "Absent",
            "Aucun paquet GRUB sélectionné (Système > "
            "Bootloader doit valoir GRUB)."
        ))

    # Ecran de connexion

    if desktop != "Aucun":
        if names & DISPLAY_MANAGERS:
            rows.append((
                "Gestionnaire de connexion",
                "Présent",
                ", ".join(sorted(names & DISPLAY_MANAGERS))
            ))

        elif family == "Fedora":
            rows.append((
                "Gestionnaire de connexion",
                "À valider",
                "Fourni par le kickstart Fedora du bureau choisi."
            ))

        else:
            rows.append((
                "Gestionnaire de connexion",
                "Absent",
                "Le bureau démarrerait sans écran de connexion."
            ))

        if family == "Debian":
            activation = (
                "Automatique",
                "Activé par la postinstallation du paquet."
            )

        elif family == "Fedora":
            activation = (
                "À valider",
                "Géré par le kickstart Fedora officiel."
            )

        else:
            activation = (
                "À configurer",
                "Le service doit être activé "
                "(systemctl enable) : non fait ici."
            )

        rows.append((
            "Activation du gestionnaire de connexion",
            activation[0],
            activation[1]
        ))

    rows.append((
        "Démarrage sous Ventoy / UEFI / BIOS",
        "Non testé",
        "À valider en machine virtuelle puis sur le PC."
    ))

    if "flatpak" in names:
        if family in ("Debian", "Fedora", "Arch Linux"):
            rows.append((
                "Flathub (Flatpak)",
                "À valider",
                "flatpak est installé ; le fichier du dépôt Flathub est "
                "déposé dans /etc/flatpak/remotes.d à la construction "
                "(jamais testé par cette application)."
            ))

        else:
            rows.append((
                "Flathub (Flatpak)",
                "À configurer",
                "flatpak est dans la liste ; ajoute Flathub "
                "après l'installation : flatpak remote-add "
                "--if-not-exists flathub "
                "https://dl.flathub.org/repo/flathub.flatpakrepo"
            ))

    return rows
