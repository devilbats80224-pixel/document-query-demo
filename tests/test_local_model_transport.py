import os, unittest
from pathlib import Path
from unittest.mock import patch

import local_models


class LocalModelTransportTests(unittest.TestCase):
    def test_default_model_only_uses_mac_loopback(self):
        with patch.dict(os.environ, {}, clear=True):
            host, token = local_models._transport()
            self.assertEqual(host, '127.0.0.1')
            self.assertEqual(token, local_models.BASE_DIR/'loopback-token')

    def test_docker_can_only_use_fixed_host_and_mounted_secret(self):
        with patch.dict(os.environ, {'LITEON_MODEL_TRANSPORT':'docker-desktop',
                                     'LITEON_MODEL_HOST':'attacker.invalid'}, clear=True):
            self.assertEqual(local_models._transport(),
                             ('host.docker.internal', Path('/run/secrets/demo-model-token')))

    def test_unknown_transport_cannot_route_to_arbitrary_host(self):
        with patch.dict(os.environ, {'LITEON_MODEL_TRANSPORT':'https://attacker.invalid'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'invalid_local_model_transport'):
                local_models._transport()
