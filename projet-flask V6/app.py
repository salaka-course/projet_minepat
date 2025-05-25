from flask import Flask, render_template, request, send_file,make_response, redirect, url_for, jsonify
import os
import pandas as pd
import plotly.express as px
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from jinja2 import Template
from io import BytesIO
import uuid
from weasyprint import HTML
import tempfile
import plotly.io as pio
import xlsxwriter


app = Flask(__name__)
app.config['DATA_FOLDER'] = 'data'
app.config['IMAGE_FOLDER'] = 'static/exports'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    graph_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def load_data(file_path):
    df = pd.read_excel(file_path, sheet_name='Feuil1' or 'Sheet1')
    df = df.dropna(subset=['Années'], how='all')
    df = df.dropna(axis=1, how='all')
    return df


def prepare_visualization(file_path, request):
    df = load_data(file_path)
    categories = df['Années'].dropna().unique().tolist()
    page = int(request.values.get("page", 1))
    selected_categories = request.form.getlist("selected_categories") if request.method == "POST" else request.args.getlist("selected_categories")
    chart_type = request.form.get("chart_type", "both")
    graphs, total_pages = generate_graphs(df, selected_categories, page, chart_type)
    return {
        "categories": categories,
        "graphs": graphs,
        "current_page": page,
        "total_pages": total_pages,
        "file_name": os.path.basename(file_path),
        "directory_name": os.path.basename(os.path.dirname(file_path)),
        "selected_categories": selected_categories,
        "chart_type": chart_type,
        "file_path": file_path,
        "page": page  
    }


def generate_graphs(df, selected_categories, page, chart_type, per_page=5):
    filtered_df = df[df['Années'].isin(selected_categories)] if selected_categories else df
    total_rows = len(filtered_df)
    start = (page - 1) * per_page
    end = start + per_page

    paginated_df = filtered_df.iloc[start:end]
    total_pages = (total_rows // per_page) + (1 if total_rows % per_page > 0 else 0)

    graphs = []
    for _, row in paginated_df.iterrows():
        category_name = row['Années']
        values = row[1:]
        graph_id = category_name.replace(" ", "_").lower()

        graph_html = f"<h5>{category_name}</h5>"

        if chart_type in ["line", "both"]:
            fig_line = px.line(x=df.columns[1:], y=values,labels={'x': 'Années', 'y': 'Valeurs'})
            graph_html += f'<div class="plotly-graph-container">{fig_line.to_html(full_html=False, include_plotlyjs="cdn")}</div>'

        if chart_type in ["bar", "both"]:
            fig_bar = px.bar(x=df.columns[1:], y=values,labels={'x': 'Années', 'y': 'Valeurs'})
            graph_html += f'<div class="plotly-graph-container">{fig_bar.to_html(full_html=False, include_plotlyjs="cdn")}</div>'

        graphs.append({"html": graph_html, "graph_id": graph_id})

    return graphs, total_pages


@app.route("/telecharger_excel/<template_name>/")
def telecharger_excel(template_name):
    templates_to_files = {
        "pib_nominal": "data/SECTEURS REELS/PIB DEMANDE/Ventilation du PIB emplois à prix courants (en milliards de FCFA).xlsx",
        "pib_a_prix_constant": "data/SECTEURS REELS/PIB DEMANDE/Ventilation du PIB emploi à prix constant (Base 100=N-1).xlsx",
        "taux_de_croissance": "data/SECTEURS REELS/PIB DEMANDE/Taux de croissance réelle du PIB emplois (en %).xlsx",
        "pib_offre_pib_nominal": "data/SECTEURS REELS/PIB OFFRE/Ventilation du PIB emplois à prix courants (en milliards de FCFA).xlsx",
        "pib_offre_prix_constant": "data/SECTEURS REELS/PIB OFFRE/Ventilation du PIB emploi à prix constant (Base 100=N-1).xlsx",
        "pib_offre_taux_de_croissance": "data/SECTEURS REELS/PIB OFFRE/Taux de croissance réelle du PIB emplois (en %).xlsx",
        "deflateur_sectoriel": "data/SECTEURS REELS/PRIX/Ventilation des indices de prix par secteurs d’activités (base 100 = 2016).xlsx",
        "petrole_et_gaz": "data/SECTEURS REELS/PRIX/Prévisions du secteur pétrolier et gazier.xlsx",
        "prix_des_emplois": "data/SECTEURS REELS/PRIX/Indices de prix des emplois.xlsx",
        "bdp": "data/AUTRES/Balance des Paiements (en milliards de FCFA).xlsx",
        "bdp_ratio": "data/AUTRES/Balance des Paiements en % du PIB.xlsx",
        "tofe": "data/AUTRES/Tableau des Opérations Financières de l'Etat (en milliards de FCFA).xlsx",
        "tofe_ratio": "data/AUTRES/TOFE en ratio au PIB.xlsx",
        "monnaie": "data/AUTRES/Situation monétaire (en milliards de FCFA).xlsx",
        "monnaie_ratio": "data/AUTRES/Situation Monétaire en ratio au PIB.xlsx",
        "dette_interieure": "data/AUTRES/Dette intérieure (en milliards fcfa).xlsx",
        "dette_exterieure": "data/AUTRES/Dette extérieure (en milliards fcfa).xlsx"
    }

    file_path = templates_to_files.get(template_name)
    if not file_path or not os.path.exists(file_path):
        return "Fichier introuvable", 404

    selected_categories = request.args.getlist("categories")

    df = pd.read_excel(file_path, sheet_name="Feuil1")
    df = df.dropna(subset=['Années'], how='all').dropna(axis=1, how='all')

    if selected_categories:
        df = df[df['Années'].isin(selected_categories)]

    # Convertir en Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Données")
    output.seek(0)

    filename = f"{template_name}_donnees.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)


@app.route("/generate_report_pdf_canvas/", methods=["POST"])
def generate_report_pdf_canvas():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Aucune donnée JSON reçue"}), 400

        images = data.get("images", [])
        if not images:
            return jsonify({"error": "Aucune image reçue"}), 400

        html_content = """
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; padding: 30px; }
                img { max-width: 700px; width: 100%; height: auto; margin-bottom: 10px; border: 1px solid #ccc; }
                h2 { font-size: 18px; margin-top: 30px; }
                ul { list-style-type: disc; padding-left: 40px; }
                li { margin-bottom: 5px; }
            </style>
        </head>
        <body>
            <h1 style="text-align:center;">Rapport des Graphiques</h1>
        """

        for img in images:
            graph_id = img.get("graph_id", "graphique")
            image_data = img.get("image_data", "")
            comments = img.get("comments", [])

            if not image_data:
                continue

            html_content += f"""
            <h2>{graph_id.replace('_', ' ').title()}</h2>
            <img src="{image_data}" alt="graphique" />
            """

            if comments:
                html_content += "<h3>Commentaires :</h3><ul>"
                for comment in comments:
                    html_content += f"<li>{comment}</li>"
                html_content += "</ul>"

        html_content += "</body></html>"

        # Création PDF
        temp_dir = tempfile.mkdtemp()
        pdf_path = os.path.join(temp_dir, f"rapport_{uuid.uuid4().hex}.pdf")

        HTML(string=html_content).write_pdf(pdf_path)

        return send_file(pdf_path, as_attachment=True, download_name="rapport_graphiques.pdf")
    
    except Exception as e:
        print(f"Erreur pendant la génération du PDF : {e}")
        return jsonify({"error": f"Erreur serveur : {str(e)}"}), 500






@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add_comment/<template_name>/", methods=["POST"])
def add_comment(template_name):
    # if request.form.get("username") != "admin":
    #     return redirect(url_for(template_name))
    name = request.form['name']
    graph_id = request.form['graph_id']
    page = request.form.get("page", 1)
    selected_categories = request.form.getlist("selected_categories")
    new_task = Task(name=name, graph_id=graph_id)
    db.session.add(new_task)
    db.session.commit()
    return redirect(url_for(template_name, page=page, selected_categories=selected_categories))

@app.route("/delete_comment/<template_name>/<int:id>/", methods=["POST"])
def delete_comment(template_name, id):
    # if request.form.get("username") != "admin":
    #     return redirect(url_for(template_name))
    task = Task.query.get_or_404(id)
    page = request.form.get("page", 1)
    selected_categories = request.form.getlist("selected_categories")
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for(template_name, page=page, selected_categories=selected_categories))



@app.route("/pib_nominal/", methods=["GET", "POST"])
def pib_nominal():
    result = prepare_visualization("data/SECTEURS REELS/PIB DEMANDE/Ventilation du PIB emplois à prix courants (en milliards de FCFA).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("PIB_NOMINAL.html", tasks=tasks,template_name="pib_nominal",**result)


@app.route("/pib_a_prix_constant/", methods=["GET", "POST"])
def pib_a_prix_constant():
    result = prepare_visualization("data/SECTEURS REELS/PIB DEMANDE/Ventilation du PIB emploi à prix constant (Base 100=N-1).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("PIB_A_PRIX_CONSTANT.html", tasks=tasks,template_name="pib_a_prix_constant",**result)


@app.route("/taux_de_croissance/", methods=["GET", "POST"])
def taux_de_croissance():
    result = prepare_visualization("data/SECTEURS REELS/PIB DEMANDE/Taux de croissance réelle du PIB emplois (en %).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("TAUX_DE_CROISSANCE.html", tasks=tasks, **result)


@app.route("/pib_offre_pib_nominal/", methods=["GET", "POST"])
def pib_offre_pib_nominal():
    result = prepare_visualization("data/SECTEURS REELS/PIB OFFRE/Ventilation du PIB emplois à prix courants (en milliards de FCFA).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("pib_offre_pib_nominal.html", tasks=tasks, template_name="pib_offre_pib_nominal", **result)
   


@app.route("/pib_offre_prix_constant/", methods=["GET", "POST"])
def pib_offre_prix_constant():
    result = prepare_visualization("data/SECTEURS REELS/PIB OFFRE/Ventilation du PIB emploi à prix constant (Base 100=N-1).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("pib_offre_pib_prix_constant", tasks=tasks, template_name="pib_offre_prix_constant", **result)


@app.route("/pib_offre_taux_de_croissance/", methods=["GET", "POST"])
def pib_offre_taux_de_croissance():
    result = prepare_visualization("data/SECTEURS REELS/PIB OFFRE/Taux de croissance réelle du PIB emplois (en %).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("pib_offre_taux_de_croissance.html", tasks=tasks, **result)

@app.route("/prix_deflateur_sectoriel/", methods=["GET", "POST"])
def deflateur_sectoriel():
    result = prepare_visualization("data/SECTEURS REELS/PRIX/Ventilation des indices de prix par secteurs d’activités (base 100 = 2016).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("DEFLATEUR_SECTORIEL.html", tasks=tasks, template_name="deflateur_sectoriel", **result)
    


@app.route("/prix_petrole_et_gaz/", methods=["GET", "POST"])
def petrole_et_gaz():
    result = prepare_visualization("data/SECTEURS REELS/PRIX/Prévisions du secteur pétrolier et gazier.xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("PETROLE_ET_GAZ.html", tasks=tasks, template_name="petrole_et_gaz", **result)
    


@app.route("/prix_prix_des_emplois/", methods=["GET", "POST"])
def prix_des_emplois():
    result = prepare_visualization("data/SECTEURS REELS/PRIX/Indices de prix des emplois.xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("PRIX_DES_EMPLOIS.html", tasks=tasks, template_name="prix_des_emplois", **result)
    
    
@app.route("/bdp/", methods=["GET", "POST"])
def bdp():
    result = prepare_visualization("data/AUTRES/Balance des Paiements (en milliards de FCFA).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("BDP.html", tasks=tasks, template_name="bdp", **result)

@app.route("/bdp_ratio/", methods=["GET", "POST"])
def bdp_ratio():
    result = prepare_visualization("data/AUTRES/Balance des Paiements en % du PIB.xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("BDP_RATIO.html", tasks=tasks, template_name="bdp_ratio", **result)

@app.route("/tofe/", methods=["GET", "POST"])
def tofe():
    result = prepare_visualization("data/AUTRES/Tableau des Opérations Financières de l'Etat (en milliards de FCFA).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("TOFE.html", tasks=tasks, template_name="tofe", **result)

@app.route("/tofe_ratio/", methods=["GET", "POST"])
def tofe_ratio():
    result = prepare_visualization("data/AUTRES/TOFE en ratio au PIB.xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("TOFE_RATIO.html", tasks=tasks, template_name="tofe_ratio", **result)

@app.route("/monnaie/", methods=["GET", "POST"])
def monnaie():
    result = prepare_visualization("data/AUTRES/Situation monétaire (en milliards de FCFA).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("MONNAIE.html", tasks=tasks, template_name="monnaie", **result)

@app.route("/monnaie_ratio/", methods=["GET", "POST"])
def monnaie_ratio():
    result = prepare_visualization("data/AUTRES/Situation Monétaire en ratio au PIB.xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("MONNAIE_RATIO.html", tasks=tasks, template_name="monnaie_ratio", **result)


@app.route("/dette_interieure/", methods=["GET", "POST"])
def dette_interieure():
    result = prepare_visualization("data/AUTRES/Dette intérieure (en milliards fcfa).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("DETTE_INTERIEURE.html", tasks=tasks, template_name="dette_interieure", **result)

@app.route("/dette_exterieure/", methods=["GET", "POST"])
def dette_exterieure():
    result = prepare_visualization("data/AUTRES/Dette extérieure (en milliards fcfa).xlsx", request)
    tasks = Task.query.order_by(Task.created_at).all()
    return render_template("DETTE_EXTERIEURE.html", tasks=tasks, template_name="dette_exterieure", **result)





@app.route("/about/")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
