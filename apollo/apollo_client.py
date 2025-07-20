#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time:2020.09.12
# @author:xhrg
# @email:634789257@qq.com
import hashlib
import json
import logging
import os
import threading
import time

from .util import (
    init_ip,
    CONFIGURATIONS,
    get_value_from_dict,
    NOTIFICATION_ID,
    NAMESPACE_NAME,
    url_encode_wrapper,
    signature,
    get_config_dict,
    http_request,
    makedirs_wrapper,
)


def _set_basic_logging():
    logging.basicConfig(
        format="%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%d-%m-%Y:%H:%M:%S",
        level=logging.DEBUG,
    )


_debug_flag = False


class ApolloClient(object):
    _instances = {}
    _create_client_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        key = f"{args},{sorted(kwargs.items())}"
        with cls._create_client_lock:
            if key not in cls._instances:
                cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(
        self,
        config_url: str = None,
        app_id: str = None,
        namespaces: list = None,
        cluster=None,
        secret=None,
        enable_scheduled_updates=True,
        enable_long_pool_updates=False,
            auto_update_enabled=False,
        value_change_listeners=None,
    ):
        # 核心参数
        self._config_url = config_url
        self._cluster = cluster
        self._app_id = app_id

        # 鉴权参数
        self.ip = init_ip()
        self._secret = secret

        # 更新参数
        self._use_scheduled_update = enable_scheduled_updates
        self._use_long_pool_update = enable_long_pool_updates
        self._long_poll_thread = None
        self._scheduled_update_thread = None
        self._value_change_listeners = value_change_listeners  # "add" "delete" "update"
        if self._value_change_listeners is None:
            self._value_change_listeners = []

        # 私有控制变量
        self._cycle_time = 2
        self._update_stopped = True
        self._cache = {}
        self._hash = {}
        self._pull_timeout = 75
        self._cache_file_path = os.path.expanduser("~") + "/data/apollo/cache/"
        self._update_cache_lock = threading.Lock()
        self._update_cache_and_file_lock = threading.Lock()


        self._namespaces = namespaces

        # 环境变量
        self._load_environment()

        # 加载前准备
        self._notification_map = {}
        for namespace in namespaces:
            self._notification_map[namespace] = -1

        # 客户端加载
        self._is_apollo_client_inited = False
        self._path_checker()
        self.update_configs()
        if auto_update_enabled:
            self.start()
        self._is_apollo_client_inited = True

    def _load_environment(self):
        env = os.environ
        if self._config_url is None:
            if 'APOLLO_META_SERVER_ADDRESS' in env:
                self._config_url = env['APOLLO_META_SERVER_ADDRESS']
            else:
                raise RuntimeError("APOLLO_META_SERVER_ADDRESS environment variable not set")
        if self._app_id is None:
            if 'APOLLO_APP_ID' in env:
                self._app_id = env['APOLLO_APP_ID']
            else:
                raise RuntimeError("APOLLO_APP_ID environment variable not set")
        if self._cluster is None:
            if 'APOLLO_CLUSTER' in env:
                self._cluster = env['APOLLO_CLUSTER']
            else:
                self._cluster = 'default'
        if self._namespaces is None:
            if 'APOLLO_NAMESPACES' in env:
                self._namespaces = env['APOLLO_NAMESPACES'].split(',')
            else:
                self._namespaces = ['application']
        if self._secret is None:
            if 'APOLLO_APP_SECRET' in env:
                self._secret = env['APOLLO_APP_SECRET']
            else:
                self._secret = ''


    def start(self):
        self._update_stopped = False
        if self._use_scheduled_update:
            self._start_scheduled_update()
        if self._use_long_pool_update:
            self._start_long_poll_update()

    def stop(self):
        self._update_stopped = True
        logging.info("Stopping listener...")

    def add_value_change_listener(self, listener):
        self._value_change_listeners.append(listener)

    def _start_scheduled_update(self):
        self._scheduled_update_thread = threading.Thread(
            target=self._scheduled_update_loop
        )
        self._scheduled_update_thread.daemon = True
        self._scheduled_update_thread.start()

    def _scheduled_update_loop(self):
        while not self._update_stopped:
            for namespace in self._notification_map:
                self.update_configs()
            time.sleep(60 * 10)  # 10分钟

    def update_configs(self):
        for namespace in self._notification_map.keys():
            # 读取网络配置
            namespace_data = self._get_json_from_net(namespace)
            if namespace_data is not None:
                self._update_cache_and_file(namespace_data, namespace)
            else:
                # 读取文件配置
                namespace_disk = self._get_json_from_local_cache(namespace)
                if namespace_disk is not None:
                    self._update_cache(namespace_disk, namespace)

    def get_value(self, key, default_val=None, namespace="application"):
        # 读取内存配置
        namespace_cache = self._cache.get(namespace)
        val = get_value_from_dict(namespace_cache, key)
        if val is not None:
            return self._convert_type(val)
        return self._convert_type(default_val)

    def get_config(self, namespace="application"):
        # 读取内存配置
        namespace_cache = self._cache.get(namespace)
        config_dict = get_config_dict(namespace_cache)
        if config_dict is not None:
            return config_dict
        # 如果全部没有获取，返回None
        return None

    @staticmethod
    def _convert_type(value):
        return value

    # 给header增加加签需求
    def _sign_headers(self, url):
        headers = {}
        if self._secret == "":
            return headers
        uri = url[len(self._config_url): len(url)]
        time_unix_now = str(int(round(time.time() * 1000)))
        headers["Authorization"] = (
            "Apollo " + self._app_id + ":" + signature(time_unix_now, uri, self._secret)
        )
        headers["Timestamp"] = time_unix_now
        return headers

    def _path_checker(self):
        if not os.path.isdir(self._cache_file_path):
            makedirs_wrapper(self._cache_file_path)

    def _get_json_from_net(self, namespace="application"):
        url = "{}/configs/{}/{}/{}?releaseKey={}&ip={}".format(
            self._config_url, self._app_id, self._cluster, namespace, "", self.ip
        )
        try:
            code, body = http_request(url, timeout=3, headers=self._sign_headers(url))
            if code == 200:
                data = json.loads(body)
                return data
            else:
                return None
        except Exception as e:
            logging.error("_get_json_from_net Exception", e)
            return None

    # 从本地文件获取配置
    def _get_json_from_local_cache(self, namespace="application"):
        cache_file_path = os.path.join(
            self._cache_file_path, "%s_configuration_%s.txt" % (self._app_id, namespace)
        )
        if os.path.isfile(cache_file_path):
            with open(cache_file_path, "r") as f:
                line = f.readline()
                if line:
                    data = json.loads(line)
                    return data
        return {}

    # 更新本地缓存
    def _update_cache(self, namespace_data, namespace="application"):
        with self._update_cache_lock:
            # 更新本地缓存
            current_data = self._cache.get(namespace)
            if current_data is None:
                current_data = {"releaseKey": "-1", CONFIGURATIONS: {}}
            if current_data["releaseKey"]  == "-1" or current_data["releaseKey"]  != namespace_data["releaseKey"]:
                if _debug_flag:
                    logging.info("Updating cache...")
                self._cache[namespace] = namespace_data
                if self._is_apollo_client_inited:
                    self._notify_change(
                        namespace,
                        current_data.get(CONFIGURATIONS),
                        namespace_data.get(CONFIGURATIONS),
                    )
                return True
            if _debug_flag:
                logging.info("Updating cache... no change...")
            return False

    # 更新本地缓存和文件缓存
    def _update_cache_and_file(self, namespace_data, namespace="application"):
        with self._update_cache_and_file_lock:
            # 更新本地缓存
            updated = self._update_cache(namespace_data, namespace)
            # 更新文件缓存
            if updated:
                new_string = json.dumps(namespace_data)
                new_hash = hashlib.md5(new_string.encode("utf-8")).hexdigest()
                if self._hash.get(namespace) == new_hash:
                    pass
                else:
                    with open(
                            os.path.join(
                                self._cache_file_path,
                                "%s_configuration_%s.txt" % (self._app_id, namespace),
                            ),
                            "w",
                    ) as f:
                        f.write(new_string)
                        f.flush()
                    self._hash[namespace] = new_hash

    def _handle_change_listeners(self, change_event):
        for change_listener in self._value_change_listeners:
            change_listener(change_event)

    # 调用设置的回调函数，如果异常，直接try掉
    def _notify_change(self, namespace, old_kv, new_kv):
        if self._value_change_listeners is None:
            return
        if len(self._value_change_listeners) == 0:
            return
        if old_kv is None:
            old_kv = {}
        if new_kv is None:
            new_kv = {}
        try:
            for key in old_kv:
                new_value = new_kv.get(key)
                old_value = old_kv.get(key)
                if new_value is None:
                    # 如果newValue 是空，则表示key，value被删除了。
                    self._handle_change_listeners(
                        {
                            "action": "delete",
                            "namespace": namespace,
                            "key": key,
                            "value": None,
                            "old_value": self._convert_type(old_value),
                        }
                    )
                    continue
                if new_value != old_value:
                    self._handle_change_listeners(
                        {
                            "action": "update",
                            "namespace": namespace,
                            "key": key,
                            "value": self._convert_type(new_value),
                            "old_value": self._convert_type(old_value),
                        }
                    )
                    continue
            for key in new_kv:
                new_value = new_kv.get(key)
                old_value = old_kv.get(key)
                if old_value is None:
                    self._handle_change_listeners(
                        {
                            "action": "add",
                            "namespace": namespace,
                            "key": key,
                            "value": self._convert_type(new_value),
                            "old_value": None,
                        }
                    )
        except BaseException as e:
            logging.error("_notify_change Exception", e)

    def _start_long_poll_update(self):
        self._long_poll_thread = threading.Thread(target=self._long_poll_update_loop)
        # 启动异步线程为守护线程，主线程推出的时候，守护线程会自动退出。
        self._long_poll_thread.daemon = True
        self._long_poll_thread.start()

    def _long_poll_update_loop(self):
        logging.info("start long_poll")
        while not self._update_stopped:
            self._long_poll()
            time.sleep(self._cycle_time)
        logging.info("stopped, long_poll")

    def _long_poll(self):
        notifications = []
        for key in self._notification_map:
            notification_id = self._notification_map.get(key)
            notifications.append(
                {NAMESPACE_NAME: key, NOTIFICATION_ID: notification_id}
            )
        try:
            # 如果长度为0直接返回
            if len(notifications) == 0:
                return
            url = "{}/notifications/v2".format(self._config_url)
            params = {
                "appId": self._app_id,
                "cluster": self._cluster,
                "notifications": json.dumps(notifications, ensure_ascii=False),
            }
            param_str = url_encode_wrapper(params)
            url = url + "?" + param_str
            code, body = http_request(
                url, self._pull_timeout, headers=self._sign_headers(url)
            )

            http_code = code
            if http_code == 304:
                logging.debug("No change, loop...")
                return
            if http_code == 200:
                data = json.loads(body)
                for entry in data:
                    namespace = entry[NAMESPACE_NAME]
                    n_id = entry[NOTIFICATION_ID]
                    self._notification_map[namespace] = n_id
                    logging.info("%s has changes: notificationId=%d", namespace, n_id)
                    namespace_data = self._get_json_from_net(namespace)
                    self._update_cache_and_file(namespace_data, namespace)
                    return
            else:
                logging.warning("Sleep...")
        except Exception as e:
            logging.error("_long_poll Exception", str(e))

__all__ = [
    "ApolloClient"
]