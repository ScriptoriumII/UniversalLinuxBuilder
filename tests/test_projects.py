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
