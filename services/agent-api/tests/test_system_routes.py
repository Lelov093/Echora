from sqlalchemy.sql.elements import TextClause

from app.api.routes import system


def test_db_health_executes_a_sqlalchemy_text_clause(monkeypatch):
    class Session:
        statement = None
        closed = False

        def execute(self, statement):
            self.statement = statement

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(system.companion_service, "get_session", lambda: session)

    response = system.db_health_check()

    assert response["error"] is None
    assert response["data"] == {"status": "ok", "database": "connected"}
    assert isinstance(session.statement, TextClause)
    assert session.closed is True


def test_db_health_closes_the_session_when_the_probe_fails(monkeypatch):
    class Session:
        closed = False

        def execute(self, statement):
            raise RuntimeError("database unavailable")

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(system.companion_service, "get_session", lambda: session)

    response = system.db_health_check()

    assert response["error"]["code"] == "DATABASE_ERROR"
    assert response["error"]["message"] == "database unavailable"
    assert session.closed is True
