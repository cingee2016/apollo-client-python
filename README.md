apollo-client-python - Python Client for Ctrip's Apollo
================
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

方便Python接入配置中心框架 [Apollo](https://github.com/ctripcorp/apollo) 所开发的Python版本客户端。

基于 [xhrg-product/apollo-client-python](https://github.com/xhrg-product/apollo-client-python)  修改

* Python3.x
* Apollo配置中心拉取配置
* 支持回调
* secret认证
* 本地文件缓存
* 热更新，通过参数配置

### 增加从环境变量读取基础配置：
### # Apollo 必需配置
APOLLO_META_SERVER_ADDRESS=http://localhost:8080
APOLLO_APP_ID=your-app-id

### # 认证配置
APOLLO_APP_SECRET=your-app-secret

### # 可选配置
APOLLO_CLUSTER=default
APOLLO_NAMESPACES=application
