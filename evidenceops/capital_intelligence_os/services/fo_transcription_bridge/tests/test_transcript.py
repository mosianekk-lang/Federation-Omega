from transcript import Word, format_timestamp, render_srt, render_text, render_vtt, words_to_segments


def test_timestamp_formats():
    assert format_timestamp(3661.234, srt=True) == "01:01:01,234"
    assert format_timestamp(3661.234, srt=False) == "01:01:01.234"


def test_words_group_by_speaker_and_pause():
    words = [
        Word("Good", 0.0, 0.3, "Speaker 1", 0.9),
        Word("morning", 0.31, 0.8, "Speaker 1", 0.8),
        Word("Commissioner", 0.9, 1.4, "Speaker 2", 0.95),
        Word("Yes", 4.0, 4.2, "Speaker 2", 0.7),
    ]
    segments = words_to_segments(words, chunk_index=0, pause_threshold=1.5)
    assert [segment.speaker for segment in segments] == ["Speaker 1", "Speaker 2", "Speaker 2"]
    assert segments[0].text == "Good morning"
    assert round(segments[0].mean_confidence or 0, 2) == 0.85


def test_renderers_include_speaker_and_text():
    segments = words_to_segments(
        [Word("Evidence", 0.0, 0.5, "Speaker 1", None)], chunk_index=0
    )
    assert "[Speaker 1] Evidence" in render_srt(segments)
    assert "<Speaker 1>Evidence" in render_vtt(segments)
    assert "Speaker 1: Evidence" in render_text(segments)
