"""Validate both identifiers for one archived OCI image, without extracting it."""
from hashlib import sha256
import json, re, sys, tarfile

DIGEST = re.compile(r'sha256:[a-f0-9]{64}\Z')


def validate(path, hosted_id, loaded_id, revision):
    with tarfile.open(path, 'r:*') as archive:
        def read(name):
            f=archive.extractfile(name)
            if f is None:
                raise ValueError('missing image metadata')
            data=f.read(1_000_001)
            if len(data)>1_000_000:
                raise ValueError('oversized image metadata')
            return data
        def blob(digest):
            if not DIGEST.fullmatch(digest):
                raise ValueError('invalid image digest')
            raw=read('blobs/sha256/'+digest.split(':')[1])
            if 'sha256:'+sha256(raw).hexdigest()!=digest:
                raise ValueError('wrong image metadata digest')
            return json.loads(raw)
        [descriptor] = json.loads(read('index.json'))['manifests']
        manifest_id=descriptor['digest']
        config_id=blob(manifest_id)['config']['digest']
        config=blob(config_id)
        if (hosted_id not in (manifest_id, config_id) or loaded_id not in (manifest_id, config_id)
                or config['architecture']!='arm64'
                or config['config']['Labels']['org.opencontainers.image.revision']!=revision):
            raise ValueError('loaded image is not the hosted-tested ARM64 image')
    return loaded_id


if __name__=='__main__':
    if len(sys.argv)!=5:
        raise SystemExit('usage: check-oci-image.py ARCHIVE HOSTED_ID LOADED_ID SHA')
    print(validate(*sys.argv[1:]))
