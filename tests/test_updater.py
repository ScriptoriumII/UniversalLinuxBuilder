import io
import subprocess
import zipfile

import pytest

from ulb import updater


def constants_text(version):
    return 'X = 1\nVERSION = "' + version + '"\n'


CHANGELOG = (
    "# Journal\n\n## 2.0.30\n- trois\n\n## 2.0.29\n- deux\n\n"
    "## 2.0.28\n- un\n"
)


def fake_getter(version="2.0.30"):
    def getter(url, timeout=10):
        if url.endswith("constants.py"):
            return constants_text(version).encode()

        if url.endswith("CHANGELOG.md"):
            return CHANGELOG.encode()

        raise RuntimeError("inattendu " + url)

    return getter


def test_versions():
    assert updater.is_newer("2.0.29", "2.0.28")
    assert updater.is_newer("2.1", "2.0.28")
    assert not updater.is_newer("2.0.28", "2.0.28")
    assert not updater.is_newer("2.0.9", "2.0.28")
    assert not updater.is_newer("abc", "2.0.28")


def test_check_update_newer_and_notes():
    info = updater.check_update("2.0.28", fake_getter())
    assert info["newer"] and info["latest"] == "2.0.30"
    assert "2.0.30" in info["notes"] and "2.0.29" in info["notes"]
    assert "2.0.28" not in info["notes"]


def test_check_update_current():
    info = updater.check_update("2.0.30", fake_getter())
    assert not info["newer"] and info["notes"] == ""


def test_check_update_unreadable():
    with pytest.raises(RuntimeError):
        updater.check_update("1.0", lambda url, timeout=10: b"rien")


def make_zip(files):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)

    return buffer.getvalue()


def test_zip_update_replaces_files(tmp_path):
    (tmp_path / "ulb").mkdir()
    (tmp_path / "ulb" / "constants.py").write_text("ancien")
    data = make_zip({
        "repo-main/ulb/constants.py": "nouveau",
        "repo-main/README.md": "lisez-moi",
        "repo-main/.git/config": "ignoré"
    })

    method, message = updater.apply_update(
        tmp_path, lambda url, timeout=10: data, git=""
    )

    assert method == "zip" and "2 fichier" in message
    assert (tmp_path / "ulb" / "constants.py").read_text() == "nouveau"
    assert (tmp_path / "README.md").read_text() == "lisez-moi"
    assert not (tmp_path / ".git").exists()


def test_zip_refuses_path_escape(tmp_path):
    target = tmp_path / "app"
    target.mkdir()
    data = make_zip({"repo-main/../../evil.txt": "x"})

    with pytest.raises(RuntimeError):
        updater.apply_update(
            target, lambda url, timeout=10: data, git=""
        )

    assert not (tmp_path / "evil.txt").exists()


def test_zip_bad_archive(tmp_path):
    with pytest.raises(RuntimeError):
        updater.apply_update(
            tmp_path, lambda url, timeout=10: b"pas un zip", git=""
        )


def test_git_pull_update(tmp_path):
    git = updater.git_executable()

    if not git:
        pytest.skip("git absent")

    def run(*args, cwd):
        subprocess.run(
            [git, "-c", "user.email=a@b", "-c", "user.name=t", *args],
            cwd=cwd, check=True, capture_output=True
        )

    origin = tmp_path / "origin"
    origin.mkdir()
    run("init", "-q", "-b", "main", cwd=origin)
    (origin / "f.txt").write_text("1")
    run("add", ".", cwd=origin)
    run("commit", "-q", "-m", "a", cwd=origin)

    clone = tmp_path / "clone"
    run("clone", "-q", str(origin), str(clone), cwd=tmp_path)

    (origin / "f.txt").write_text("2")
    run("commit", "-q", "-am", "b", cwd=origin)

    method, _ = updater.apply_update(clone, git=git)
    assert method == "git"
    assert (clone / "f.txt").read_text() == "2"


def test_git_pull_conflict_is_reported(tmp_path):
    git = updater.git_executable()

    if not git:
        pytest.skip("git absent")

    (tmp_path / ".git").mkdir()

    with pytest.raises(RuntimeError, match="git pull a échoué"):
        updater.apply_update(tmp_path, git=git)
