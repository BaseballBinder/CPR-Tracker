"""
Application configuration with environment variable support.
Supports both development mode and PyInstaller frozen mode.
"""
import os
from pathlib import Path
from functools import lru_cache

from app.desktop_config import get_bundle_dir, get_appdata_dir
from app.service_context import get_active_service_dir


# Base directory for bundled assets (templates, static files)
BASE_DIR = get_bundle_dir()


class Settings:
    """Application settings - resolves paths based on active service context."""

    def __init__(self):
        service_dir = get_active_service_dir()

        if service_dir:
            # Desktop mode: resolve from active service's AppData directory
            self.canroc_master_template_path: Path = Path(
                os.getenv("CANROC_MASTER_TEMPLATE_PATH",
                           str(service_dir / "templates_canroc" / "1.Master_CanROC_Sheet_Update_August 2025.xlsx"))
            )
            self.canroc_pco_template_path: Path = Path(
                os.getenv("CANROC_PCO_TEMPLATE_PATH",
                           str(service_dir / "templates_canroc" / "4. CanROC_Variables_PCO_Files_Master_Update_June2025.xlsx"))
            )
            self.export_output_dir: Path = Path(
                os.getenv("EXPORT_OUTPUT_DIR", str(service_dir / "exports"))
            )
            self.upload_tmp_dir: Path = Path(
                os.getenv("UPLOAD_TMP_DIR", str(service_dir / "uploads"))
            )
        else:
            # Dev mode / no service selected: use project-relative paths
            self.canroc_master_template_path: Path = Path(
                os.getenv("CANROC_MASTER_TEMPLATE_PATH",
                           str(BASE_DIR / "templates_canroc" / "1.Master_CanROC_Sheet_Update_August 2025.xlsx"))
            )
            self.canroc_pco_template_path: Path = Path(
                os.getenv("CANROC_PCO_TEMPLATE_PATH",
                           str(BASE_DIR / "templates_canroc" / "4. CanROC_Variables_PCO_Files_Master_Update_June2025.xlsx"))
            )
            self.export_output_dir: Path = Path(
                os.getenv("EXPORT_OUTPUT_DIR", str(BASE_DIR / "exports"))
            )
            self.upload_tmp_dir: Path = Path(
                os.getenv("UPLOAD_TMP_DIR", str(BASE_DIR / "uploads"))
            )

        self._ensure_directories()

    def _ensure_directories(self):
        """Create required directories if they don't exist."""
        self.export_output_dir.mkdir(parents=True, exist_ok=True)
        self.upload_tmp_dir.mkdir(parents=True, exist_ok=True)
        self.canroc_master_template_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
