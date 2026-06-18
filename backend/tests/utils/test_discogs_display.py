from app.utils.discogs_display import (
    clean_discogs_artist_name,
    clean_discogs_label_name,
    clean_discogs_self_released_label,
)


def test_clean_discogs_artist_name_trims_suffix_per_artist() -> None:
    assert clean_discogs_artist_name("Karma (54), Mutt (2)") == "Karma, Mutt"


def test_clean_discogs_artist_name_keeps_numbers_inside_name() -> None:
    assert clean_discogs_artist_name("Studio 54 Ensemble (7)") == "Studio 54 Ensemble"


def test_clean_discogs_self_released_label_trims_nested_artist_suffix() -> None:
    assert clean_discogs_self_released_label("Not On Label (Karma (54) Self-Released)") == (
        "Not On Label (Karma Self-Released)"
    )


def test_clean_discogs_self_released_label_keeps_clean_label() -> None:
    assert clean_discogs_self_released_label("Not On Label (Om Unit Self-Released)") == (
        "Not On Label (Om Unit Self-Released)"
    )


def test_clean_discogs_label_name_trims_discogs_suffix() -> None:
    assert clean_discogs_label_name("System Music (2)") == "System Music"


def test_clean_discogs_label_name_trims_self_released_nested_suffix() -> None:
    assert clean_discogs_label_name("Not On Label (Karma (54) Self-Released)") == ("Not On Label (Karma Self-Released)")
