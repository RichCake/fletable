from __future__ import annotations

import argparse
import shutil
from importlib import resources
from pathlib import Path

def _copy_template(destination: Path) -> None:
    template_dir = resources.files("fletable").joinpath("flet_template")
    with resources.as_file(template_dir) as template_path:
        shutil.copytree(template_path, destination, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="flet-template-init")
    parser.add_argument("destination")
    args = parser.parse_args()

    destination = Path(args.destination).expanduser().resolve()
    if destination.exists() and destination.is_file():
        parser.error(f"Destination is a file: {destination}")

    destination.mkdir(parents=True, exist_ok=True)
    _copy_template(destination=destination)
    print(f"Template copied to: {destination}")


if __name__ == "__main__":
    main()
