"""
Wrenify — Thread-safe In-App Updater & Downloader.

Checks version and downloads updates directly inside Wrenify.
Preserves user data (songs, recordings, models, .env).
"""

from __future__ import annotations

import configparser
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from loguru import logger

from wrenify.core.config import ROOT_DIR


CONFIG_KOUSHIN_PATH = ROOT_DIR / "config.koushin"
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/MrRishabThapa/Wrenify/master/config.koushin"


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    has_update: bool
    changelog: str
    repo_url: str
    download_url: str


class KoushinEngine:
    """Handles update checks and in-place code package downloading."""

    def __init__(self, local_config_path: Path = CONFIG_KOUSHIN_PATH) -> None:
        self.local_config_path = local_config_path
        self.current_version = self._get_local_version()

    def _get_local_version(self) -> str:
        if not self.local_config_path.exists():
            return "0.1.0"
        try:
            config = configparser.ConfigParser()
            config.read(self.local_config_path)
            return config.get("version", "version", fallback="0.1.0")
        except Exception as e:
            logger.warning(f"Could not read local config.koushin: {e}")
            return "0.1.0"

    def check_for_updates(self) -> UpdateInfo:
        logger.info(f"Checking for updates... (Local: v{self.current_version})")
        try:
            req = urllib.request.Request(
                REMOTE_CONFIG_URL,
                headers={"User-Agent": "Wrenify-Updater"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                content = response.read().decode("utf-8")

            remote_config = configparser.ConfigParser()
            remote_config.read_string(content)

            latest_version = remote_config.get("version", "version", fallback=self.current_version)
            changelog = remote_config.get("changelog", "notes", fallback="Performance improvements and bug fixes.")
            repo_url = remote_config.get("github", "repo", fallback="https://github.com/MrRishabThapa/Wrenify")
            download_url = remote_config.get(
                "download", "download_url", 
                fallback=f"{repo_url}/archive/refs/heads/master.zip"
            )

            has_update = self._is_newer_version(self.current_version, latest_version)

            return UpdateInfo(
                current_version=self.current_version,
                latest_version=latest_version,
                has_update=has_update,
                changelog=changelog,
                repo_url=repo_url,
                download_url=download_url,
            )
        except Exception as e:
            logger.warning(f"Failed to check for updates: {e}")
            return UpdateInfo(
                current_version=self.current_version,
                latest_version=self.current_version,
                has_update=False,
                changelog="",
                repo_url="",
                download_url="",
            )

    @staticmethod
    def _is_newer_version(current: str, latest: str) -> bool:
        def parse_ver(v_str: str) -> tuple[int, ...]:
            clean = v_str.lstrip("v").strip()
            return tuple(int(x) for x in clean.split(".") if x.isdigit())

        try:
            return parse_ver(latest) > parse_ver(current)
        except Exception:
            return latest != current


class UpdateCheckWorker(QObject):
    finished = pyqtSignal(object)

    def run(self) -> None:
        engine = KoushinEngine()
        info = engine.check_for_updates()
        self.finished.emit(info)


class UpdateDownloadWorker(QObject):
    """
    Downloads the update zip in a background thread and updates app files.
    PRESERVES: songs/, recordings/, models/, .env
    """

    # Signals: (progress_percent, bytes_downloaded, total_bytes, speed_str)
    progress = pyqtSignal(float, int, int, str)
    status_changed = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, download_url: str) -> None:
        super().__init__()
        self.download_url = download_url
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        try:
            self.status_changed.emit("Connecting to download server...")
            temp_zip = ROOT_DIR / "update_temp.zip"

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "Wrenify-InApp-Downloader"}
            )

            start_time = time.time()
            with urllib.request.urlopen(req, timeout=15) as response:
                total_size = int(response.info().get("Content-Length", 0))
                bytes_downloaded = 0
                block_size = 65536  # 64KB chunks

                with open(temp_zip, "wb") as f:
                    while True:
                        if self._is_cancelled:
                            self.status_changed.emit("Download cancelled.")
                            if temp_zip.exists():
                                temp_zip.unlink()
                            self.finished.emit(False, "Cancelled")
                            return

                        buffer = response.read(block_size)
                        if not buffer:
                            break

                        bytes_downloaded += len(buffer)
                        f.write(buffer)

                        elapsed = time.time() - start_time
                        speed_mbps = (bytes_downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        speed_str = f"{speed_mbps:.1f} MB/s"

                        percent = (bytes_downloaded / total_size * 100) if total_size > 0 else 50.0
                        self.progress.emit(percent, bytes_downloaded, total_size, speed_str)

            self.status_changed.emit("Extracting update files...")
            self._apply_update(temp_zip)

            if temp_zip.exists():
                temp_zip.unlink()

            self.status_changed.emit("Update complete! Ready to restart.")
            self.finished.emit(True, "Success")

        except Exception as e:
            logger.error(f"In-app update download failed: {e}")
            self.finished.emit(False, str(e))

    def _apply_update(self, zip_path: Path) -> None:
        """Extract zip and overwrite code files, keeping user data intact."""
        extract_dir = ROOT_DIR / "update_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        # Zip root is usually Wrenify-master/
        source_root = extract_dir
        subdirs = list(extract_dir.iterdir())
        if len(subdirs) == 1 and subdirs[0].is_dir():
            source_root = subdirs[0]

        # Copy over code files ONLY, ignoring user data
        PROTECTED_NAMES = {"songs", "recordings", "models", ".env", ".venv"}

        for item in source_root.iterdir():
            if item.name in PROTECTED_NAMES:
                logger.info(f"Preserving user directory: {item.name}")
                continue

            target = ROOT_DIR / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

        if extract_dir.exists():
            shutil.rmtree(extract_dir)