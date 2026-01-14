from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

C0 = 3e8  # m/s
FREQ_OPTIONS_GHZ = [1.8, 2.2, 2.3, 2.4, 3.3]  # sesuai PDF

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

@app.route("/", methods=["GET", "POST"])
def landing():
    if request.method == "POST":
        return redirect(url_for("calculator"))
    return render_template("landing.html")

@app.route("/calculator", methods=["GET", "POST"])
def calculator():
    # default sesuai PDF (FR-4, h=1.6, er=4.4, Z0 50 ohm, Wo=3)
    form = {
        "freq": 2.4,
        "substrat": "FR-4",
        "h": 1.6,
        "er": 4.4,
        "z0": "50 OHM",
        "wo": 3.0
    }

    hasil = None

    if request.method == "POST":
        freq = float(request.form.get("freq", form["freq"]))
        er = float(request.form.get("er", form["er"]))
        h = float(request.form.get("h", form["h"]))
        wo = float(request.form.get("wo", form["wo"]))

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
        img_d=img_d
    )

if __name__ == "__main__":
    app.run(debug=True)
