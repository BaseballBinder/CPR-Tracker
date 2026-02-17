from app.services.csv_import_service import parse_provider_csv, validate_provider_csv

def test_parse_valid_csv():
    csv_text = "Name,Certification\nJohn Smith,ACP\nJane Doe,PCP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 2
    assert rows[0] == {"name": "John Smith", "certification": "ACP"}

def test_parse_csv_case_insensitive_headers():
    csv_text = "name,CERTIFICATION\nAlice,ACP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"

def test_parse_csv_strips_whitespace():
    csv_text = "Name , Certification \n  Bob  ,  PCP  \n"
    rows = parse_provider_csv(csv_text)
    assert rows[0] == {"name": "Bob", "certification": "PCP"}

def test_validate_missing_headers():
    csv_text = "FirstName,LastName\nJohn,Smith\n"
    errors = validate_provider_csv(csv_text)
    assert len(errors) > 0
    assert "Name" in errors[0]

def test_validate_empty_csv():
    errors = validate_provider_csv("")
    assert len(errors) > 0

def test_parse_csv_skips_empty_rows():
    csv_text = "Name,Certification\nJohn,ACP\n\n\nJane,PCP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 2
