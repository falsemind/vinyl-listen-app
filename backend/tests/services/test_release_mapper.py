from app.services.release_mapper import extract_release_artists, map_discogs_to_internal


def test_map_discogs_to_internal_normalizes_release_metadata() -> None:
    payload = {
        "id": 555123,
        "artists_sort": "Boards of Canada",
        "title": "Music Has The Right To Children",
        "year": "1998",
        "labels": [
            {"name": "Warp Records", "catno": "WARPLP55"},
            {"name": "Skam"},
        ],
        "identifiers": [
            {"type": "Matrix / Runout", "value": "etching"},
            {"type": "Barcode", "value": " 5021603065515 "},
        ],
        "genres": ["Electronic", "Electronic", " Ambient "],
        "styles": ["IDM", "", "Downtempo", "IDM"],
        "images": [{"uri": "https://img.discogs.com/cover.jpg"}],
    }

    result = map_discogs_to_internal(payload)

    assert result.discogs_release_id == 555123
    assert result.artist == "Boards of Canada"
    assert result.title == "Music Has The Right To Children"
    assert result.year == 1998
    assert result.label == "Warp Records"
    assert result.catalog_number == "WARPLP55"
    assert result.barcode == "5021603065515"
    assert result.genres == ["Electronic", "Ambient"]
    assert result.styles == ["IDM", "Downtempo"]
    assert result.cover_image_url == "https://img.discogs.com/cover.jpg"


def test_map_discogs_to_internal_falls_back_to_artist_list_and_thumb() -> None:
    payload = {
        "id": 2468,
        "artists": [{"name": "Basic Channel"}, {"name": "Maurizio"}],
        "title": "Phylyps Trak",
        "thumb": "https://img.discogs.com/thumb.jpg",
    }

    result = map_discogs_to_internal(payload)

    assert result.artist == "Basic Channel, Maurizio"
    assert result.cover_image_url == "https://img.discogs.com/thumb.jpg"
    assert result.genres is None
    assert result.styles is None


def test_map_discogs_to_internal_trims_discogs_artist_number_suffix() -> None:
    payload = {
        "id": 1357,
        "artists_sort": "Karma (54), Mutt (2)",
        "title": "The Warning",
    }

    result = map_discogs_to_internal(payload)

    assert result.artist == "Karma, Mutt"


def test_map_discogs_to_internal_keeps_numbers_inside_artist_names() -> None:
    payload = {
        "id": 24680,
        "artists_sort": "Studio 54 Ensemble (7)",
        "title": "Night Drive",
    }

    result = map_discogs_to_internal(payload)

    assert result.artist == "Studio 54 Ensemble"


def test_map_discogs_to_internal_trims_discogs_artist_suffix_in_self_released_label() -> None:
    payload = {
        "id": 9753,
        "artists_sort": "Karma (54)",
        "title": "Dub Plate",
        "labels": [{"name": "Not On Label (Karma (54) Self-Released)", "catno": "KARMADUBZ001"}],
    }

    result = map_discogs_to_internal(payload)

    assert result.label == "Not On Label (Karma Self-Released)"
    assert result.catalog_number == "KARMADUBZ001"


def test_map_discogs_to_internal_keeps_clean_self_released_label() -> None:
    payload = {
        "id": 8642,
        "artists_sort": "Om Unit",
        "title": "Acid Dub Studies",
        "labels": [{"name": "Not On Label (Om Unit Self-Released)", "catno": "ADS002"}],
    }

    result = map_discogs_to_internal(payload)

    assert result.label == "Not On Label (Om Unit Self-Released)"


def test_extract_release_artists_returns_discogs_artist_ids() -> None:
    artists = extract_release_artists(
        {
            "artists": [
                {"id": 194, "name": "Boards Of Canada"},
                {"id": "355", "name": "Karma (54)"},
                {"id": 194, "name": "Boards Of Canada"},
                {"name": "Missing ID"},
            ]
        }
    )

    assert [(artist.name, artist.discogs_artist_id) for artist in artists] == [
        ("Boards Of Canada", 194),
        ("Karma", 355),
    ]
