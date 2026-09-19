import pytest

pytestmark = pytest.mark.skipif(
    __import__("sys").platform != "win32",
    reason="COMPUTER runtime currently targets Windows and imports msvcrt",
)


def test_session_end_recognizes_ruhemodus_variants():
    from jarvis.main import _is_session_end_command

    assert _is_session_end_command("Ruhemodus")
    assert _is_session_end_command("Computer, Ruhemodus!")
    assert _is_session_end_command("COMPUTER   standby")
    assert not _is_session_end_command("Wie funktioniert der Ruhemodus?")


def test_direct_time_command_normalizes_whitespace():
    from jarvis.main import _direct_system_response

    result = _direct_system_response("  Wie   spät   ist es?  ")
    assert result is not None
    assert "Captain" in result
    assert "Uhr" in result


def test_direct_system_response_ignores_unrelated_text():
    from jarvis.main import _direct_system_response

    assert _direct_system_response("Öffne meine Notizen") is None
