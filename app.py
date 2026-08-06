"""AirOS Log Analyzer — Tarayıcı otomatik açılan başlatıcı."""

import os
import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

from device_fetcher import fetch_logs
from log_parser import parse_log_content

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

EMPTY_STATE = {
    "loaded": False,
    "summary": {"total": 0, "info": 0, "warning": 0, "error": 0, "info_pct": 0, "warning_pct": 0, "error_pct": 0},
    "entries": [],
    "distribution": {"labels": [], "values": [], "percentages": []},
    "timeline": {"labels": [], "all": [], "warnings": [], "errors": []},
    "top_events": [],
    "problems": [],
    "device": {"device": "—", "ip": "—", "version": "—", "uptime": "—"},
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze_upload():
    if "file" not in request.files:
        return jsonify({"error": "Dosya seçilmedi."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Dosya seçilmedi."}), 400

    try:
        content = file.read().decode("utf-8", errors="replace")
    except Exception as e:
        return jsonify({"error": f"Dosya okunamadı: {e}"}), 400

    if not content.strip():
        return jsonify({"error": "Dosya boş."}), 400

    result = parse_log_content(content)
    result["loaded"] = True
    result["device"] = {
        "device": "PowerBeam / Rocket M5",
        "ip": "—",
        "version": "AirOS 8",
        "uptime": "—",
    }
    result["source"] = file.filename
    return jsonify(result)


@app.route("/api/fetch", methods=["POST"])
def analyze_fetch():
    data = request.get_json(silent=True) or {}
    ip = (data.get("ip") or "").strip()
    username = (data.get("username") or "ubnt").strip()
    password = data.get("password") or "ubnt"
    method = data.get("method") or "auto"

    if not ip:
        return jsonify({"error": "IP adresi gerekli."}), 400

    content, error, device_info = fetch_logs(ip, username, password, method)
    if error:
        return jsonify({"error": error}), 400

    result = parse_log_content(content)
    result["loaded"] = True
    result["device"] = device_info
    result["source"] = f"SSH/HTTP — {ip}"
    return jsonify(result)


@app.route("/api/empty")
def empty_state():
    return jsonify(EMPTY_STATE)


def open_browser(port: int) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  AirOS Log Analyzer")
    print(f"  http://127.0.0.1:{port}")
    print(f"  Tarayıcı otomatik açılıyor...\n")

    threading.Timer(1.0, open_browser, args=[port]).start()
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False)
