from datetime import datetime
from decimal import Decimal
import unittest
from unittest.mock import patch

import cloud_sessions


class SimulatedRedis(cloud_sessions.RedisSessionBackend):
    def __init__(self, slots):
        self.slots=slots

    def command(self, *items):
        if items[0]=="GET":
            return self.slots.get(items[1])
        if items[0]=="DEL":
            return int(self.slots.pop(items[1],None) is not None)
        lua,arity,key,expected,encoded,ttl=items[1:]
        assert "redis.call('GET'" in lua
        assert arity==1 and ttl==7200
        if self.slots.get(key,"")!=expected:
            return 0
        self.slots[key]=encoded
        return 1


class CloudSessions(unittest.TestCase):
    def test_cross_instance_data_and_browser_partition(self):
        cells={}
        first=SimulatedRedis(cells)
        other=SimulatedRedis(cells)
        data={"a.xlsx":{"cells":[Decimal("1.21"),datetime(2026,11,27),{"_cloud_type":"user"}]}}
        sid=first.new_id()
        first.update("table",sid,lambda old:data)
        self.assertEqual(other.read("table",sid),data)
        self.assertIsNone(other.read("documents",sid))
        self.assertIsNone(other.read("table",other.new_id()))
        other.delete("table",sid)
        self.assertIsNone(first.read("table",sid))

    def test_rejects_unsafe_store_configuration_by_default(self):
        with patch.dict("os.environ",{"UPSTASH_REDIS_REST_URL":"https://evil.example","UPSTASH_REDIS_REST_TOKEN":"not-real"},clear=True):
            self.assertIsNone(cloud_sessions.backend())
