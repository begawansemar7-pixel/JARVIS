from core.introduction import CREATOR, employee_title, identity_line, startup_introduction_clause


def test_creator_is_ko_henri():
    assert CREATOR == "Ko Henri"


def test_employee_title_uses_user_name():
    assert employee_title("Henri") == "AI Employee Henri"
    assert employee_title("  ") == "AI Employee"


def test_startup_clause_introduces_assistant_owner_and_creator():
    clause = startup_introduction_clause("JARVIS", "Henri")
    assert "JARVIS, AI Employee Henri, created by Ko Henri" in clause
    assert "exactly as written" in clause


def test_identity_line_without_user_name_stays_grammatical():
    line = identity_line("JARVIS")
    assert "the AI Employee of the user, created by Ko Henri" in line
    assert "AI Employee Henri" not in line
