"""Local browser CI only; do not deploy this fixture."""
from unittest.mock import Mock
from test_cloud_sessions import SimulatedRedis
import cloud_sessions
from vercel_app import app

_slots = {}
cloud_sessions.backend = Mock(side_effect=lambda:SimulatedRedis(_slots))
