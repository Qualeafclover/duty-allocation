from app.rules import overlaps


def test_overlapping_ranges():
    assert overlaps(1, 5, 4, 8)


def test_separate_ranges():
    assert not overlaps(1, 3, 5, 8)
