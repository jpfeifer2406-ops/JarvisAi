from jarvis.permissions import (
    CRITICAL,
    EXECUTE,
    PermissionBroker,
    approval_intent,
    risk_for_tool,
)


def test_risk_classification_is_fail_closed():
    assert risk_for_tool("web_search") == "READ"
    assert risk_for_tool("create_document") == "PREPARE"
    assert risk_for_tool("open_app") == EXECUTE
    assert risk_for_tool("power_command") == CRITICAL
    assert risk_for_tool("brand_new_tool") == CRITICAL


def test_execute_requires_explicit_phrase_not_bare_yes():
    assert approval_intent("ja", EXECUTE) is None
    assert approval_intent("Aktion freigeben", EXECUTE) == "approve"
    assert approval_intent("Aktion abbrechen", EXECUTE) == "cancel"


def test_critical_requires_strong_confirmation():
    assert approval_intent("Aktion freigeben", CRITICAL) is None
    assert approval_intent("Kritische Aktion bestätigen", CRITICAL) == "approve"


def test_broker_consumes_confirmed_action():
    broker = PermissionBroker(ttl_seconds=120)
    staged = broker.stage("open_app", {"name": "spotify"})
    decision, pending = broker.decide("Aktion freigeben")
    assert decision == "approve"
    assert pending == staged
    assert broker.get() is None
