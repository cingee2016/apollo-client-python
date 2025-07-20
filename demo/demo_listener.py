#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com
import os
import time

from apollo.apollo_client import ApolloClient

apollo_config_url = os.environ.get("APOLLO_CONFIG_URL")

print(apollo_config_url)


# {'action': 'update', 'namespace': 'application', 'key': 'infra.redis.database', 'value': '1', 'old_value': '0'}
# {'action': 'add', 'namespace': 'application', 'key': 'infra.redis.database', 'value': '1', 'old_value': None}
# {'action': 'delete', 'namespace': 'application', 'key': 'infra.redis.database', 'value': None, 'old_value': '0'}
def listener(event):
    print(event)


client = ApolloClient(
    app_id="demo-service",
    cluster="default",
    config_url=apollo_config_url,
    value_change_listeners=[listener],
)
client.start()
val = client.get_value("name", default_val="defaultVal")

print(val)
time.sleep(100)
