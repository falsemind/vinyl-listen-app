from app.services.release_mapper import map_discogs_to_internal


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
