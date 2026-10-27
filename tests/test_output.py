from ulb.output import check_folder, clean_iso_name, iso_file_name


def test_clean_iso_name():
    assert clean_iso_name("") == ""
    assert clean_iso_name("  ") == ""
    assert clean_iso_name("mon iso") == "mon iso.iso"
    assert clean_iso_name("mon.ISO") == "mon.iso"
    assert clean_iso_name("a/b\\c:d") == "a_b_c_d.iso"
    assert clean_iso_name("CON") == "_CON.iso"
    assert clean_iso_name("...") == ""
    assert len(clean_iso_name("x" * 500)) == 124


def test_iso_file_name():
    assert iso_file_name("", "auto.iso") == "auto.iso"
    assert iso_file_name("perso", "auto.iso") == "perso.iso"
    assert iso_file_name("perso", "auto.iso", 2, 3) == "perso_2.iso"


def test_check_folder(tmp_path):
    assert check_folder("")
    assert check_folder(str(tmp_path / "absent"))
    assert check_folder(str(tmp_path)) == ""
