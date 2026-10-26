from ulb.progress import BuildProgress, describe, format_duration


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def tick(self, seconds):
        self.now += seconds


DEBIAN = (
    ["== Construction (Debian) ==", "P: Executing auto/config script."]
    + ["I: Retrieving libc6 2.41-1", "I: Validating libc6 2.41-1",
       "I: Unpacking libc6", "I: Configuring base-files",
       "I: Base system installed successfully."]
    + ["Reading package lists...", "Need to get 480 MB of archives.",
       "0 upgraded, 4 newly installed, 0 to remove"]
    + ["Get:%d http://deb.debian.org/debian trixie/main amd64 xorriso"
       % n for n in range(1, 5)]
    + ["Unpacking xorriso (1.5) ...", "Unpacking squashfs-tools (4.6) ...",
       "Setting up xorriso (1.5) ...", "Setting up squashfs-tools (4.6) ..."]
)


def run(tracker, lines, clock=None, step=1):
    seen = []

    for line in lines:
        tracker.feed(line)

        if clock:
            clock.tick(step)

        seen.append(tracker.fraction())

    return seen


def test_package_names_do_not_trigger_later_stages():
    clock = Clock()
    tracker = BuildProgress("Debian", clock=clock)
    run(tracker, DEBIAN, clock)
    # xorriso / squashfs-tools cités par apt : on reste dans l'installation
    assert tracker.stage_name() == "Installation des paquets"
    assert 0.40 < tracker.fraction() < 0.50


def test_progress_is_monotonic_and_reaches_the_end():
    clock = Clock()
    tracker = BuildProgress("Debian", clock=clock)
    seen = run(tracker, DEBIAN, clock)
    seen += run(tracker, [
        "Parallel mksquashfs: Using 4 processors",
        "Creating 4.0 filesystem on filesystem.squashfs",
        "xorriso 1.5.6 : RockRidge filesystem manipulator",
        "Writing to 'stdio:binary.hybrid.iso' completed successfully.",
        "== Copie vers Windows : ULB.iso ==",
        "Copie de l'ISO : 50 %",
        "== Terminé =="
    ], clock)

    assert seen == sorted(seen)
    assert tracker.stage_name() == "Terminé"
    assert tracker.fraction() == 1.0
    assert tracker.eta() == 0.0


def test_eta_uses_elapsed_time_once_progress_is_measurable():
    clock = Clock()
    tracker = BuildProgress("Debian", clock=clock)
    run(tracker, DEBIAN, clock, step=10)
    eta = tracker.eta()
    assert eta is not None and eta > 0
    percent, text = describe(tracker)
    assert percent == int(tracker.fraction() * 100)
    assert "Installation des paquets" in text and "estimation" in text


def test_without_history_or_counters_only_elapsed_time_is_shown():
    clock = Clock()
    tracker = BuildProgress("Fedora", clock=clock)
    tracker.feed("Running anaconda")
    clock.tick(75)
    assert tracker.eta() is None
    assert "écoulé" in describe(tracker)[1]


def test_history_drives_a_silent_stage():
    clock = Clock()
    history = {
        "total": 100,
        "stages": {
            "Construction (livemedia-creator)": 95.0,
            "Copie vers Windows": 5.0
        }
    }
    tracker = BuildProgress("Fedora", history, clock=clock)
    tracker.feed("INFO: Running anaconda")
    clock.tick(47.5)
    assert 0.4 < tracker.fraction() < 0.55
    assert 40 < tracker.eta() < 60


def test_summary_feeds_the_next_estimate():
    clock = Clock()
    tracker = BuildProgress("Arch Linux", clock=clock)
    steps = [
        "(1/2) checking keys in keyring",
        "(1/2) installing base",
        "[mkarchiso] INFO: Customizing airootfs / mkinitcpio",
        "[mkarchiso] INFO: Creating SquashFS image",
        "[mkarchiso] INFO: Creating ISO image... xorriso",
        "== Copie vers Windows : x.iso ==",
        "== Terminé =="
    ]

    for line in steps:
        tracker.feed(line)
        clock.tick(10)

    summary = tracker.summary()
    assert summary["total"] == 70.0
    assert set(summary["stages"]) == {s.name for s in tracker.stages}

    again = BuildProgress("Arch Linux", summary, clock=clock)
    assert again.weights[0] == 20.0


def test_pacman_counter_weights_installation():
    clock = Clock()
    tracker = BuildProgress("Arch Linux", clock=clock)
    tracker.feed(":: Synchronizing package databases...")
    tracker.feed("(100/200) installing foo")
    assert abs(tracker._inner() - (0.25 + 0.75 * 0.5)) < 1e-9


def test_format_duration():
    assert format_duration(40) == "40 s"
    assert format_duration(600) == "10 min"
    assert format_duration(5400 + 60) == "1 h 31 min"
