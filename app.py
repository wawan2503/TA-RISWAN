from flask import Flask, render_template, request, redirect, url_for, jsonify


app = Flask(__name__)

C0 = 3e8  # m/s
FREQ_OPTIONS_GHZ = [1.8, 2.2, 2.3, 2.4, 3.3]  # sesuai PDF
CST_FREQ_DIR = {
    1.8: "1.8",
    2.2: "22",
    2.3: "23",
    2.4: "24",
    3.3: "33",
}


def cst_image_relpath(freq_ghz: float, filename: str) -> str:
    freq_dir = CST_FREQ_DIR.get(freq_ghz)
    if not freq_dir:
        raise ValueError("Frekuensi tidak tersedia.")
    return f"img/gambar cst/{freq_dir}/{filename}"


def cst_image_urls(freq_ghz: float) -> dict:
    return {
        "antena": url_for("static", filename=cst_image_relpath(freq_ghz, "antena.png")),
        "gain": url_for("static", filename=cst_image_relpath(freq_ghz, "gain.png")),
        "pola": url_for("static", filename=cst_image_relpath(freq_ghz, "pola.png")),
        "return_loss": url_for("static", filename=cst_image_relpath(freq_ghz, "RETURN LOSS.png")),
        "vswr": url_for("static", filename=cst_image_relpath(freq_ghz, "VSWR.png")),
    }

def calc(f_ghz: float, er: float, h_mm: float, wo_mm: float = 3.0):
    """
    Rumus (sesuai spesifikasi):
    - a = (2*c) / (3*f*sqrt(er))
    - ws = ls = 1.5 * a
    - lambda0 = c / f
    - eff = (er+1)/2 + (er-1)/2 * ( 1 / sqrt(1 + 12h/W0) )
    - lambda_g = c / (f * sqrt(eff))
    - lf = lambda_g / 2

    Catatan:
    - Input f_ghz dalam GHz
    - h_mm dan W0 (wo_mm) dalam mm
    """
    f_hz = f_ghz * 1e9
    h_m = h_mm / 1000.0
    w_m = wo_mm / 1000.0  # Wo (lebar microstrip) dalam mm

    if w_m <= 0:
        raise ValueError("W0 harus lebih besar dari 0.")

    eps_eff = (er + 1) / 2 + (er - 1) / 2 * (1 / ((1 + 12 * (h_m / w_m)) ** 0.5))
    lambda_g_m = C0 / (f_hz * (eps_eff ** 0.5))

    a_m = (2 * C0) / (3 * f_hz * (er ** 0.5))
    ws_m = 1.5 * a_m
    ls_m = 1.5 * a_m
    lf_m = lambda_g_m / 2

    return {
        "wo": wo_mm,
        "lf_mm": lf_m * 1000,
        "a_mm": a_m * 1000,
        "ws_mm": ws_m * 1000,
        "ls_mm": ls_m * 1000,
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
        "z0": "50 Ohm",
        "wo": 3.0
    }

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
            try:
                hasil = calc(freq, er, h, wo)
            except ValueError:
                hasil = None
            else:
                form.update({"freq": freq, "er": er, "h": h, "wo": wo})

    img_c = cst_image_relpath(form["freq"], "antena.png")
    img_gain = cst_image_relpath(form["freq"], "gain.png")
    img_pola = cst_image_relpath(form["freq"], "pola.png")
    img_return_loss = cst_image_relpath(form["freq"], "RETURN LOSS.png")
    img_vswr = cst_image_relpath(form["freq"], "VSWR.png")

    freq_image_urls = {str(f): cst_image_urls(f) for f in FREQ_OPTIONS_GHZ}

    return render_template(
        "index.html",
        freq_options=FREQ_OPTIONS_GHZ,
        form=form,
        hasil=hasil,
        img_c=img_c,
        img_gain=img_gain,
        img_pola=img_pola,
        img_return_loss=img_return_loss,
        img_vswr=img_vswr,
        freq_image_urls=freq_image_urls,
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

    try:
        hasil = calc(freq, er, h, wo)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    imgs = cst_image_urls(freq)
    return jsonify({
        "ok": True,
        "hasil": hasil,
        "imgs": imgs,
        "img_c": imgs["antena"],
        "img_d": imgs["pola"],
    })

if __name__ == "__main__":
    app.run(debug=True)

