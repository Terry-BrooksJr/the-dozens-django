# -*- coding: utf-8 -*-
from cacheops.signals import cache_read
from statsd.defaults.django import statsd
from prometheus_client import Counter


def stats_collector(sender, func, hit, **kwargs):
    event = "hit" if hit else "miss"
    statsd.incr("cacheops.%s" % event)


cache_read.connect(stats_collector)
