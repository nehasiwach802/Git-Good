"""Explicit deployment configuration. No secrets are logged or loaded on import."""
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path('data')
    catalog_path: Path = Path(__file__).with_name('catalog.json')
    firebase_project: str = ''
    vision_enabled: bool = True
    worker_enabled: bool = True
    memory_scopes_file: str = ''
    qwen_enabled: bool = True

    @classmethod
    def from_env(cls):
        return cls(data_dir=Path(os.getenv('DATA_DIR', 'data')),
                   catalog_path=Path(os.getenv('EXPERIMENT_CATALOG_PATH', str(Path(__file__).with_name('catalog.json')))),
                   firebase_project=os.getenv('FIREBASE_PROJECT_ID', ''),
                   vision_enabled=os.getenv('VISION_ENABLED', 'true').lower() == 'true',
                   worker_enabled=os.getenv('WORKER_ENABLED', 'true').lower() == 'true',
                   memory_scopes_file=os.getenv('MEMORY_SCOPES_FILE', ''),
                   qwen_enabled=os.getenv('QWEN_ENABLED', 'true').lower()=='true')
