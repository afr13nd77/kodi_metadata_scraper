from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.join(PROJECT_DIR, "shared")

ADDONS = [
    {"addon_dir": "metadata.ums", "archive_root": "metadata.ums"},
    {"addon_dir": "metadata.tvshows.ums", "archive_root": "metadata.tvshows.ums"},
]

EXCLUDE_DIRS = {"tests", "__pycache__", ".pytest_cache", ".claude"}
EXCLUDE_EXTENSIONS = {".pyc"}


def get_addon_version(addon_dir_path: str) -> str:
    """Parse addon.xml and return the version attribute from the root <addon> element."""
    addon_xml_path = os.path.join(addon_dir_path, "addon.xml")
    tree = ET.parse(addon_xml_path)
    root = tree.getroot()
    version = root.get("version")
    if not version:
        raise ValueError(f"No version attribute found in {addon_xml_path}")
    return version


def build_addon_zip(cfg: dict) -> None:
    """Build a single addon zip according to *cfg*."""
    addon_dir_path = os.path.join(PROJECT_DIR, cfg["addon_dir"])
    archive_root = cfg["archive_root"]
    version = get_addon_version(addon_dir_path)
    output_name = f"{archive_root}-{version}.zip"
    output_path = os.path.join(PROJECT_DIR, output_name)

    if os.path.exists(output_path):
        os.remove(output_path)

    file_count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Walk addon directory and add all files (respecting exclusions)
        for root, dirs, files in os.walk(addon_dir_path):
            # Prune excluded directories so os.walk does not descend into them
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for filename in sorted(files):
                _, ext = os.path.splitext(filename)
                if ext in EXCLUDE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, addon_dir_path)
                arcname = os.path.join(archive_root, rel_path)
                zf.write(filepath, arcname)
                file_count += 1
                print(f"  + {arcname}")

        # Copy shared modules into {archive_root}/python/ inside the zip
        for filename in sorted(os.listdir(SHARED_DIR)):
            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(SHARED_DIR, filename)
            if not os.path.isfile(filepath):
                continue

            arcname = os.path.join(archive_root, "python", filename)
            zf.write(filepath, arcname)
            file_count += 1
            print(f"  + {arcname}  (shared)")

    size_kb = os.path.getsize(output_path) / 1024
    print(f"\nBuild complete: {output_name}")
    print(f"Version: {version}")
    print(f"Files: {file_count}")
    print(f"Size: {size_kb:.1f} KB")


def build_all() -> None:
    """Iterate ADDONS, build each, print separator and final success message."""
    for idx, cfg in enumerate(ADDONS):
        if idx > 0:
            print("\n" + "=" * 60 + "\n")
        print(f"Building {cfg['addon_dir']} ...")
        print("-" * 40)
        build_addon_zip(cfg)

    print("\n" + "=" * 60)
    print("All addons built successfully.")


if __name__ == "__main__":
    build_all()
