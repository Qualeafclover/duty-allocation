from app.auth import hash_password, verify_password


def test_correct_password_matches():
    assert verify_password(hash_password("secret"), "secret")


def test_wrong_password_does_not_match():
    assert not verify_password(hash_password("secret"), "wrong")


def test_hash_is_not_the_plain_password():
    assert "secret" not in hash_password("secret")


def test_missing_hash_never_matches():
    assert not verify_password(None, "dummy-password")


def test_broken_hash_does_not_match():
    assert not verify_password("not-a-hash", "secret")
