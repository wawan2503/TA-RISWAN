from pathlib import Path
import os
import subprocess
import sys
import re
import urllib.request

from flask import Flask, render_template, request, redirect, url_for, jsonify, Response


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

USE_DRIVE_ASSETS = os.getenv("USE_DRIVE_ASSETS", "1").lower() in {"1", "true", "yes", "on"}
DRIVE_IMG_INDEX: dict[str, str] = {}
DRIVE_TXT_INDEX: dict[str, str] = {}
DRIVE_IMG_READY = False
DRIVE_TXT_READY = False


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



def _normalize_drive_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def _load_drive_index(url: str) -> dict[str, str]:
    try:
        import gdown
    except Exception as exc:
        print(f"[gdrive] gdown tidak tersedia: {exc}")
        return {}
    try:
        files = gdown.download_folder(url=url, skip_download=True, quiet=True)
    except Exception as exc:
        print(f"[gdrive] gagal membaca folder: {exc}")
        return {}
    index: dict[str, str] = {}
    if not files:
        return index
    for item in files:
        path = _normalize_drive_path(item.path)
        if path:
            index[path] = item.id
    return index


def ensure_drive_img_index() -> None:
    global DRIVE_IMG_READY, DRIVE_IMG_INDEX
    if DRIVE_IMG_READY:
        return
    index = _load_drive_index(IMG_DRIVE_FOLDER_URL)
    if index:
        DRIVE_IMG_INDEX = index
        DRIVE_IMG_READY = True


def ensure_drive_txt_index() -> None:
    global DRIVE_TXT_READY, DRIVE_TXT_INDEX
    if DRIVE_TXT_READY:
        return
    index = _load_drive_index(GDRIVE_FOLDER_URL)
    if index:
        DRIVE_TXT_INDEX = index
        DRIVE_TXT_READY = True


def drive_file_url(file_id: str, export: str = "download") -> str:
    return f"https://drive.google.com/uc?export={export}&id={file_id}"


def drive_img_file_id(rel_path: str) -> str | None:
    ensure_drive_img_index()
    key = _normalize_drive_path(rel_path)
    return DRIVE_IMG_INDEX.get(key)


def drive_img_url(rel_path: str) -> str | None:
    file_id = drive_img_file_id(rel_path)
    if not file_id:
        return None
    return url_for("drive_img", rel_path=rel_path)


def drive_txt_file_id(freq_ghz: float, source: str, kind: str) -> str | None:
    ensure_drive_txt_index()
    source_key = source.upper()
    if source_key not in TXT_FREQ_DIR:
        return None
    dir_parts = TXT_FREQ_DIR[source_key].get(freq_ghz)
    if not dir_parts:
        return None
    prefix = "/".join([source_key, *dir_parts]).strip("/")
    keywords = TXT_KIND_KEYWORDS.get(kind, ())
    for path, file_id in DRIVE_TXT_INDEX.items():
        if not path.startswith(prefix + "/"):
            continue
        name = path.split("/")[-1].lower()
        if any(key in name for key in keywords):
            return file_id
    return None


def fetch_drive_file_bytes(file_id: str) -> bytes | None:
    try:
        with urllib.request.urlopen(drive_file_url(file_id)) as resp:
            return resp.read()
    except Exception as exc:
        print(f"[gdrive] gagal fetch file: {exc}")
        return None



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
    if USE_DRIVE_ASSETS:
        ensure_drive_img_index()
        ensure_drive_txt_index()


def cst_image_relpath(freq_ghz: float, filename: str) -> str:
    freq_dir = CST_FREQ_DIR.get(freq_ghz)
    if not freq_dir:
        raise ValueError("Frekuensi tidak tersedia.")
    return f"img/gambar cst/{freq_dir}/{filename}"


def cst_image_urls(freq_ghz: float) -> dict:
    if USE_DRIVE_ASSETS:
        freq_dir = CST_FREQ_DIR.get(freq_ghz)
        if not freq_dir:
            raise ValueError("Frekuensi tidak tersedia.")
        base = f"gambar cst/{freq_dir}"
        return {
            "antena": drive_img_url(f"{base}/antena.png"),
            "gain": drive_img_url(f"{base}/gain.png"),
            "pola": drive_img_url(f"{base}/pola.png"),
            "return_loss": drive_img_url(f"{base}/RETURN LOSS.png"),
            "vswr": drive_img_url(f"{base}/VSWR.png"),
        }
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
    if USE_DRIVE_ASSETS:
        freq_dir = GRAPH_FREQ_DIR.get(freq_ghz)
        if not freq_dir:
            raise ValueError("Frekuensi tidak tersedia.")
        base = f"grafik cst/{source}/{freq_dir}"
        return {
            "gain": drive_img_url(f"{base}/gain.png"),
            "return_loss": drive_img_url(f"{base}/return_loss.png"),
            "vswr": drive_img_url(f"{base}/vswr.png"),
            "pola": drive_img_url(f"{base}/pola.png"),
        }

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
        if USE_DRIVE_ASSETS:
            return url_for("drive_txt", source=source, freq=freq_ghz, kind=kind)
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


def graph_meta_urls_for(freq_ghz: float, source: str = "CST") -> dict:
    def build_url(kind: str) -> str | None:
        if not USE_DRIVE_ASSETS:
            return None
        return url_for("drive_meta", source=source, freq=freq_ghz, kind=kind)

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






@app.route("/drive/img/<path:rel_path>")
def drive_img(rel_path: str):
    if not USE_DRIVE_ASSETS:
        return "", 404
    file_id = drive_img_file_id(rel_path)
    if not file_id:
        return "", 404
    data = fetch_drive_file_bytes(file_id)
    if data is None:
        return "", 502
    ext = rel_path.lower().rsplit(".", 1)[-1] if "." in rel_path else ""
    if ext == "png":
        mime = "image/png"
    elif ext in {"jpg", "jpeg"}:
        mime = "image/jpeg"
    else:
        mime = "application/octet-stream"
    return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})

@app.route("/drive/txt/<source>/<freq>/<kind>")
def drive_txt(source: str, freq: str, kind: str):
    if not USE_DRIVE_ASSETS:
        return "", 404
    try:
        freq_val = float(freq)
    except ValueError:
        return "", 400
    kind_key = kind.lower()
    file_id = drive_txt_file_id(freq_val, source, kind_key)
    if not file_id:
        return "", 404
    data = fetch_drive_file_bytes(file_id)
    if data is None:
        return "", 502
    return data, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/drive/meta/<source>/<freq>/<kind>")
def drive_meta(source: str, freq: str, kind: str):
    if not USE_DRIVE_ASSETS:
        return "", 404
    try:
        freq_val = float(freq)
    except ValueError:
        return "", 400
    kind_key = kind.lower()
    file_id = drive_txt_file_id(freq_val, source, kind_key)
    if not file_id:
        return "", 404
    raw = fetch_drive_file_bytes(file_id)
    if raw is None:
        return "", 502
    text_data = raw.decode("utf-8", errors="ignore")
    lines = text_data.splitlines()
    header = " ".join(lines[:3]).lower()
    rows = []
    for line in lines:
        if not re.search(r"\d", line):
            continue
        nums = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", line)
        if len(nums) < 2:
            continue
        rows.append([float(n) for n in nums])
    if not rows:
        return "", 404

    is_angle = ("theta" in header) or ("angle" in header)
    has_abs_gain = ("abs(gain)" in header) or ("abs(theta)" in header) or ("abs(phi)" in header)
    x_idx = 0
    y_idx = 2 if has_abs_gain and len(rows[0]) > 2 else 1
    x_vals = []
    y_vals = []
    for row in rows:
        if len(row) <= y_idx:
            continue
        x_vals.append(row[x_idx])
        y_vals.append(row[y_idx])
    if not x_vals:
        return "", 404

    # Labels are not used for meta, but keep plot consistent
    if kind_key == "gain":
        y_label = "Gain (dBi)"
    elif kind_key == "vswr":
        y_label = "VSWR"
    elif kind_key == "return_loss":
        y_label = "Return Loss (dB)"
    elif kind_key == "pola":
        y_label = "Pola (dB)"
    else:
        y_label = "Value"
    x_label = "Angle (deg)" if is_angle else "Frequency (GHz)"

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.transforms as mtrans

    fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=140)
    ax.plot(x_vals, y_vals, color="#1f7a8c", linewidth=1.6)
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.6)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if freq_val:
        ax.set_title(f"{y_label} - {freq_val} GHz")
    fig.tight_layout()

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    ax_bbox = ax.get_window_extent(renderer)
    fig_bbox = fig.get_tightbbox(renderer)
    fig_bbox_px = fig_bbox.transformed(mtrans.Affine2D().scale(fig.dpi))

    width = max(fig_bbox_px.width, 1.0)
    height = max(fig_bbox_px.height, 1.0)
    left = (ax_bbox.x0 - fig_bbox_px.x0) / width
    right = 1.0 - (ax_bbox.x1 - fig_bbox_px.x0) / width
    bottom = (ax_bbox.y0 - fig_bbox_px.y0) / height
    top = 1.0 - (ax_bbox.y1 - fig_bbox_px.y0) / height

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    plt.close(fig)

    meta = {
        "pad": {
            "left": max(0.0, min(1.0, left)),
            "right": max(0.0, min(1.0, right)),
            "top": max(0.0, min(1.0, top)),
            "bottom": max(0.0, min(1.0, bottom)),
        },
        "xlim": [float(xlim[0]), float(xlim[1])],
        "ylim": [float(ylim[0]), float(ylim[1])],
    }
    return jsonify(meta)

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

    imgs_current = cst_image_urls(form["freq"])
    img_c = imgs_current["antena"]
    img_gain = imgs_current["gain"]
    img_pola = imgs_current["pola"]
    img_return_loss = imgs_current["return_loss"]
    img_vswr = imgs_current["vswr"]
    freq_image_urls = {str(f): cst_image_urls(f) for f in FREQ_OPTIONS_GHZ}
    graph_urls = graph_image_urls(form["freq"], "CST")
    freq_graph_urls = {str(f): graph_image_urls(f, "CST") for f in FREQ_OPTIONS_GHZ}
    graph_urls_awr = graph_image_urls(form["freq"], "AWR")
    freq_graph_urls_awr = {str(f): graph_image_urls(f, "AWR") for f in FREQ_OPTIONS_GHZ}
    graph_data_urls = graph_data_urls_for(form["freq"], "CST")
    freq_graph_data_urls = {str(f): graph_data_urls_for(f, "CST") for f in FREQ_OPTIONS_GHZ}
    graph_data_urls_awr = graph_data_urls_for(form["freq"], "AWR")
    freq_graph_data_urls_awr = {str(f): graph_data_urls_for(f, "AWR") for f in FREQ_OPTIONS_GHZ}
    graph_meta_urls = graph_meta_urls_for(form["freq"], "CST")
    freq_graph_meta_urls = {str(f): graph_meta_urls_for(f, "CST") for f in FREQ_OPTIONS_GHZ}
    graph_meta_urls_awr = graph_meta_urls_for(form["freq"], "AWR")
    freq_graph_meta_urls_awr = {str(f): graph_meta_urls_for(f, "AWR") for f in FREQ_OPTIONS_GHZ}

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
        graph_meta_urls=graph_meta_urls,
        freq_graph_meta_urls=freq_graph_meta_urls,
        graph_meta_urls_awr=graph_meta_urls_awr,
        freq_graph_meta_urls_awr=freq_graph_meta_urls_awr,
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

