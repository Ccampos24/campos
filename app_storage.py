import os
import shutil


def get_app_data_dir():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(local_app_data, "Campos Tecnologia", "Campos Defenser")


def migrate_legacy_app_data(legacy_dir, app_data_dir):
    legacy_path = os.path.abspath(legacy_dir)
    target_path = os.path.abspath(app_data_dir)

    if os.path.normcase(legacy_path) == os.path.normcase(target_path) or not os.path.isdir(legacy_path):
        return

    def copy_if_missing(source, destination):
        if os.path.exists(destination):
            return destination
        return shutil.copy2(source, destination)

    try:
        shutil.copytree(
            legacy_path,
            target_path,
            dirs_exist_ok=True,
            copy_function=copy_if_missing
        )
    except OSError as exc:
        raise OSError(
            f"Não foi possível preservar os dados locais de '{legacy_path}' em '{target_path}': {exc}"
        ) from exc
