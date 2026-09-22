import hashlib
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup as bs
from loguru import logger

from core.utils import parse_version

BASE_URL = "https://medoc.ua"
DOWNLOAD_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2
CHUNK_SIZE = 131072


@dataclass(frozen=True)
class AvailableUpdate:
    # one entry from the medoc.ua download page; downloaded/error are
    # filled in later via replace(), once we've tried to fetch it
    version: Tuple[int, int, int]
    url: str
    docs_url: str
    md5: str
    downloaded: bool = False
    error: Optional[str] = None


def parse_updates(html: str) -> List[AvailableUpdate]:
    # page html -> every update listed on it, unfiltered
    soup = bs(html, "html.parser")
    updates = []

    for item in soup.find_all("div", class_="download-dist-specification-item"):
        version_spans = item.find_all("span", class_="js-update-num")
        if len(version_spans) != 1:
            logger.debug("Skipped update list item: missing data")
            continue

        try:
            version = parse_version(version_spans[0].text.strip())
        except ValueError:
            logger.debug("Skipped update list item: unrecognized version")
            continue

        links = item.find_all("a", class_="main-btn")
        md5_spans = item.find_all("span", class_="js-md5")
        if len(links) < 2 or not md5_spans:
            logger.debug("Skipped update list item: missing data")
            continue

        updates.append(AvailableUpdate(
            version=version,
            url=links[0]["href"],
            docs_url=BASE_URL + links[1]["href"],
            md5=md5_spans[0].text.strip().lower(),
        ))

    return updates


def get_md5_hash(file_path: Path) -> str:
    # file on disk -> its md5, read in chunks
    md5 = hashlib.md5()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            md5.update(chunk)
    return md5.hexdigest()


def download_file(url: str, target_dir: Path, expected_md5: str, proxy: Optional[str] = None) -> Path:
    # url + folder + expected md5 -> verified file path, one attempt
    # any failure leaves nothing behind: a partial/wrong file is deleted before raising
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / url.split("/")[-1]
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        with requests.get(url, stream=True, timeout=30, proxies=proxies) as r:
            r.raise_for_status()
            with file_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    f.write(chunk)

        if get_md5_hash(file_path) != expected_md5:
            raise ValueError("Downloaded file's MD5 does not match the expected one")

        return file_path

    except Exception:
        file_path.unlink(missing_ok=True)
        raise


def download_update(update: AvailableUpdate, target_dir: Path, proxy: Optional[str] = None) -> AvailableUpdate:
    # one AvailableUpdate -> the same one, with downloaded/error filled in
    version_str = ".".join(map(str, update.version))

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            download_file(update.url, target_dir, update.md5, proxy)
            logger.success(f"Update {version_str} downloaded successfully.")
            return replace(update, downloaded=True)

        except Exception as e:
            last_error = str(e)
            if attempt < DOWNLOAD_ATTEMPTS:
                logger.warning(f"Failed to download {version_str} (attempt {attempt}/{DOWNLOAD_ATTEMPTS}): {e}")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Failed to download {version_str} (attempt {attempt}/{DOWNLOAD_ATTEMPTS}): {e}")

    return replace(update, error=last_error)


def download_updates(catalog_url: str, updates_dir: Path, floor_version: Tuple[int, int, int], proxy: Optional[str] = None) -> List[AvailableUpdate]:
    # catalog url + "oldest instance still needs this" -> download results
    proxies = {"http": proxy, "https": proxy} if proxy else None
    response = requests.get(catalog_url, proxies=proxies)
    response.raise_for_status()
    needed = [u for u in parse_updates(response.text) if u.version > floor_version]

    if not needed:
        logger.info("No new updates to download.")
        return []

    return [download_update(u, updates_dir, proxy) for u in needed]
