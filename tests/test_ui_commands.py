from jarvis.ui_commands import detect_ui_command, detect_overlay_command


def test_open_input_commands():
    assert detect_ui_command("Computer, Eingabe öffnen.") is True
    assert detect_ui_command("Bitte Chat öffnen") is True
    assert detect_ui_command("open input") is True


def test_close_input_commands():
    assert detect_ui_command("Eingabe schließen") is False
    assert detect_ui_command("Computer, Chat schliessen.") is False
    assert detect_ui_command("close chat") is False


def test_unrelated_text_is_not_ui_command():
    assert detect_ui_command("Zeig mir die Nachrichten für Deutschland") is None
    assert detect_ui_command("Öffne Spotify") is None


def test_settings_overlay_commands():
    assert detect_overlay_command("Computer, Einstellungen öffnen.") == ("settings", True)
    assert detect_overlay_command("Konsole schließen") == ("settings", False)


def test_workshop_overlay_commands():
    assert detect_overlay_command("Werkstatt öffnen") == ("workshop", True)
    assert detect_overlay_command("Creative-Werkstatt schließen") == ("workshop", False)


def test_call_overlay_commands():
    assert detect_overlay_command("Anrufmodus öffnen") == ("call", True)
    assert detect_overlay_command("Call schließen") == ("call", False)
