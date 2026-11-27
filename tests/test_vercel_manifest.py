"""The deployed function installs from pyproject, not the Mac test environment."""
from pathlib import Path
import tomllib
import unittest

ROOT=Path(__file__).resolve().parents[1]

class CloudManifest(unittest.TestCase):
    def test_cloud_entry_builds_with_pinned_runtime_dependency_metadata(self):
        metadata=tomllib.loads((ROOT/'pyproject.toml').read_text())
        self.assertEqual(metadata['tool']['vercel']['entrypoint'],'vercel_app:app')
        self.assertEqual(metadata['project']['requires-python'],'>=3.12,<3.13')
        installed={value.split('==')[0] for value in metadata['project']['dependencies'] if '==' in value}
        self.assertTrue({'fastapi','uvicorn','pydantic','pypdf','openpyxl'}<=installed)

if __name__=='__main__':
    unittest.main()
