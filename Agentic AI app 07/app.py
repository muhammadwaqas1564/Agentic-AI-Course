from flask import Flask, render_template, request, redirect, url_for
from agents.research import fetch_papers
from agents.summarize import summarize_papers

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    topic = request.form.get("topic", "").strip()
    if not topic:
        return redirect(url_for("index"))

    # Agent 1 — Research
    papers = fetch_papers(topic)

    if not papers:
        error = "No papers found. Try a different topic or check your connection."
        return render_template("results.html", topic=topic, papers=[], error=error)

    # Agent 2 — Summarize
    papers = summarize_papers(papers)

    return render_template("results.html", topic=topic, papers=papers, error=None)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
