import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from core.utils import parse_version

NAME_PATTERN = re.compile(r"^.+\.(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)\.upd$", re.IGNORECASE)


@dataclass(frozen=True)
class Update:
    path: Path
    from_version: Tuple[int, int, int]
    to_version: Tuple[int, int, int]


def update_from_path(path: Path) -> Optional[Update]:
    # ezvit.11.02.190-11.02.191.upd -> Update(from=(11,2,190), to=(11,2,191))
    match = NAME_PATTERN.match(path.name)
    if not match:
        return None

    from_str, to_str = match.groups()
    return Update(
        path=path,
        from_version=parse_version(from_str),
        to_version=parse_version(to_str),
    )


def extract_zip(archive_path: Path, member_name: str) -> Path:
    # archive + member name -> extracted file path (next to the archive), one attempt
    # no such member, or a failure mid-write, leaves nothing behind
    target_dir = archive_path.parent
    target_path = target_dir / member_name

    try:
        with zipfile.ZipFile(archive_path) as zf:
            return Path(zf.extract(member_name, target_dir))
    except Exception:
        target_path.unlink(missing_ok=True)
        raise


def discover_update(file_path: Path) -> Optional[Update]:
    # one file -> the Update it represents, or None
    # figuring out the format is part of discovery, not a separate step
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".upd":
            upd_path = file_path
        elif suffix == ".zip":
            # medoc packs the .upd under the archive's own name, just with a different extension
            member_name = file_path.with_suffix(".upd").name
            upd_path = extract_zip(file_path, member_name)
        else:
            logger.debug(f"Skipped {file_path}: unsupported format")
            return None
    except Exception as e:
        logger.debug(f"Skipped {file_path}: {e}")
        return None

    upd = update_from_path(upd_path)
    if not upd:
        logger.debug(f"Skipped {file_path}: not a valid update")
        return None
    return upd


def discover_updates(updates_dir: Path) -> List[Update]:
    # updates/ directory -> sorted list of update files found there
    # archives are converted to .upd files as part of the same scan
    updates = []
    for file_path in Path(updates_dir).iterdir():
        upd = discover_update(file_path)
        if upd:
            updates.append(upd)

    updates.sort(key=lambda u: u.to_version)
    logger.info(f"Found updates in {updates_dir}: {len(updates)}")
    return updates
