import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from backend.config import Settings
from backend.preflight import check
from backend.catalog import load_catalog


class DeploymentTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        self.settings=Settings(data_dir=Path(self.directory.name),firebase_project='synthetic-project',vision_enabled=False,qwen_enabled=False)
        self.catalog=load_catalog(self.settings.catalog_path)

    def tearDown(self):self.directory.cleanup()

    def report(self,**kwargs):
        with patch.dict(os.environ,{},clear=True),patch('backend.preflight.find_ngspice',return_value='synthetic-solver'):
            return check(self.settings,catalog=self.catalog,**kwargs)

    def test_missing_credentials_fail_closed_without_secret_values(self):
        result=self.report()
        self.assertEqual(result['status'],'not_ready')
        self.assertFalse(result['checks']['firebase_credentials'])
        self.assertNotIn('synthetic-project',str(result))

    def test_integration_ready_with_injected_auth_but_not_production_catalog(self):
        self.assertEqual(self.report(authenticated=True)['status'],'ready')
        strict=self.report(authenticated=True,production=True)
        self.assertEqual(strict['status'],'not_ready')
        self.assertFalse(strict['checks']['approved_real_experiments'])

    def test_approved_catalog_and_worker_are_required(self):
        record=next(iter(self.catalog.values()))
        record.update(workflow_approved=True,simulated=False)
        self.assertEqual(self.report(authenticated=True,production=True)['status'],'ready')
        self.settings=replace(self.settings,worker_enabled=False)
        self.assertFalse(self.report(authenticated=True)['checks']['worker'])

    def test_enabled_provider_requires_configuration(self):
        self.settings=replace(self.settings,vision_enabled=True)
        self.assertFalse(self.report(authenticated=True)['checks']['vision_configuration'])
