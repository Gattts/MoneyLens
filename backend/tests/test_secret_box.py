from financeiro.services.secret_box import seal, unseal

KEY = "k" * 40


def test_seal_roundtrip_and_wrong_key():
    token = seal("senha-de-teste", KEY)
    assert unseal(token, KEY) == "senha-de-teste"
    assert unseal(token, "x" * 40) is None
    assert "senha-de-teste" not in token


def test_each_seal_uses_a_new_nonce():
    assert seal("a", KEY) != seal("a", KEY)


def test_unseal_garbage_is_none():
    assert unseal("@@@", KEY) is None
    assert unseal("", KEY) is None
    assert unseal(seal("a", KEY)[:-6], KEY) is None
