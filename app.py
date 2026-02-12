from pathlib import Path
import os
import subprocess
import sys

from flask import Flask, render_template, request, redirect, url_for, jsonify


app = Flask(__name__)
STATIC_ROOT = Path(app.root_path) / "static"

GDRIVE_FOLDER_URL = os.getenv("GDRIVE_FOLDER_URL", "https://drive.google.com/drive/folders/1l4SOF8xSFUQWzJnWUZCW5XK6jVLqPjf8")
SYNC_GDRIVE_ON_START = os.getenv("GDRIVE_SYNC_ON_START", "0").lower() in {"1", "true", "yes", "on"}
SYNC_GDRIVE_FORCE = os.getenv("GDRIVE_SYNC_FORCE", "0").lower() in {"1", "true", "yes", "on"}
SYNC_REBUILD_GRAPHS = os.getenv("GDRIVE_SYNC_REBUILD_GRAPHS", "1").lower() in {"1", "true", "yes", "on"}
SYNC_MARKER_PATH = STATIC_ROOT / "gambar cst file" / ".gdrive_sync_done"

IMG_DRIVE_FOLDER_URL = os.getenv("IMG_DRIVE_FOLDER_URL", "https://drive.google.com/drive/folders/1t-yekQlxnPuYDCWKW6UlgXXKaU-oPlGB")
IMG_SYNC_ON_START = os.getenv("IMG_SYNC_ON_START", "0").lower() in {"1", "true", "yes", "on"}
IMG_SYNC_FORCE = os.getenv("IMG_SYNC_FORCE", "0").lower() in {"1", "true", "yes", "on"}
IMG_SYNC_MARKER_PATH = STATIC_ROOT / "img" / ".gdrive_sync_done"


C0 = 3e8  # m/s
FREQ_OPTIONS_GHZ = [1.8, 2.2, 2.3, 2.4, 3.3]  # sesuai PDF
CST_FREQ_DIR = {
    1.8: "1.8",
    2.2: "22",
    2.3: "23",
    2.4: "24",
    3.3: "33",
}
GRAPH_FREQ_DIR = {
    1.8: "1.8",
    2.2: "2.2",
    2.3: "2.3",
    2.4: "2.4",
    3.3: "3.3",
}
TXT_FREQ_DIR = {
    "CST": {
        1.8: ("1.8 GHZ",),
        2.2: ("2.2 GHZ",),
        2.3: ("2.3 GHZ",),
        2.4: ("2.4 GHZ",),
        3.3: ("3.33", "3.3"),
    },
    "AWR": {
        1.8: ("1.8",),
        2.2: ("2.2",),
        2.3: ("2,3",),
        2.4: ("2.4",),
        3.3: ("3.3",),
    },
}
TXT_KIND_KEYWORDS = {
    "gain": ("gain",),
    "return_loss": ("return", "rl", "sparameter"),
    "vswr": ("vswr",),
    "pola": ("pola",),
}



def sync_gdrive_folder() -> bool:
    if not SYNC_GDRIVE_ON_START:
        return False
    if (not SYNC_GDRIVE_FORCE) and SYNC_MARKER_PATH.exists():
        return False
    try:
        import gdown
    except Exception as exc:
        print(f"[gdrive] gdown tidak tersedia: {exc}")
        return False

def sync_img_folder() -> bool:
    if not IMG_SYNC_ON_START:
        return False
    if (not IMG_SYNC_FORCE) and IMG_SYNC_MARKER_PATH.exists():
        return False
    try:
        import gdown
    except Exception as exc:
        print(f"[gdrive] gdown tidak tersedia: {exc}")
        return False

    dest = STATIC_ROOT / "img"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        files = gdown.download_folder(
            url=IMG_DRIVE_FOLDER_URL,
            output=str(dest),
            quiet=True,
            remaining_ok=True,
            resume=True,
        )
    except Exception as exc:
        print(f"[gdrive] gagal sync img: {exc}")
        return False

    if not files:
        return False
    try:
        IMG_SYNC_MARKER_PATH.write_text("ok", encoding="utf-8")
    except Exception:
        pass
    print(f"[gdrive] sync img selesai: {len(files)} file")
    return True


    dest = STATIC_ROOT / "gambar cst file"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        files = gdown.download_folder(
            url=GDRIVE_FOLDER_URL,
            output=str(dest),
            quiet=True,
            remaining_ok=True,
            resume=True,
        )
    except Exception as exc:
        print(f"[gdrive] gagal sync: {exc}")
        return False

    if not files:
        return False
    try:
        SYNC_MARKER_PATH.write_text("ok", encoding="utf-8")
    except Exception:
        pass
    print(f"[gdrive] sync selesai: {len(files)} file")
    return True


def rebuild_graphs() -> None:
    script_path = Path(__file__).resolve().parent / "scripts" / "generate_graphs.py"
    if not script_path.exists():
        print("[gdrive] scripts/generate_graphs.py tidak ditemukan.")
        return
    try:
        subprocess.run([sys.executable, str(script_path)], check=True)
        print("[gdrive] grafik diperbarui.")
    except Exception as exc:
        print(f"[gdrive] gagal update grafik: {exc}")


def maybe_sync_on_start() -> None:
    synced = sync_gdrive_folder()
    sync_img_folder()
    if synced and SYNC_REBUILD_GRAPHS:
        rebuild_graphs()


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

def graph_image_relpath(freq_ghz: float, source: str, filename: str) -> str:
    freq_dir = GRAPH_FREQ_DIR.get(freq_ghz)
    if not freq_dir:
        raise ValueError("Frekuensi tidak tersedia.")
    return f"img/grafik cst/{source}/{freq_dir}/{filename}"


def graph_image_urls(freq_ghz: float, source: str = "CST") -> dict:
    def build_url(filename: str) -> str | None:
        relpath = graph_image_relpath(freq_ghz, source, filename)
        if not (STATIC_ROOT / relpath).exists():
            return None
        return url_for("static", filename=relpath)

    return {
        "gain": build_url("gain.png"),
        "return_loss": build_url("return_loss.png"),
        "vswr": build_url("vswr.png"),
        "pola": build_url("pola.png"),
    }


def txt_data_relpath(freq_ghz: float, source: str, kind: str) -> str | None:
    source_dirs = TXT_FREQ_DIR.get(source, {})
    dir_parts = source_dirs.get(freq_ghz)
    if not dir_parts:
        return None
    base_dir = STATIC_ROOT / "gambar cst file" / source
    dir_path = base_dir.joinpath(*dir_parts)
    if not dir_path.exists():
        return None
    keywords = TXT_KIND_KEYWORDS.get(kind, ())
    for path in sorted(dir_path.rglob("*.txt")):
        name = path.name.lower()
        if any(key in name for key in keywords):
            return path.relative_to(STATIC_ROOT).as_posix()
    return None


def graph_data_urls_for(freq_ghz: float, source: str = "CST") -> dict:
    def build_url(kind: str) -> str | None:
        relpath = txt_data_relpath(freq_ghz, source, kind)
        if not relpath:
            return None
        return url_for("static", filename=relpath)

    return {
        "gain": build_url("gain"),
        "return_loss": build_url("return_loss"),
        "vswr": build_url("vswr"),
        "pola": build_url("pola"),
    }

def calc(f_ghz: float, er: float, h_mm: float, wf_mm: float = 3.0):
    """
    Rumus (sesuai spesifikasi):
    - a = (2*c) / (3*f*sqrt(er))
    - wg = lg = a + 6h
    - Ht = (sqrt(3)/2) * a
    - lambda0 = c / f
    - eff = (er+1)/2 + (er-1)/2 * ( 1 / sqrt(1 + 12h/Wf) )
    - lambda_g = c / (f * sqrt(eff))
    - lf = lambda_g / 2

    Catatan:
    - Input f_ghz dalam GHz
    - h_mm dan Wf (wf_mm) dalam mm
    """
    f_hz = f_ghz * 1e9
    h_m = h_mm / 1000.0
    w_m = wf_mm / 1000.0  # Wf (lebar microstrip) dalam mm

    if w_m <= 0:
        raise ValueError("Wf harus lebih besar dari 0.")

    eps_eff = (er + 1) / 2 + (er - 1) / 2 * (1 / ((1 + 12 * (h_m / w_m)) ** 0.5))
    lambda_g_m = C0 / (f_hz * (eps_eff ** 0.5))

    a_m = (2 * C0) / (3 * f_hz * (er ** 0.5))
    wg_m = a_m + (6 * h_m)
    lg_m = a_m + (6 * h_m)
    ht_m = ((3 ** 0.5) / 2) * a_m
    lf_m = lambda_g_m / 2

    return {
        "wf": wf_mm,
        "lf_mm": lf_m * 1000,
        "a_mm": a_m * 1000,
        "wg_mm": wg_m * 1000,
        "lg_mm": lg_m * 1000,
        "ht_mm": ht_m * 1000,
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
        "wf": 3.0
    }
maybe_sync_on_start()


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
            wf = float(request.form.get("wf", form["wf"]))
        except (TypeError, ValueError):
            freq = form["freq"]
            er = form["er"]
            h = form["h"]
            wf = form["wf"]

        if freq in FREQ_OPTIONS_GHZ:
            try:
                hasil = calc(freq, er, h, wf)
            except ValueError:
                hasil = None
            else:
                form.update({"freq": freq, "er": er, "h": h, "wf": wf})

    img_c = cst_image_relpath(form["freq"], "antena.png")
    img_gain = cst_image_relpath(form["freq"], "gain.png")
    img_pola = cst_image_relpath(form["freq"], "pola.png")
    img_return_loss = cst_image_relpath(form["freq"], "RETURN LOSS.png")
    img_vswr = cst_image_relpath(form["freq"], "VSWR.png")

    freq_image_urls = {str(f): cst_image_urls(f) for f in FREQ_OPTIONS_GHZ}
    graph_urls = graph_image_urls(form["freq"], "CST")
    freq_graph_urls = {str(f): graph_image_urls(f, "CST") for f in FREQ_OPTIONS_GHZ}
    graph_urls_awr = graph_image_urls(form["freq"], "AWR")
    freq_graph_urls_awr = {str(f): graph_image_urls(f, "AWR") for f in FREQ_OPTIONS_GHZ}
    graph_data_urls = graph_data_urls_for(form["freq"], "CST")
    freq_graph_data_urls = {str(f): graph_data_urls_for(f, "CST") for f in FREQ_OPTIONS_GHZ}
    graph_data_urls_awr = graph_data_urls_for(form["freq"], "AWR")
    freq_graph_data_urls_awr = {str(f): graph_data_urls_for(f, "AWR") for f in FREQ_OPTIONS_GHZ}

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
        graph_urls=graph_urls,
        freq_graph_urls=freq_graph_urls,
        graph_urls_awr=graph_urls_awr,
        freq_graph_urls_awr=freq_graph_urls_awr,
        graph_data_urls=graph_data_urls,
        freq_graph_data_urls=freq_graph_data_urls,
        graph_data_urls_awr=graph_data_urls_awr,
        freq_graph_data_urls_awr=freq_graph_data_urls_awr,
    )

@app.route("/api/calculator", methods=["POST"])
def calculator_api():
    form = get_default_form()
    try:
        freq = float(request.form.get("freq", form["freq"]))
        er = float(request.form.get("er", form["er"]))
        h = float(request.form.get("h", form["h"]))
        wf = float(request.form.get("wf", form["wf"]))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Input tidak valid."}), 400

    if freq not in FREQ_OPTIONS_GHZ:
        return jsonify({"ok": False, "message": "Frekuensi tidak tersedia."}), 400

    try:
        hasil = calc(freq, er, h, wf)
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

