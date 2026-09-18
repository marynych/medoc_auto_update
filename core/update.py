import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from core.utils import parse_version

NAME_PATTERN = re.compile(r"^.+\.(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)\.(zip|upd)$", re.IGNORECASE)


@dataclass(frozen=True)
class Update:
    path: Path
    from_version: Tuple[int, int, int]
    to_version: Tuple[int, int, int]


def update_from_path(path: Path) -> Optional[Update]:
    # ezvit.11.02.190-11.02.191.zip -> Update(from=(11,2,190), to=(11,2,191))
    match = NAME_PATTERN.match(path.name)
    if not match:
        return None

    from_str, to_str, _ext = match.groups()
    return Update(
        path=path,
        from_version=parse_version(from_str),
        to_version=parse_version(to_str),
    )


def discover_updates(updates_dir: Path) -> List[Update]:
    # updates/ directory -> sorted list of update files found there
    updates = []
    for file_path in Path(updates_dir).iterdir():
        upd = update_from_path(file_path)
        if upd:
            updates.append(upd)
        else:
            logger.debug(f"Файл {file_path} пропущен: не похож на файл обновления")

    updates.sort(key=lambda u: u.to_version)
    logger.info(f"Найдено обновлений в {updates_dir}: {len(updates)}")
    return updates
