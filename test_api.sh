#!/bin/bash

# WCF 服务器地址
WCF_SERVER="http://123.57.237.185:8086"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 测试函数
test_api() {
    local endpoint=$1
    local description=$2
    echo -e "\n${GREEN}测试 $description ($endpoint)${NC}"
    curl -s -w "\n响应状态码: %{http_code}\n" "$WCF_SERVER$endpoint"
}

echo "开始测试 WCF API 接口..."
echo "服务器地址: $WCF_SERVER"

# 测试登录状态
test_api "/islogin" "登录状态"

# 测试获取微信ID
test_api "/selfwxid" "获取微信ID"

# 测试获取用户信息
test_api "/selfinfo" "获取用户信息"

# 测试其他可能的接口
test_api "/api/is_login" "登录状态 (备选路径)"
test_api "/api/get_self_info" "获取用户信息 (备选路径)"
