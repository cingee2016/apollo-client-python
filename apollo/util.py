#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com

import hashlib
import logging
import os
import socket
import urllib.request
from urllib import parse
from urllib.error import HTTPError

# 定义常量
CONFIGURATIONS = "configurations"
NOTIFICATION_ID = "notificationId"
NAMESPACE_NAME = "namespaceName"


def http_request(url, timeout, headers=None):
    try:
        request = urllib.request.Request(
            url, headers=headers if headers is not None else {}
        )
        res = urllib.request.urlopen(request, timeout=timeout)
        body = res.read().decode("utf-8")
        return res.code, body
    except HTTPError as e:
        if e.code == 304:
            return 304, None
        logging.error("http_request error,code is %d, msg is %s", e.code, e.msg, e)
        raise e


def url_encode(params):
    return parse.urlencode(params)


def makedirs_wrapper(path):
    os.makedirs(path, exist_ok=True)


# 对时间戳，uri，秘钥进行加签
def signature(timestamp, uri, secret):
    import hmac
    import base64

    string_to_sign = "" + timestamp + "\n" + uri
    hmac_code = hmac.new(
        secret.encode(), string_to_sign.encode(), hashlib.sha1
    ).digest()
    return base64.b64encode(hmac_code).decode()


def url_encode_wrapper(params):
    return url_encode(params)


# 返回是否获取到的值，不存在则返回None
def get_value_from_dict(namespace_cache, key):
    if namespace_cache:
        kv_data = namespace_cache.get(CONFIGURATIONS)
        if kv_data is None:
            return None
        if key in kv_data:
            return kv_data[key]
    return None


# 返回是否获取到的值，不存在则返回None
def get_config_dict(namespace_cache):
    if namespace_cache:
        kv_data = namespace_cache.get(CONFIGURATIONS)
        return kv_data
    return None


def init_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        return ip


__all__ = [
    "CONFIGURATIONS",
    "NOTIFICATION_ID",
    "NAMESPACE_NAME",
    "signature",
    "url_encode_wrapper",
    "get_value_from_dict",
    "init_ip",
    "get_config_dict",
    "http_request",
    "url_encode_wrapper",
    "makedirs_wrapper",
]
