"""Install both built distributions and smoke-test their packaged migrations.

Run `uv build` first. Use --offline when the dependency resolver's complete
registry metadata and compatible wheels are cached. Use --uv and --cache-dir
when build tooling is isolated outside PATH.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(arguments: list[str], *, cwd: Path) -> str:
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {arguments}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--cache-dir")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = ["--cache-dir", args.cache_dir] if args.cache_dir else []
    for pattern in ("*.whl", "*.tar.gz"):
        distributions = sorted((root / "dist").glob(pattern))
        if len(distributions) != 1:
            raise RuntimeError(f"Expected exactly one {pattern} in dist/, found {distributions}")
        distribution = distributions[0]
        with tempfile.TemporaryDirectory(prefix="socialdna-distribution-") as directory:
            isolated = Path(directory)
            environment = isolated / "venv"
            run(
                [args.uv, "venv", str(environment), "--python", sys.executable, *cache],
                cwd=isolated,
            )
            python = environment / (
                "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
            )
            run(
                [
                    args.uv,
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    *(["--offline"] if args.offline else []),
                    str(distribution),
                    *cache,
                ],
                cwd=isolated,
            )
            module = run(
                [str(python), "-c", "import socialdna; print(socialdna.__file__)"], cwd=isolated
            )
            if "site-packages" not in module:
                raise RuntimeError(f"Distribution imported from the checkout: {module}")
            executable = environment / (
                "Scripts/socialdna.exe" if sys.platform == "win32" else "bin/socialdna"
            )
            for command in (["doctor"], ["storage", "verify"]):
                result = json.loads(
                    run(
                        [
                            str(executable),
                            *command,
                            "--data-dir",
                            str(isolated / "data"),
                            "--format",
                            "json",
                        ],
                        cwd=isolated,
                    )
                )
                if result["status"] != "success" or result["errors"]:
                    raise RuntimeError(f"Installed distribution failed health checks: {result}")
            print(f"PASS: {distribution.name} isolated install, initialization and verification")


if __name__ == "__main__":
    main()
