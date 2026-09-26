from seed_intel.parsers.pdf_parser import parse_pdf_bytes


def test_pdf_text_extraction():
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "SeedASDAN PDF Project Application Deadline: 2026-06-30")
    data = doc.tobytes()
    result = parse_pdf_bytes(data)
    assert not result.needs_manual_review
    assert "Application Deadline" in result.text
