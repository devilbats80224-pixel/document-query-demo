from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import runpy, tarfile, tempfile
from unittest import TestCase

validate = runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/check-oci-image.py'))['validate']


class OCIIdentity(TestCase):
    def test_exact_config_and_manifest_are_valid_not_an_unrelated_id(self):
        revision='a'*40
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'image.tar.gz'
            with tarfile.open(path,'w:gz') as archive:
                def add(name, item):
                    raw=json.dumps(item).encode()
                    digest=sha256(raw).hexdigest()
                    meta=tarfile.TarInfo(name or 'blobs/sha256/'+digest)
                    meta.size=len(raw)
                    archive.addfile(meta,BytesIO(raw))
                    return 'sha256:'+digest
                config=add(None,{'architecture':'arm64','config':{'Labels':{'org.opencontainers.image.revision':revision}}})
                manifest=add(None,{'config':{'digest':config}})
                add('index.json',{'manifests':[{'digest':manifest}]})
            self.assertEqual(validate(path,config,manifest,revision),manifest)
            self.assertEqual(validate(path,config,config,revision),config)
            with self.assertRaisesRegex(ValueError,'not the hosted-tested'):
                validate(path,config,'sha256:'+'0'*64,revision)
            with self.assertRaisesRegex(ValueError,'not the hosted-tested'):
                validate(path,config,manifest,'b'*40)
