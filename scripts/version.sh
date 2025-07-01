#!/bin/bash

# 版本管理脚本
# 用法: ./scripts/version.sh [get|set|bump]

set -e

VERSION_FILE="VERSION"

get_version() {
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE"
    else
        echo "错误: VERSION文件不存在" >&2
        exit 1
    fi
}

set_version() {
    local new_version="$1"
    if [ -z "$new_version" ]; then
        echo "错误: 请提供新版本号" >&2
        echo "用法: $0 set <版本号>" >&2
        exit 1
    fi
    
    # 验证版本号格式 (简单的语义版本检查)
    if ! echo "$new_version" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        echo "错误: 版本号格式无效，应为 x.y.z 格式" >&2
        exit 1
    fi
    
    echo "$new_version" > "$VERSION_FILE"
    echo "版本号已更新为: $new_version"
    
    # 只更新VERSION文件，不自动修改CHANGELOG.md
    # CHANGELOG.md应该手动维护，确保内容质量
    echo "请手动更新CHANGELOG.md中的版本 $new_version 内容"
}

bump_version() {
    local bump_type="$1"
    local current_version=$(get_version)
    
    # 解析当前版本号
    local major=$(echo "$current_version" | cut -d. -f1)
    local minor=$(echo "$current_version" | cut -d. -f2)
    local patch=$(echo "$current_version" | cut -d. -f3)
    
    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            echo "错误: 无效的bump类型，支持: major, minor, patch" >&2
            exit 1
            ;;
    esac
    
    local new_version="${major}.${minor}.${patch}"
    set_version "$new_version"
}

show_help() {
    echo "版本管理脚本"
    echo ""
    echo "用法:"
    echo "  $0 get                    - 获取当前版本号"
    echo "  $0 set <版本号>           - 设置新版本号"
    echo "  $0 bump <major|minor|patch> - 自动递增版本号"
    echo ""
    echo "示例:"
    echo "  $0 get"
    echo "  $0 set 1.3.0"
    echo "  $0 bump minor"
}

# 主逻辑
case "${1:-}" in
    get)
        get_version
        ;;
    set)
        set_version "$2"
        ;;
    bump)
        bump_version "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "错误: 无效的命令" >&2
        echo ""
        show_help
        exit 1
        ;;
esac
