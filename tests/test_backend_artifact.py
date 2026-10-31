"""Catch modules available in checkout but absent from the deployed artifact."""
from pathlib import Path
import shlex
import json
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class DeploymentArtifactTests(unittest.TestCase):
    def test_docker_copy_manifest_boots_without_checkout_imports(self):
        root=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            target=Path(directory)
            for line in (root/'Dockerfile.backend').read_text().splitlines():
                if not line.startswith('COPY '):continue
                tokens=shlex.split(line)[1:]
                for source in tokens[:-1]:
                    original=root/source
                    if original.is_dir():
                        shutil.copytree(original,target/tokens[-1],dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
                    else:
                        destination=target/tokens[-1]
                        destination.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(original,destination/original.name)
            # Keep installed dependency directories, including a system-site-packages
            # venv's user dependencies, while excluding all checkout import paths.
            dependencies=[p for p in sys.path if Path(p).name in ('site-packages','dist-packages')]
            script="import sys,json; from pathlib import Path; sys.path.extend(json.loads(sys.argv[2])); sys.path.insert(0,sys.argv[1]); from backend.app import app; assert app.openapi()['info']['version']=='1.0.0'; import ml3_http; assert Path(ml3_http.__file__).parent==Path(sys.argv[1])"
            result=subprocess.run([sys.executable,'-I','-c',script,str(target),json.dumps(dependencies)],cwd=target,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
