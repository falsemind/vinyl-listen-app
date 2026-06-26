from app.utils.release_formats import is_likely_digital_release_format


def test_detects_file_based_digital_formats() -> None:
    assert is_likely_digital_release_format(["File", "MP3", "Album"])
    assert is_likely_digital_release_format(["File", "WAV"])
    assert is_likely_digital_release_format("FLAC")


def test_keeps_physical_formats() -> None:
    assert not is_likely_digital_release_format(["Vinyl", "LP"])
    assert not is_likely_digital_release_format(["CD", "Album"])
    assert not is_likely_digital_release_format(["Vinyl", '12"', "File", "MP3"])
