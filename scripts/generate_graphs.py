import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.transforms as mtrans


ROOT = Path(__file__).resolve().parents[1]
INPUT_ROOT = ROOT / "static" / "gambar cst file"
OUTPUT_ROOT = ROOT / "static" / "img" / "grafik cst"

FLOAT_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def extract_freq(path: Path) -> float | None:
    matches = re.findall(r"\d+(?:[.,]\d+)?", str(path))
    if not matches:
        return None
    raw = matches[-1].replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def freq_dir_name(freq: float | None) -> str:
    if freq is None:
        return "unknown"
    rounded = round(freq, 1)
    if abs(freq - rounded) < 1e-9:
        return f"{rounded:.1f}"
    return f"{freq:g}"


def parse_rows(file_path: Path) -> tuple[str, list[list[float]]]:
    text = file_path.read_text(errors="ignore").splitlines()
    header = " ".join(text[:3]).lower()
    rows: list[list[float]] = []
    for line in text:
        if not re.search(r"\d", line):
            continue
        nums = FLOAT_RE.findall(line)
        if len(nums) < 2:
            continue
        rows.append([float(n) for n in nums])
    return header, rows


def detect_labels(file_path: Path, header: str) -> tuple[str, str, int, int]:
    name = file_path.stem.lower()
    if "gain" in name:
        y_label = "Gain (dBi)"
    elif "vswr" in name:
        y_label = "VSWR"
    elif "rl" in name or "return" in name or "sparameter" in name:
        y_label = "Return Loss (dB)"
    elif "pola" in name:
        y_label = "Pola (dB)"
    else:
        y_label = "Value"

    header_l = header.lower()
    if ("theta" in header_l) or ("angle" in header_l):
        x_label = "Angle (deg)"
        use_third = "abs(gain)" in header_l or "theta" in header_l
    else:
        x_label = "Frequency (GHz)"
        use_third = False

    x_idx = 0
    y_idx = 2 if use_third else 1
    return x_label, y_label, x_idx, y_idx


def output_name(file_path: Path) -> str:
    name = file_path.stem.lower()
    if "gain" in name:
        return "gain.png"
    if "vswr" in name:
        return "vswr.png"
    if "rl" in name or "return" in name or "sparameter" in name:
        return "return_loss.png"
    if "pola" in name:
        return "pola.png"
    return f"{file_path.stem}.png"


def plot_file(file_path: Path, out_dir: Path, freq: float | None) -> Path | None:
    header, rows = parse_rows(file_path)
    if not rows:
        return None

    x_label, y_label, x_idx, y_idx = detect_labels(file_path, header)

    x_vals = []
    y_vals = []
    for row in rows:
        if len(row) <= max(x_idx, y_idx):
            continue
        x_vals.append(row[x_idx])
        y_vals.append(row[y_idx])

    if not x_vals:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name(file_path)
    meta_path = out_dir / f"{out_path.stem}.meta.json"

    fig, ax = plt.subplots(figsize=(6.2, 4.0), dpi=140)
    ax.plot(x_vals, y_vals, color="#1f7a8c", linewidth=1.6)
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.6)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if freq is not None:
        ax.set_title(f"{y_label} - {freq_dir_name(freq)} GHz")
    else:
        ax.set_title(y_label)
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
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    fig.savefig(out_path, bbox_inches=fig_bbox)
    plt.close(fig)
    return out_path


def main() -> None:
    sources = {
        "CST": INPUT_ROOT / "CST",
        "AWR": INPUT_ROOT / "AWR",
    }
    for source, src_dir in sources.items():
        if not src_dir.exists():
            continue
        for file_path in src_dir.rglob("*.txt"):
            freq = extract_freq(file_path)
            freq_dir = freq_dir_name(freq)
            out_dir = OUTPUT_ROOT / source / freq_dir
            plot_file(file_path, out_dir, freq)


if __name__ == "__main__":
    main()
