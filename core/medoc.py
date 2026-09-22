import re
import winreg
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from core.utils import parse_version

UNINSTALL_KEY = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
BUSINESS_DOC_KEY = r"SOFTWARE\IntellectService"
DISPLAY_NAME_RE = re.compile(r"medoc|m\.e\.doc", re.IGNORECASE)
INSTANCE_NUMBER_RE = re.compile(r"Medoc_(\d+)", re.IGNORECASE)
DB_RELATIVE = ("db", "ZVIT.FDB")
GFIX_EXE = "gfix.exe"
NO_SERVICE = "-1"


@dataclass(frozen=True)
class Medoc:
    # immutable snapshot of an installed instance; after installing an
    # update, build a new value with dataclasses.replace(medoc, ...)
    # instead of assigning to fields
    name: str
    path: Path
    major: int
    minor: int
    build: int
    instance_type: str  # "network" | "local"
    instance_number: int
    gfix_path: Optional[Path]
    db_path: Optional[Path]
    service_name: Optional[str]

    @property
    def version(self) -> str:
        # e.g. "11.2.209"
        return f"{self.major}.{self.minor}.{self.build}"

    @property
    def fullname(self) -> str:
        # matches the GUI list text, e.g. "11.02.209 - C:\...\Medoc_3SRV"
        return f"{self.major:02}.{self.minor:02}.{self.build:03} - {self.path}"


def _reg_value(key, name: str, default: str = "") -> str:
    # read a single registry value, default if missing
    try:
        return winreg.QueryValueEx(key, name)[0]
    except FileNotFoundError:
        return default


def _read_uninstall_entries() -> Dict[str, str]:
    # installed M.E.Doc entries: InstallLocation -> DisplayVersion
    entries: Dict[str, str] = {}
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
    except FileNotFoundError:
        return entries

    with root:
        count = winreg.QueryInfoKey(root)[0]
        for i in range(count):
            subkey_name = winreg.EnumKey(root, i)
            with winreg.OpenKey(root, subkey_name) as subkey:
                display_name = _reg_value(subkey, "DisplayName")
                if not DISPLAY_NAME_RE.search(display_name):
                    continue
                version = _reg_value(subkey, "DisplayVersion")
                install_location = _reg_value(subkey, "InstallLocation")
                if not version or not install_location:
                    continue
                entries[install_location] = version
    return entries


def _read_business_doc_entries() -> Dict[str, dict]:
    # BusinessDocN entries: PATH -> service/db fields
    entries: Dict[str, dict] = {}
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, BUSINESS_DOC_KEY)
    except FileNotFoundError:
        return entries

    with root:
        count = winreg.QueryInfoKey(root)[0]
        for i in range(count):
            subkey_name = winreg.EnumKey(root, i)
            if not subkey_name.startswith("BusinessDoc"):
                continue
            with winreg.OpenKey(root, subkey_name) as subkey:
                path = _reg_value(subkey, "PATH")
                if not path:
                    continue
                entries[path] = {
                    "appdata": _reg_value(subkey, "APPDATA"),
                    "service_name": _reg_value(subkey, "ServiceName"),
                    "fb_path": _reg_value(subkey, "fbPath"),
                }
    return entries


def read_registry() -> List[dict]:
    # Uninstall + IntellectService\BusinessDoc*, joined by PATH == InstallLocation
    uninstall_entries = _read_uninstall_entries()
    business_entries = _read_business_doc_entries()

    raw = []
    for path, version in uninstall_entries.items():
        business = business_entries.get(path, {})
        raw.append({
            "path": path,
            "version": version,
            "appdata": business.get("appdata", ""),
            "service_name": business.get("service_name", ""),
            "fb_path": business.get("fb_path", ""),
        })
    return raw


def get_instance_number(path: Path) -> int:
    # Medoc_13SRV -> 13, defaults to 1
    match = INSTANCE_NUMBER_RE.search(path.name)
    return int(match.group(1)) if match else 1


def is_network_instance(service_name: Optional[str]) -> bool:
    # True if ServiceName is a real value, not "-1" or empty
    return bool(service_name) and service_name != NO_SERVICE


def build_medoc(raw: dict) -> Medoc:
    # raw registry entry -> Medoc
    path = Path(raw["path"])
    major, minor, build = parse_version(raw["version"])
    service_name = raw.get("service_name")
    network = is_network_instance(service_name)

    fb_path = raw.get("fb_path")
    appdata = raw.get("appdata")

    return Medoc(
        name=path.name,
        path=path,
        major=major,
        minor=minor,
        build=build,
        instance_type="network" if network else "local",
        instance_number=get_instance_number(path),
        gfix_path=Path(fb_path) / GFIX_EXE if network and fb_path else None,
        db_path=Path(appdata).joinpath(*DB_RELATIVE) if network and appdata else None,
        service_name=service_name if network else None,
    )


def discover_medocs() -> List[Medoc]:
    # registry -> list of installed Medoc instances
    return [build_medoc(raw) for raw in read_registry()]
