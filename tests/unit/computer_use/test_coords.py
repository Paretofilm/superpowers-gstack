from test_smoke import load
coords = load("coords")


def test_denormalize_against_points():
    # SPIKE-verifisert: (450,365) normalisert mot 402x874 pt (iPhone 17 Pro) → "Generelt"-raden
    p = coords.denormalize(450, 365, 402, 874)
    assert round(p.x, 1) == round(450 / 1000 * 402, 1)  # 180.9
    assert round(p.y, 1) == round(365 / 1000 * 874, 1)  # 319.0


def test_denormalize_center():
    p = coords.denormalize(500, 500, 402, 874)
    assert round(p.x, 1) == 201.0
    assert round(p.y, 1) == 437.0


def test_in_safe_area_rejects_status_bar():
    safe = coords.SafeArea(left=0, top=60, right=390, bottom=800)
    assert coords.in_safe_area(coords.Point(200, 400), safe) is True
    assert coords.in_safe_area(coords.Point(200, 30), safe) is False   # i status-bar
    assert coords.in_safe_area(coords.Point(200, 810), safe) is False  # under home-indicator


def test_table_insets_ipad_portrait():
    sa = coords.table_insets("ipad", "portrait", 820.0, 1180.0)
    assert (sa.left, sa.top, sa.right, sa.bottom) == (0, 24, 820.0, 1160.0)


def test_table_insets_landscape_has_side_insets():
    sa = coords.table_insets("iphone_island", "landscape", 852.0, 393.0)
    assert sa.left > 0 and sa.right < 852.0


def test_table_insets_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        coords.table_insets("nosuchdevice", "portrait", 100.0, 100.0)
