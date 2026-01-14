from flask import Flask, render_template, request, redirect, url_for, jsonify
from pathlib import Path
import csv
import json
import secrets
from werkzeug.utils import secure_filename

app = Flask(__name__)

C0 = 3e8  # m/s
FREQ_OPTIONS_GHZ = [1.8, 2.2, 2.3, 2.4, 3.3]  # sesuai PDF
UPLOAD_DIR = Path("static/uploads")
ALLOWED_IMAGE = {".jpg", ".jpeg", ".png"}
ALLOWED_DATA = {".csv"}

def calc(f_ghz: float, er: float, h_mm: float, wo: float = 3.0):
    """
    Mengikuti ringkasan rumus pada PDF:
    - a = 2c / (3 f sqrt(er))
    - ws = ls = 1.5 a
    - λ0 = c / f
    - εeff = (er+1)/2 + (er-1)/2 * (1/sqrt(1 + 12*h/W))
      ketentuan Wo = 3 -> W/h = Wo => W = Wo*h
    - λg = c / (f*sqrt(εeff))
    - lf = λg / 2
    """
    f_hz = f_ghz * 1e9
    h_m = h_mm / 1000.0
    w_m = wo * h_m  # W = (W/h)*h

    eps_eff = (er + 1) / 2 + (er - 1) / 2 * (1 / ((1 + 12 * (h_m / w_m)) ** 0.5))
    lambda0_m = C0 / f_hz
    lambda_g_m = C0 / (f_hz * (eps_eff ** 0.5))

    a_m = (2 * C0) / (3 * f_hz * (er ** 0.5))
    ws_m = 1.5 * a_m
    ls_m = 1.5 * a_m
    lf_m = lambda_g_m / 2

    return {
        "f_ghz": f_ghz,
        "er": er,
        "h_mm": h_mm,
        "wo": wo,
        "eps_eff": eps_eff,
        "a_mm": a_m * 1000,
        "ws_mm": ws_m * 1000,
        "ls_mm": ls_m * 1000,
        "lambda0_mm": lambda0_m * 1000,
        "lambda_g_mm": lambda_g_m * 1000,
        "lf_mm": lf_m * 1000,
    }

def key_freq(f_ghz: float) -> str:
    # 1.8 -> "1_8"
    return str(f_ghz).replace(".", "_")

def get_default_form():
    return {
        "freq": 2.4,
        "substrat": "FR-4",
        "h": 1.6,
        "er": 4.4,
        "z0": "50 OHM",
        "wo": 3.0
    }

def parse_csv_data(file_stream):
    text = file_stream.read().decode("utf-8-sig").splitlines()
    if not text:
        return None, "CSV kosong."

    sample = text[0]
    has_header = any(ch.isalpha() for ch in sample)

    data = []
    if has_header:
        reader = csv.DictReader(text)
        for row in reader:
            if len(data) >= 1200:
                break
            x = None
            y = None
            for key in row.keys():
                k = key.lower()
                if x is None and ("freq" in k or "f" == k):
                    try:
                        x = float(row[key])
                    except (ValueError, TypeError):
                        pass
                if y is None and ("s11" in k or "mag" in k or "db" in k):
                    try:
                        y = float(row[key])
                    except (ValueError, TypeError):
                        pass
            if x is None or y is None:
                continue
            data.append((x, y))
    else:
        reader = csv.reader(text)
        for row in reader:
            if len(data) >= 1200:
                break
            if len(row) < 2:
                continue
            try:
                x = float(row[0])
                y = float(row[1])
            except ValueError:
                continue
            data.append((x, y))

    if not data:
        return None, "CSV tidak dikenali. Pastikan ada kolom frekuensi dan S11/magnitudo."
    return data, None

@app.route("/", methods=["GET", "POST"])
def landing():
    if request.method == "POST":
        return redirect(url_for("calculator"))
    return render_template("landing.html")

@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    form = get_default_form()

    hasil = None

    if request.method == "POST":
        try:
            freq = float(request.form.get("freq", form["freq"]))
            er = float(request.form.get("er", form["er"]))
            h = float(request.form.get("h", form["h"]))
            wo = float(request.form.get("wo", form["wo"]))
        except (TypeError, ValueError):
            freq = form["freq"]
            er = form["er"]
            h = form["h"]
            wo = form["wo"]

        if freq in FREQ_OPTIONS_GHZ:
            hasil = calc(freq, er, h, wo)
            form.update({"freq": freq, "er": er, "h": h, "wo": wo})

    # gambar C dan D ikut frekuensi
    k = key_freq(form["freq"])
    img_c = f"img/top_{k}.png"     # kotak C (top view)
    img_d = f"img/view_{k}.png"    # kotak D (3D / pola radiasi / dll)

    return render_template(
        "index.html",
        freq_options=FREQ_OPTIONS_GHZ,
        form=form,
        hasil=hasil,
        img_c=img_c,
        img_d=img_d,
        cst_result=None
    )

@app.route("/api/calculator", methods=["POST"])
def calculator_api():
    form = get_default_form()
    try:
        freq = float(request.form.get("freq", form["freq"]))
        er = float(request.form.get("er", form["er"]))
        h = float(request.form.get("h", form["h"]))
        wo = float(request.form.get("wo", form["wo"]))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Input tidak valid."}), 400

    if freq not in FREQ_OPTIONS_GHZ:
        return jsonify({"ok": False, "message": "Frekuensi tidak tersedia."}), 400

    hasil = calc(freq, er, h, wo)
    k = key_freq(freq)
    return jsonify({
        "ok": True,
        "hasil": hasil,
        "img_c": url_for("static", filename=f"img/top_{k}.png"),
        "img_d": url_for("static", filename=f"img/view_{k}.png")
    })

@app.route("/cst", methods=["POST"])
def cst_upload():
    form = get_default_form()
    hasil = None
    cst_result = {"message": "Tidak ada file yang diunggah."}

    file = request.files.get("cst_file")
    display_mode = request.form.get("display_mode", "image")
    if not file or not file.filename:
        cst_result = {"message": "Silakan pilih file CST terlebih dulu."}
    else:
        suffix = Path(file.filename).suffix.lower()
        if suffix in ALLOWED_IMAGE:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = secure_filename(file.filename)
            token = secrets.token_hex(6)
            filename = f"{token}_{safe_name}"
            file_path = UPLOAD_DIR / filename
            file.save(file_path)
            cst_result = {
                "image_url": url_for("static", filename=f"uploads/{filename}"),
                "display_mode": display_mode
            }
        elif suffix in ALLOWED_DATA:
            data, error = parse_csv_data(file.stream)
            if error:
                cst_result = {"message": error, "display_mode": display_mode}
            else:
                labels = [d[0] for d in data]
                values = [d[1] for d in data]
                cst_result = {
                    "csv_labels": json.dumps(labels),
                    "csv_values": json.dumps(values),
                    "display_mode": display_mode
                }
        else:
            cst_result = {"message": "Format file belum didukung. Gunakan .jpg/.png atau .csv."}

    k = key_freq(form["freq"])
    img_c = f"img/top_{k}.png"
    img_d = f"img/view_{k}.png"

    return render_template(
        "index.html",
        freq_options=FREQ_OPTIONS_GHZ,
        form=form,
        hasil=hasil,
        img_c=img_c,
        img_d=img_d,
        cst_result=cst_result
    )

@app.route("/api/cst", methods=["POST"])
def cst_upload_api():
    file = request.files.get("cst_file")
    display_mode = request.form.get("display_mode", "image")
    if not file or not file.filename:
        return jsonify({"ok": False, "message": "Silakan pilih file CST terlebih dulu."}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix in ALLOWED_IMAGE:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(file.filename)
        token = secrets.token_hex(6)
        filename = f"{token}_{safe_name}"
        file_path = UPLOAD_DIR / filename
        file.save(file_path)
        return jsonify({
            "ok": True,
            "display_mode": display_mode,
            "image_url": url_for("static", filename=f"uploads/{filename}")
        })

    if suffix in ALLOWED_DATA:
        data, error = parse_csv_data(file.stream)
        if error:
            return jsonify({"ok": False, "message": error}), 400
        labels = [d[0] for d in data]
        values = [d[1] for d in data]
        return jsonify({
            "ok": True,
            "display_mode": display_mode,
            "csv_labels": labels,
            "csv_values": values
        })

    return jsonify({"ok": False, "message": "Format file belum didukung. Gunakan .jpg/.png atau .csv."}), 400

if __name__ == "__main__":
    app.run(debug=True)
