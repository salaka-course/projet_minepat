"""
Tests du projet Flask MINEPAT
Couverture : routes simples, DB, Excel, PDF, commentaires
"""
import json
import pytest
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from unittest.mock import patch, MagicMock
from app import app, db, Task


# ══════════════════════════════════════════════
# 1. ROUTES SIMPLES
# ══════════════════════════════════════════════

class TestRoutesSimples:

    def test_index_status_200(self, client):
        """La page d'accueil doit retourner 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contient_html(self, client):
        """La page d'accueil doit retourner du HTML."""
        response = client.get("/")
        assert b"<!DOCTYPE html>" in response.data or b"<html" in response.data

    def test_about_status_200(self, client):
        """La page about doit retourner 200."""
        response = client.get("/about/")
        assert response.status_code == 200

    def test_route_inexistante_404(self, client):
        """Une route inexistante doit retourner 404."""
        response = client.get("/route-qui-nexiste-pas/")
        assert response.status_code == 404


# ══════════════════════════════════════════════
# 2. MODÈLE TASK — BASE DE DONNÉES
# ══════════════════════════════════════════════

class TestModeleTask:

    def test_creer_task(self, client):
        """Créer une tâche en base doit fonctionner."""
        with app.app_context():
            task = Task(name="Mon commentaire", graph_id="pib_2020")
            db.session.add(task)
            db.session.commit()
            assert task.id is not None

    def test_lire_task(self, client):
        """Lire une tâche depuis la base doit retourner les bonnes valeurs."""
        with app.app_context():
            task = Task(name="Test lecture", graph_id="tofe_2021")
            db.session.add(task)
            db.session.commit()

            result = Task.query.filter_by(name="Test lecture").first()
            assert result is not None
            assert result.graph_id == "tofe_2021"

    def test_supprimer_task(self, client):
        """Supprimer une tâche doit la retirer de la base."""
        with app.app_context():
            task = Task(name="À supprimer", graph_id="bdp_2019")
            db.session.add(task)
            db.session.commit()
            task_id = task.id

            db.session.delete(task)
            db.session.commit()

            assert Task.query.get(task_id) is None

    def test_task_created_at_auto(self, client):
        """Le champ created_at doit être rempli automatiquement."""
        with app.app_context():
            task = Task(name="Test date", graph_id="monnaie_2022")
            db.session.add(task)
            db.session.commit()
            assert task.created_at is not None

    def test_task_name_obligatoire(self, client):
        """Créer une tâche sans nom doit lever une erreur."""
        with app.app_context():
            task = Task(graph_id="test")
            db.session.add(task)
            with pytest.raises(Exception):
                db.session.commit()
            db.session.rollback()


# ══════════════════════════════════════════════
# 3. COMMENTAIRES — add_comment / delete_comment
# ══════════════════════════════════════════════

class TestCommentaires:

    def test_add_comment_redirect(self, client, mock_excel):
        """Ajouter un commentaire doit rediriger."""
        response = client.post(
            "/add_comment/pib_nominal/",
            data={
                "name": "Bon résultat",
                "graph_id": "pib_2020",
                "page": "1",
                "selected_categories": [],
            },
        )
        assert response.status_code in [302, 200]

    def test_add_comment_persiste_en_base(self, client, mock_excel):
        """Un commentaire ajouté doit être enregistré en base."""
        client.post(
            "/add_comment/pib_nominal/",
            data={
                "name": "Commentaire persisté",
                "graph_id": "pib_2021",
                "page": "1",
            },
        )
        with app.app_context():
            task = Task.query.filter_by(name="Commentaire persisté").first()
            assert task is not None
            assert task.graph_id == "pib_2021"

    def test_delete_comment_inexistant_404(self, client):
        """Supprimer un commentaire inexistant doit retourner 404."""
        response = client.post("/delete_comment/pib_nominal/9999/")
        assert response.status_code == 404

    def test_delete_comment_supprime_de_la_base(self, client_with_task, mock_excel):
        """Supprimer un commentaire doit le retirer de la base."""
        with app.app_context():
            task = Task.query.first()
            task_id = task.id

        response = client_with_task.post(
            f"/delete_comment/pib_nominal/{task_id}/",
            data={"page": "1"},
        )
        assert response.status_code in [302, 200]

        with app.app_context():
            assert Task.query.get(task_id) is None


# ══════════════════════════════════════════════
# 4. ROUTES VISUALISATION (avec mock Excel)
# ══════════════════════════════════════════════

ROUTES_VISUALISATION = [
    "/pib_nominal/",
    "/pib_a_prix_constant/",
    "/taux_de_croissance/",
    "/bdp/",
    "/bdp_ratio/",
    "/tofe/",
    "/tofe_ratio/",
    "/monnaie/",
    "/monnaie_ratio/",
    "/dette_interieure/",
    "/dette_exterieure/",
    "/prix_deflateur_sectoriel/",
    "/prix_petrole_et_gaz/",
    "/prix_prix_des_emplois/",
    "/pib_offre_pib_nominal/",
    "/pib_offre_taux_de_croissance/",
]


class TestRoutesVisualisation:

    @pytest.mark.parametrize("route", ROUTES_VISUALISATION)
    def test_route_get_200(self, client, mock_excel, route):
        """Chaque route de visualisation doit retourner 200 en GET."""
        response = client.get(route)
        assert response.status_code == 200, f"Échec sur {route} : {response.status_code}"

    @pytest.mark.parametrize("route", ROUTES_VISUALISATION)
    def test_route_post_200(self, client, mock_excel, route):
        """Chaque route de visualisation doit accepter un POST."""
        response = client.post(route, data={
            "chart_type": "bar",
            "selected_categories": ["2018", "2019"],
            "page": "1",
        })
        assert response.status_code in [200, 302], f"Échec POST sur {route}"

    def test_pagination_page_2(self, client, mock_excel):
        """La pagination doit fonctionner sur la page 2."""
        response = client.get("/pib_nominal/?page=2")
        assert response.status_code == 200

    def test_filtre_categories(self, client, mock_excel):
        """Le filtre par catégories doit être accepté."""
        response = client.post("/pib_nominal/", data={
            "selected_categories": ["2018"],
            "chart_type": "line",
        })
        assert response.status_code == 200

    def test_chart_type_line(self, client, mock_excel):
        """Le type de graphique 'line' doit être accepté."""
        response = client.post("/pib_nominal/", data={"chart_type": "line"})
        assert response.status_code == 200

    def test_chart_type_bar(self, client, mock_excel):
        """Le type de graphique 'bar' doit être accepté."""
        response = client.post("/pib_nominal/", data={"chart_type": "bar"})
        assert response.status_code == 200

    def test_chart_type_both(self, client, mock_excel):
        """Le type de graphique 'both' doit être accepté."""
        response = client.post("/pib_nominal/", data={"chart_type": "both"})
        assert response.status_code == 200


# ══════════════════════════════════════════════
# 5. TÉLÉCHARGEMENT EXCEL
# ══════════════════════════════════════════════

class TestTelechargerExcel:

    TEMPLATES_VALIDES = [
        "pib_nominal",
        "pib_a_prix_constant",
        "taux_de_croissance",
        "bdp",
        "tofe",
        "monnaie",
        "dette_interieure",
        "dette_exterieure",
    ]

    @pytest.mark.parametrize("template", TEMPLATES_VALIDES)
    def test_telecharger_excel_200(self, client, mock_excel, template):
        """Télécharger un fichier Excel valide doit retourner 200."""
        response = client.get(f"/telecharger_excel/{template}/")
        assert response.status_code == 200

    def test_telecharger_excel_content_type(self, client, mock_excel):
        """La réponse doit être de type Excel."""
        response = client.get("/telecharger_excel/pib_nominal/")
        assert response.status_code == 200
        content_type = response.content_type
        assert "spreadsheet" in content_type or "octet-stream" in content_type

    def test_telecharger_excel_template_invalide_404(self, client):
        """Un template inexistant doit retourner 404."""
        response = client.get("/telecharger_excel/template_inexistant/")
        assert response.status_code == 404

    def test_telecharger_excel_avec_filtre(self, client, mock_excel):
        """Téléchargement avec filtre de catégories doit fonctionner."""
        response = client.get(
            "/telecharger_excel/pib_nominal/?categories=2018&categories=2019"
        )
        assert response.status_code == 200


# ══════════════════════════════════════════════
# 6. GÉNÉRATION PDF
# ══════════════════════════════════════════════

class TestGeneratePdf:

    def _payload_valide(self):
        return {
            "images": [
                {
                    "graph_id": "pib_2020",
                    "image_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                    "comments": ["Tendance à la hausse", "Résultat positif"],
                }
            ]
        }

    def test_generate_pdf_status_200(self, client):
        """La génération PDF avec données valides doit retourner 200."""
        with patch("app.HTML") as mock_html:
            mock_html_instance = MagicMock()
            mock_html.return_value = mock_html_instance

            with patch("app.send_file") as mock_send:
                mock_send.return_value = app.response_class(
                    response=b"%PDF-fake",
                    status=200,
                    mimetype="application/pdf",
                )
                response = client.post(
                    "/generate_report_pdf_canvas/",
                    data=json.dumps(self._payload_valide()),
                    content_type="application/json",
                )
                assert response.status_code == 200

    def test_generate_pdf_sans_donnees_400(self, client):
        """Une requête sans corps JSON doit retourner 400."""
        response = client.post(
            "/generate_report_pdf_canvas/",
            data="",
            content_type="application/json",
        )
        assert response.status_code in [400, 500]

    def test_generate_pdf_images_vides_400(self, client):
        """Un payload avec images vides doit retourner 400."""
        response = client.post(
            "/generate_report_pdf_canvas/",
            data=json.dumps({"images": []}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_generate_pdf_json_invalide_400(self, client):
        """Un JSON malformé doit retourner 400."""
        response = client.post(
            "/generate_report_pdf_canvas/",
            data="pas du json",
            content_type="application/json",
        )
        assert response.status_code in [400, 500]


# ══════════════════════════════════════════════
# 7. FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════

class TestFonctionsUtilitaires:

    def test_load_data_retourne_dataframe(self):
        """load_data doit retourner un DataFrame pandas."""
        from app import load_data
        fake_df = pd.DataFrame({
            "Années": ["2018", "2019", None],
            "val": [1, 2, 3],
        })
        with patch("app.pd.read_excel", return_value=fake_df):
            result = load_data("fake_path.xlsx")
            assert isinstance(result, pd.DataFrame)

    def test_load_data_supprime_lignes_vides(self):
        """load_data doit supprimer les lignes où Années est NaN."""
        from app import load_data
        fake_df = pd.DataFrame({
            "Années": ["2018", None, "2020"],
            "val": [1, 2, 3],
        })
        with patch("app.pd.read_excel", return_value=fake_df):
            result = load_data("fake_path.xlsx")
            assert result["Années"].isna().sum() == 0

    def test_generate_graphs_retourne_liste(self):
        """generate_graphs doit retourner une liste de graphiques."""
        from app import generate_graphs
        fake_df = pd.DataFrame({
            "Années": ["2018", "2019", "2020"],
            "2018": [100, 200, 300],
            "2019": [110, 210, 310],
        })
        graphs, total_pages = generate_graphs(fake_df, [], 1, "both")
        assert isinstance(graphs, list)
        assert total_pages >= 1

    def test_generate_graphs_filtre_categories(self):
        """generate_graphs doit filtrer selon les catégories sélectionnées."""
        from app import generate_graphs
        fake_df = pd.DataFrame({
            "Années": ["2018", "2019", "2020"],
            "val1": [1, 2, 3],
            "val2": [4, 5, 6],
        })
        graphs, _ = generate_graphs(fake_df, ["2018"], 1, "bar")
        assert len(graphs) == 1

    def test_generate_graphs_pagination(self):
        """generate_graphs doit paginer correctement."""
        from app import generate_graphs
        fake_df = pd.DataFrame({
            "Années": [str(i) for i in range(12)],
            "val": list(range(12)),
        })
        _, total_pages = generate_graphs(fake_df, [], 1, "both", per_page=5)
        assert total_pages == 3