import pytest

from ulb.projects import normalize_project, read_project

ROOT_EXAMPLE = "examples/distribution_legacy.json"


def test_legacy_format():
    project = read_project(ROOT_EXAMPLE)
    assert project["family"] == "Gentoo"
    assert project["options"] == {
        "Wi-Fi": True, "Bluetooth": True, "Impression": True
    }
    assert project["packages"] == []
    assert project["notes"]


def test_nested_and_flat_choices():
    nested = normalize_project(
        {"family": "Debian", "choices": {"desktop": "Xfce"}}
    )
    flat = normalize_project({"family": "Debian", "desktop": "Xfce"})
    assert nested["choices"] == flat["choices"] == {"desktop": "Xfce"}


@pytest.mark.parametrize("data", [[], {}, {"family": "Windows"}])
def test_invalid_projects(data):
    with pytest.raises(ValueError):
        normalize_project(data)


def test_arch_commands_initialise_the_keyring(monkeypatch):
    from ulb import environments

    seen = []
    monkeypatch.setattr(
        environments, "execute",
        lambda env, command, *a, **k: seen.append(command) or ("", "", 0)
    )
    monkeypatch.setattr(
        environments, "check_tools",
        lambda env, family: [("mkarchiso", "archiso", "Absent")]
    )

    environments.update_repositories("arch", "Arch Linux")
    environments.install_tools("arch", "Arch Linux")

    assert all(
        command.startswith("pacman-key --init && pacman-key --populate archlinux")
        for command in seen
    ) and len(seen) == 2


def test_fedora_kickstarts_have_a_git_fallback():
    from ulb.builders import fedora_script
    from ulb.environments import fedora_install_command

    command = fedora_install_command(["fedora-kickstarts", "lorax"])
    assert "--whatprovides '*/fedora-live-base.ks'" in command
    assert "ks=git" in command and "lorax" in command
    assert fedora_install_command(["lorax"]) == "dnf5 -y install lorax"

    script = fedora_script("/var/tmp/x", "44", ["a"], "Xfce")
    assert 'want="f44"' in script
    assert 'git clone --depth 1 --branch "$br"' in script
    assert "pagure.io/fedora-kickstarts" in script


def test_rpm_tool_states_are_parsed(monkeypatch):
    from ulb import environments

    def fake_wsl(env, command, timeout=300, root=False):
        return "\n".join(
            entry[0] + ":OK" for entry in environments.BUILD_TOOLS["Fedora"]
        ), "", 0

    monkeypatch.setattr(environments, "wsl", fake_wsl)
    rows = environments.check_tools("x", "Fedora")
    assert all(state == "Présent" for _, _, state in rows), rows
