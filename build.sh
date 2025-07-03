#!/bin/bash
set -e

# 构建Docker IPv6 Firewall Manager Debian包

PACKAGE_NAME="docker-ipv6-firewall"
VERSION=$(cat VERSION)  # 从VERSION文件读取版本号
REVISION=${1:-""}  # 可选的修订版本号，如 -2
ARCH="amd64"
BUILD_DIR="build"

# 如果有修订版本号，添加到版本中
if [ -n "$REVISION" ]; then
    FULL_VERSION="${VERSION}${REVISION}"
else
    FULL_VERSION="${VERSION}"
fi

PACKAGE_DIR="${BUILD_DIR}/${PACKAGE_NAME}_${FULL_VERSION}_${ARCH}"

echo "构建 ${PACKAGE_NAME} v${FULL_VERSION} for ${ARCH}"

# 清理之前的构建
rm -rf ${BUILD_DIR}
mkdir -p ${BUILD_DIR}

# 创建包目录结构
mkdir -p ${PACKAGE_DIR}/DEBIAN
mkdir -p ${PACKAGE_DIR}/usr/lib/${PACKAGE_NAME}
mkdir -p ${PACKAGE_DIR}/usr/share/${PACKAGE_NAME}
mkdir -p ${PACKAGE_DIR}/etc/systemd/system
mkdir -p ${PACKAGE_DIR}/var/log

# 动态生成control文件（替换版本号）
sed "s/Version: .*/Version: ${FULL_VERSION}/" debian/control > ${PACKAGE_DIR}/DEBIAN/control
cp debian/postinst ${PACKAGE_DIR}/DEBIAN/
cp debian/prerm ${PACKAGE_DIR}/DEBIAN/
cp debian/postrm ${PACKAGE_DIR}/DEBIAN/

# 设置权限
chmod 755 ${PACKAGE_DIR}/DEBIAN/postinst
chmod 755 ${PACKAGE_DIR}/DEBIAN/prerm
chmod 755 ${PACKAGE_DIR}/DEBIAN/postrm

# 复制源代码
cp src/*.py ${PACKAGE_DIR}/usr/lib/${PACKAGE_NAME}/
chmod 755 ${PACKAGE_DIR}/usr/lib/${PACKAGE_NAME}/main.py

# 复制配置文件
cp config/config.yaml ${PACKAGE_DIR}/usr/share/${PACKAGE_NAME}/

# 复制systemd服务文件
cp systemd/${PACKAGE_NAME}.service ${PACKAGE_DIR}/etc/systemd/system/

# 创建包
echo "创建Debian包..."
dpkg-deb --build ${PACKAGE_DIR}

# 移动到当前目录
mv ${BUILD_DIR}/${PACKAGE_NAME}_${FULL_VERSION}_${ARCH}.deb .

echo "构建完成: ${PACKAGE_NAME}_${FULL_VERSION}_${ARCH}.deb"
echo ""
echo "安装命令:"
echo "sudo dpkg -i ${PACKAGE_NAME}_${FULL_VERSION}_${ARCH}.deb"
echo ""
echo "如果有依赖问题，运行:"
echo "sudo apt-get install -f"
