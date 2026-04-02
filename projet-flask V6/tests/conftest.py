import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from app import app, db, Task


# ── DataFrame fictif qui simule un fichier Excel ──
def make_fake_df():
    return pd.DataFrame({
        "Années": ["2018", "2019", "2020", "2021", "2022"],
        "2018":   [100, 200, 300, 400, 500],
        "2019":   [110, 210, 310, 410, 510],
        "2020":   [120, 220, 320, 420, 520],
    })


@pytest.fixture
def client():
    """Client de test Flask avec base SQLite en mémoire."""
    app.config["TESTING"]                = True
    app.config["WTF_CSRF_ENABLED"]       = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SECRET_KEY"]             = "test-secret-key"

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client_with_task(client):
    """Client avec une tâche pré-insérée en base."""
    with app.app_context():
        task = Task(name="Commentaire de test", graph_id="pib_2018")
        db.session.add(task)
        db.session.commit()
    return client


@pytest.fixture
def mock_excel():
    """Patch pd.read_excel pour éviter les fichiers Excel réels."""
    with patch("app.pd.read_excel", return_value=make_fake_df()):
        with patch("os.path.exists", return_value=True):
            yield