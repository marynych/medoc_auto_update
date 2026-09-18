from typing import Tuple


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """'11.02.209' -> (11, 2, 209)"""
    try:
        major, minor, build = version_str.split(".")
        return int(major), int(minor), int(build)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Не удалось распознать версию в строке '{version_str}': {e}")
