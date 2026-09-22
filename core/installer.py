import time
from pathlib import Path

from loguru import logger
from pywinauto import Desktop, timings

from core.utils import run_command

DEFAULT_TIMEOUT = 1800
# the success window can't be closed right after the success pane appears,
# has to be a real wait, not just a UI quirk we can query for
CLOSE_DELAY_SECONDS = 30


def _set_ui_timeouts(timeout: int) -> None:
    timings.Timings.window_find_timeout = timeout
    timings.Timings.exists_timeout = timeout


def _select_window(title: str):
    dlg = Desktop(backend="uia").window(title_re=title)
    dlg.wait("exists")
    return dlg


def _launch_update(update_exec_path: Path) -> None:
    pwh_command = f"$p = Start-Process '{update_exec_path}' -PassThru; echo $p.id"
    pid_str = run_command(["powershell", "-Command", pwh_command])
    try:
        int(pid_str.strip())
    except ValueError:
        raise RuntimeError(f"Installer did not return a valid PID: {pid_str}")


def _confirm_init_dialog() -> None:
    dlg = _select_window("Оновлення програми")
    btn = dlg.child_window(auto_id="btOK", control_type="Button")
    btn.wait("exists")
    btn.click()


def _select_medoc_instance(medoc_name: str) -> None:
    dlg = _select_window("Вибір програми для оновлення")
    list_medocs = dlg.child_window(auto_id="lbZvits", control_type="List")
    item = list_medocs.child_window(title=medoc_name)
    item.wait("exists")
    item.set_focus()
    item.click_input()
    btn = dlg.child_window(auto_id="btnNext", control_type="Button")
    btn.wait("exists")
    btn.click()


def _wait_success() -> None:
    dlg = _select_window("Оновлення програми")
    success_pane = dlg.child_window(title="Оновлення програми виконано успішно", control_type="Pane")
    success_pane.wait("exists")
    time.sleep(CLOSE_DELAY_SECONDS)
    dlg.close()


def install_update(medoc_name: str, update_exec_path: Path, timeout: int = DEFAULT_TIMEOUT) -> None:
    # runs the update installer through its GUI for one medoc instance;
    # raises on any failure, returns normally on success
    logger.info(f"Installing {update_exec_path.name} for {medoc_name}")
    _set_ui_timeouts(timeout)
    _launch_update(update_exec_path)
    _confirm_init_dialog()
    _select_medoc_instance(medoc_name)
    _wait_success()
    logger.success(f"Installed {update_exec_path.name} for {medoc_name}")
