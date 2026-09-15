"""Verify every vendored challenge dependency against the published release hashes."""
from . import paths
from .io import loads, sha256


def verify():
    released = loads((paths.VENDOR / "RELEASE_MANIFEST.json").read_text())["files"]
    checked = []
    for path in sorted(paths.VENDOR.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(paths.VENDOR))
        key = "references/" + relative if relative.startswith("OP-") else relative
        if key in released:
            if sha256(path) != released[key]:
                raise ValueError(f"vendored challenge file changed: {relative}")
            checked.append(relative)
        elif relative not in {"PROVENANCE.md", "RELEASE_MANIFEST.json"}:
            raise ValueError(f"unrecognised vendored file: {relative}")
    return {"checked_files": len(checked), "files": checked, "all_match": True}


if __name__ == "__main__":
    print(verify())
