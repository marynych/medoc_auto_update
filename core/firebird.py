import re
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from core.utils import run_command

GFIX_USER = "SYSDBA"
GFIX_PASS = "masterkey"
GFIX_LINE_RE = re.compile(r"^\s*(.+?)\s*:\s*([-+]?\d[\d,]*)\s*$", re.MULTILINE)

ValidationResult = Dict[str, int]


def parse_gfix_output(raw_text: str) -> ValidationResult:
    # gfix -validate output -> {metric name: count}, e.g. {"Number of bad pages": 0}
    if not raw_text:
        return {}

    result = {}
    for key, value in GFIX_LINE_RE.findall(raw_text):
        try:
            result[key.strip()] = int(value.replace(",", ""))
        except ValueError:
            continue
    return result


def run_gfix_validate(gfix_path: Path, db_path: Path) -> str:
    # read-only full validation, returns raw stdout
    cmd = [
        str(gfix_path), "-validate", "-full", "-no_update",
        "-user", GFIX_USER, "-pass", GFIX_PASS, str(db_path),
    ]
    return run_command(cmd)


def stop_service(service_name: str) -> None:
    logger.info(f"Stopping service {service_name}")
    run_command(["powershell", "-Command", f"Stop-Service {service_name} -ErrorAction Stop"])


def start_service(service_name: str) -> None:
    logger.info(f"Starting service {service_name}")
    run_command(["powershell", "-Command", f"Start-Service {service_name} -ErrorAction Stop"])


def validate(gfix_path: Path, db_path: Path, service_name: Optional[str] = None) -> ValidationResult:
    # stops the service holding the db file open (if any), runs gfix, restarts the service
    try:
        if service_name:
            stop_service(service_name)
        raw = run_gfix_validate(gfix_path, db_path)
        return parse_gfix_output(raw)
    finally:
        if service_name:
            start_service(service_name)
