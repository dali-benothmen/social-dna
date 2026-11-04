"""Install both built distributions and smoke-test their packaged migrations.

Run `uv build` first. Use --offline when the dependency resolver's complete
registry metadata and compatible wheels are cached. Use --uv and --cache-dir
when build tooling is isolated outside PATH.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
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
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    cache = ["--cache-dir", args.cache_dir] if args.cache_dir else []
    for pattern in (f"socialdna-{version}-*.whl", f"socialdna-{version}.tar.gz"):
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
            export = isolated / "account.json"
            shutil.copyfile(root / "examples/imports/account.json", export)
            base = [
                str(executable),
                "--data-dir",
                str(isolated / "data"),
                "--offline",
                "--format",
                "json",
            ]
            imported = json.loads(run([*base, "import", "json", str(export)], cwd=isolated))
            account_id = imported["data"]["account_ids"][0]
            analyzed = json.loads(
                run(
                    [*base, "analyze", "account", account_id, "--metric", "demo.views.v1"],
                    cwd=isolated,
                )
            )
            account_report = json.loads(
                run([*base, "report", "generate", "--account", account_id], cwd=isolated)
            )
            if account_report["data"]["content"]["results"]["available_n"] != 2:
                raise RuntimeError("Installed account report lost imported observations")
            if analyzed["run_id"] != account_report["data"]["content"]["run_id"]:
                raise RuntimeError("Installed account report did not reopen the saved analysis")
            print(
                f"PASS: {distribution.name} installed account import, analytics and report restart"
            )
            if shutil.which("ffmpeg") and shutil.which("ffprobe"):
                source = isolated / "generated.mkv"
                run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-v",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "color=c=red:s=64x48:r=10:d=0.5",
                        "-an",
                        "-c:v",
                        "ffv1",
                        "-threads",
                        "1",
                        str(source),
                    ],
                    cwd=isolated,
                )
                analysis = json.loads(
                    run(
                        [
                            str(executable),
                            "analyze",
                            "video",
                            str(source),
                            "--format",
                            "json",
                            "--data-dir",
                            str(isolated / "data"),
                        ],
                        cwd=isolated,
                    )
                )
                if analysis["status"] != "success" or not analysis["data"]["reports"]:
                    raise RuntimeError(f"Installed media analysis failed: {analysis}")
                report = json.loads(
                    run(
                        [
                            str(executable),
                            "report",
                            "generate",
                            "--run",
                            analysis["run_id"],
                            "--format",
                            "json",
                            "--data-dir",
                            str(isolated / "data"),
                        ],
                        cwd=isolated,
                    )
                )
                if not report["data"]["content"]["timeline"]["observations"]:
                    raise RuntimeError("Installed media report has no measurements.")
                print(f"PASS: {distribution.name} installed video analysis and report restart")
            print(f"PASS: {distribution.name} isolated install, initialization and verification")


if __name__ == "__main__":
    main()
