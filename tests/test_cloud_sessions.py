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
        if self.slots.get(key,"")[:32]!=expected:
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

    def test_previous_large_state_is_not_sent_again_in_compare_and_set(self):
        slots={}
        payload_sizes=[]
        class Measured(SimulatedRedis):
            def command(self,*items):
                if items[0]=="EVAL":
                    import json
                    payload_sizes.append(len(json.dumps(items,ensure_ascii=False).encode("utf-8")))
                return super().command(*items)
        connection=Measured(slots)
        sid=connection.new_id()
        payload={"d":("\\\\"*860_000)}
        connection.update("table",sid,lambda _:payload)
        connection.update("table",sid,lambda _:payload)
        self.assertLess(max(payload_sizes),8_000_000)

    def test_reset_cannot_be_undone_by_a_late_write_retry(self):
        slots={}
        class Resetting(SimulatedRedis):
            triggered=False
            def command(self,*items):
                if items[0]=="EVAL" and not self.triggered and items[4]:
                    self.triggered=True
                    self.slots.pop(items[3],None)
                return super().command(*items)
        connection=Resetting(slots)
        sid=connection.new_id()
        connection.update("documents",sid,lambda _:{"doc":1})
        with self.assertRaises(cloud_sessions.CloudStorageError):
            connection.update("documents",sid,lambda _:{"doc":2})
        self.assertIsNone(connection.read("documents",sid))
