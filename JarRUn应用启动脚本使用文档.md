# JarRUn应用启动脚本使用文档

## 脚本概述

这是一个专业的 Spring Boot 应用启动管理脚本，提供了完整的应用生命周期管理功能，包括启动、停止、重启、状态查询等。

## 功能特性

- ✅ 完整的应用生命周期管理
- ✅ 生产级 JVM 参数配置
- ✅ 完善的错误处理和日志管理
- ✅ 环境检查和依赖验证
- ✅ 优雅的进程关闭机制
- ✅ 详细的状态监控信息

## 快速开始

### 1. 脚本配置

在使用脚本前，需要根据实际情况修改配置区域：

```bash
# 应用基本信息
APP_NAME="your-springboot-app"        # 应用名称
JAR_FILE="your-app.jar"               # JAR 文件名
MAIN_CLASS=""                         # 主类名（使用 JAR 时留空）

# 目录配置（通常无需修改）
APP_HOME=$(cd "$(dirname "$0")" && pwd)
JAR_PATH="$APP_HOME/$JAR_FILE"
LOG_DIR="$APP_HOME/logs"
PID_FILE="$APP_HOME/$APP_NAME.pid"

# 服务端口和配置文件
SPRING_OPTS="-Dspring.profiles.active=prod -Dserver.port=8080"
```

### 2. 文件结构要求

```
/app-directory/
├── startup.sh           # 启动脚本
├── your-app.jar         # Spring Boot 应用 JAR 文件
└── logs/                # 日志目录（自动创建）
    ├── application.out  # 应用日志
    └── gc.log          # GC 日志
```

### 3. 权限设置

```bash
chmod +x startup.sh
```

## 使用方法

### 启动应用
```bash
./startup.sh start
```

### 停止应用
```bash
./startup.sh stop
```

### 重启应用
```bash
./startup.sh restart
```

### 查看状态
```bash
./startup.sh status
```

### 获取帮助
```bash
./startup.sh help
```

## 配置详解

### JVM 内存配置
```bash
# 堆内存设置
MEMORY_OPTS="-Xms4g -Xmx4g"                    # 初始和最大堆内存

# 元空间设置
METASPACE_OPTS="-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=1g"

# 直接内存设置
DIRECT_MEMORY_OPTS="-XX:MaxDirectMemorySize=1g"

# 代码缓存设置
CODE_CACHE_OPTS="-XX:ReservedCodeCacheSize=256m"
```

### GC 配置
```bash
# G1 垃圾回收器
GC_OPTS="-XX:+UseG1GC -XX:G1ReservePercent=15 -XX:InitiatingHeapOccupancyPercent=65"

# GC 日志配置
GC_LOG_OPTS="-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:$GC_LOG_PATH"
```

### 错误处理配置
```bash
# 内存溢出时生成堆转储
ERROR_OPTS="-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=$LOG_DIR"
```

## 生产环境建议配置

### 小型应用（1-2GB 内存）
```bash
MEMORY_OPTS="-Xms1g -Xmx2g"
METASPACE_OPTS="-XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=512m"
```

### 中型应用（4-8GB 内存）
```bash
MEMORY_OPTS="-Xms4g -Xmx8g"
METASPACE_OPTS="-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=1g"
```

### 大型应用（16GB+ 内存）
```bash
MEMORY_OPTS="-Xms8g -Xmx16g"
METASPACE_OPTS="-XX:MetaspaceSize=512m -XX:MaxMetaspaceSize=2g"
```

## 监控和日志

### 实时日志查看
```bash
# 查看应用日志
tail -f logs/application.out

# 查看 GC 日志
tail -f logs/gc.log
```

### 状态信息示例
```bash
$ ./startup.sh status
your-springboot-app 正在运行 (PID: 12345)

进程信息:
UID        PID  PPID  C STIME TTY      TIME CMD
user     12345     1  2 14:30 pts/0    00:01:25 java -server -Xms4g -Xmx4g ...

端口监听情况:
tcp6       0      0 :::8080    :::*    LISTEN      12345/java
```

## 故障排除

### 常见问题及解决方案

#### 1. 应用启动失败
```bash
# 检查 Java 环境
java -version

# 检查 JAR 文件是否存在
ls -la your-app.jar

# 查看详细错误日志
cat logs/application.out
```

#### 2. 端口被占用
```bash
# 检查端口占用情况
netstat -tlnp | grep 8080

# 修改应用端口
SPRING_OPTS="-Dserver.port=8081"
```

#### 3. 内存不足
```bash
# 调整内存配置
MEMORY_OPTS="-Xms2g -Xmx2g"
```

#### 4. 权限问题
```bash
# 确保脚本有执行权限
chmod +x startup.sh

# 确保有日志目录写入权限
mkdir -p logs
chmod 755 logs
```

## 系统集成

### 作为系统服务（Systemd）
创建 `/etc/systemd/system/springboot-app.service`：
```ini
[Unit]
Description=Spring Boot Application
After=network.target

[Service]
Type=forking
User=appuser
Group=appgroup
WorkingDirectory=/path/to/your/app
ExecStart=/path/to/your/app/startup.sh start
ExecStop=/path/to/your/app/startup.sh stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable springboot-app
sudo systemctl start springboot-app
```

### 定时重启（Crontab）
```bash
# 每天凌晨 3 点重启应用
0 3 * * * /path/to/your/app/startup.sh restart
```

## 安全建议

1. **文件权限**：确保配置文件和脚本权限适当
2. **日志轮转**：定期清理日志文件，避免磁盘空间不足
3. **监控告警**：设置进程监控和异常告警
4. **备份策略**：定期备份应用和配置文件

## 版本更新

更新应用时建议的步骤：
1. 停止当前应用：`./startup.sh stop`
2. 备份旧版本 JAR 文件
3. 部署新版本 JAR 文件
4. 启动应用：`./startup.sh start`
5. 验证应用状态：`./startup.sh status`

## 技术支持

如果遇到问题，可以：
1. 查看日志文件：`logs/application.out`
2. 检查系统资源：`free -h`, `df -h`
3. 验证网络连接和端口状态
4. 确认 Java 环境配置正确

---

*此文档根据实际脚本功能编写，具体配置请根据生产环境需求调整。*
