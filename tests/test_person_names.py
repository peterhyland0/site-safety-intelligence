from ssi.matching.candidates import is_person_core


def test_recognises_peoples_names():
    assert is_person_core("JUAN GARCIA")
    assert is_person_core("JOSE A HERNANDEZ")
    assert is_person_core("HERNANDEZ JOSE")  # surname first


def test_leaves_company_names_alone():
    assert not is_person_core("BRASFIELD GORRIE")
    assert not is_person_core("JOSE")  # one word: not enough to say it's a person
    assert not is_person_core("JR 84")
    assert not is_person_core("AUSTIN BRIDGE ROAD")  # place names that are also first names are not listed
