import argparse
from pathlib import Path

import gdown

DEFAULT_URL = "https://drive.google.com/drive/folders/1l4SOF8xSFUQWzJnWUZCW5XK6jVLqPjf8"
DEFAULT_DEST = Path(__file__).resolve().parents[1] / "static" / "gambar cst file"


def sync_folder(url: str = DEFAULT_URL, dest: Path = DEFAULT_DEST, quiet: bool = False) -> list[str] | None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    files = gdown.download_folder(
        url=url,
        output=str(dest),
        quiet=quiet,
        remaining_ok=True,
        resume=True,
    )
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Google Drive folder to static/gambar cst file.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Google Drive folder URL")
    parser.add_argument("--dest", default=str(DEFAULT_DEST), help="Destination folder")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    files = sync_folder(args.url, Path(args.dest), quiet=args.quiet)
    if not files:
        print("Tidak ada file yang diunduh atau gagal mengunduh.")
        return
    print(f"Selesai mengunduh {len(files)} file.")


if __name__ == "__main__":
    main()
