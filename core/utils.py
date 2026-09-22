import subprocess
from typing import List, Tuple


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """'11.02.209' -> (11, 2, 209)"""
    try:
        major, minor, build = version_str.split(".")
        return int(major), int(minor), int(build)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Could not parse version from string '{version_str}': {e}")


def run_command(cmd: List[str]) -> str:
    # runs cmd, returns stdout; raises with combined stderr+stdout on non-zero exit
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=cmd,
            output=(result.stderr + result.stdout).strip(),
        )
    return result.stdout.strip()
