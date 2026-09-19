from pathlib import Path

import jarvis.workshop as workshop


def test_txt_create_read_and_revise(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "_WORKSPACE", tmp_path)

    created = workshop.create_document("Test Dokument", "Hallo Captain.", "txt")
    assert "Test Dokument.txt" in created
    assert workshop.read_document("Test Dokument.txt") == "Hallo Captain."

    revised = workshop.revise_document("Test Dokument.txt", "Captain", "Commander")
    assert "Test Dokument-revised.txt" in revised
    assert workshop.read_document("Test Dokument-revised.txt") == "Hallo Commander."


def test_create_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "_WORKSPACE", tmp_path)

    workshop.create_document("Bericht", "eins", "txt")
    workshop.create_document("Bericht", "zwei", "txt")

    assert (tmp_path / "Bericht.txt").read_text(encoding="utf-8") == "eins"
    assert (tmp_path / "Bericht-2.txt").read_text(encoding="utf-8") == "zwei"


def test_path_escape_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "_WORKSPACE", tmp_path)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    try:
        workshop.read_document("../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("workspace path escape must be rejected")


def test_docx_and_pdf_are_real_readable_files(tmp_path, monkeypatch):
    monkeypatch.setattr(workshop, "_WORKSPACE", tmp_path)

    workshop.create_document("DOCX Test", "Hallo Captain.", "docx")
    workshop.create_document("PDF Test", "Hallo Captain.", "pdf")

    assert (tmp_path / "DOCX Test.docx").stat().st_size > 0
    assert (tmp_path / "PDF Test.pdf").stat().st_size > 0
    assert "Hallo Captain." in workshop.read_document("DOCX Test.docx")
    assert "Hallo Captain." in workshop.read_document("PDF Test.pdf")
