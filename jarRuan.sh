#!/bin/bash

# Spring Boot 应用启动脚本
# 使用方法: ./startup.sh [start|stop|restart|status] <jar_path>

# ==============================================
# 配置区域
# ==============================================

MAIN_CLASS=""  # 如果使用jar文件，此项留空；如果直接运行class，填写主类名

# 目录配置
APP_HOME=$(cd "$(dirname "$0")" && pwd)

# 检查是否提供了JAR路径参数
if [ -z "$2" ]; then
    echo "错误: 必须指定JAR文件路径"
    echo "使用方法: $0 [命令] <jar路径>"
    echo "示例: $0 start myapp.jar"
    echo "使用 '$0 help' 查看详细帮助"
    exit 1
fi

# 处理JAR路径参数
if [[ "$2" = /* ]]; then
    # 绝对路径
    JAR_PATH="$2"
else
    # 相对路径，相对于脚本目录
    JAR_PATH="$APP_HOME/$2"
fi

# 从路径中提取JAR文件名作为应用名
JAR_FILE=$(basename "$JAR_PATH")
APP_NAME="${JAR_FILE%.*}"
LOG_DIR="$APP_HOME/logs"
PID_FILE="$APP_HOME/$APP_NAME.pid"

# JVM参数配置
JAVA_OPTS="-server"

# 内存配置
MEMORY_OPTS="-Xms4g -Xmx4g"

# 元空间配置
METASPACE_OPTS="-XX:MetaspaceSize=256m -XX:MaxMetaspaceSize=1g"

# 直接内存配置
DIRECT_MEMORY_OPTS="-XX:MaxDirectMemorySize=1g"

# 代码缓存配置
CODE_CACHE_OPTS="-XX:ReservedCodeCacheSize=256m"

# G1 GC配置
GC_OPTS="-XX:+UseG1GC -XX:G1ReservePercent=15 -XX:InitiatingHeapOccupancyPercent=65"

# GC日志配置
GC_LOG_PATH="$LOG_DIR/gc.log"
GC_LOG_OPTS="-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:$GC_LOG_PATH"

# 错误处理配置
ERROR_OPTS="-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=$LOG_DIR"

# Spring Boot配置
SPRING_OPTS="-Dspring.profiles.active=prod -Dserver.port=8080"

# 组合所有JVM参数
JVM_OPTS="$JAVA_OPTS $MEMORY_OPTS $METASPACE_OPTS $DIRECT_MEMORY_OPTS $CODE_CACHE_OPTS $GC_OPTS $GC_LOG_OPTS $ERROR_OPTS $SPRING_OPTS"

# ==============================================
# 函数定义
# ==============================================

# 检查Java环境
check_java() {
    if [ -z "$JAVA_HOME" ]; then
        JAVA_CMD=$(which java)
        if [ $? -ne 0 ]; then
            echo "错误: 未找到Java环境，请设置JAVA_HOME或确保java在PATH中"
            exit 1
        fi
    else
        JAVA_CMD="$JAVA_HOME/bin/java"
        if [ ! -x "$JAVA_CMD" ]; then
            echo "错误: Java可执行文件不存在: $JAVA_CMD"
            exit 1
        fi
    fi
    
    # 显示Java版本信息
    echo "使用Java: $JAVA_CMD"
    $JAVA_CMD -version
}

# 检查应用文件
check_app() {
    if [ ! -f "$JAR_PATH" ]; then
        echo "错误: JAR文件不存在: $JAR_PATH"
        echo "请确保JAR文件路径正确，或修改脚本中的JAR_FILE变量"
        exit 1
    fi
    echo "应用文件: $JAR_PATH"
}

# 创建必要的目录
create_dirs() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        echo "创建日志目录: $LOG_DIR"
    fi
}

# 检查应用是否正在运行
is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# 启动应用
start_app() {
    echo "正在启动 $APP_NAME..."
    
    if is_running; then
        echo "$APP_NAME 已在运行中 (PID: $(cat $PID_FILE))"
        return 0
    fi
    
    # 检查环境
    check_java
    check_app
    create_dirs
    
    # 启动应用
    echo "执行命令: $JAVA_CMD $JVM_OPTS -jar $JAR_PATH"
    nohup $JAVA_CMD $JVM_OPTS -jar "$JAR_PATH" > "$LOG_DIR/application.out" 2>&1 &
    
    # 保存PID
    echo $! > "$PID_FILE"
    PID=$!
    
    # 等待应用启动
    echo "等待应用启动..."
    sleep 3
    
    if is_running; then
        echo "$APP_NAME 启动成功! PID: $PID"
        echo "日志文件: $LOG_DIR/application.out"
        echo "GC日志: $GC_LOG_PATH"
        echo "可使用 tail -f $LOG_DIR/application.out 查看实时日志"
    else
        echo "$APP_NAME 启动失败，请查看日志文件"
        return 1
    fi
}

# 停止应用
stop_app() {
    echo "正在停止 $APP_NAME..."
    
    if ! is_running; then
        echo "$APP_NAME 未在运行"
        return 0
    fi
    
    PID=$(cat "$PID_FILE")
    echo "正在终止进程 $PID..."
    
    # 优雅关闭
    kill $PID
    
    # 等待进程结束
    for i in {1..30}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            echo "$APP_NAME 已停止"
            return 0
        fi
        echo "等待进程结束... ($i/30)"
        sleep 1
    done
    
    # 强制结束
    echo "优雅关闭超时，强制终止进程..."
    kill -9 $PID
    rm -f "$PID_FILE"
    echo "$APP_NAME 已强制停止"
}

# 重启应用
restart_app() {
    stop_app
    sleep 2
    start_app
}

# 检查应用状态
status_app() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        echo "$APP_NAME 正在运行 (PID: $PID)"
        
        # 显示进程信息
        echo ""
        echo "进程信息:"
        ps -f -p $PID
        
        # 显示端口监听情况
        echo ""
        echo "端口监听情况:"
        netstat -tlnp 2>/dev/null | grep $PID || echo "未找到监听端口信息"
        
        return 0
    else
        echo "$APP_NAME 未运行"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "Spring Boot 应用启动脚本"
    echo ""
    echo "使用方法:"
    echo "  $0 <命令> <jar路径>"
    echo ""
    echo "可用命令:"
    echo "  start    - 启动应用"
    echo "  stop     - 停止应用"
    echo "  restart  - 重启应用"
    echo "  status   - 查看应用状态"
    echo "  help     - 显示帮助信息"
    echo ""
    echo "jar路径参数 (必需):"
    echo "  - 相对路径: ./startup.sh start myapp.jar"
    echo "  - 绝对路径: ./startup.sh start /opt/apps/myapp.jar"
    echo ""
    echo "使用示例:"
    echo "  $0 start myapp.jar              # 启动相对路径JAR文件"
    echo "  $0 start /opt/myapp.jar         # 启动绝对路径JAR文件"
    echo "  $0 stop myapp.jar               # 停止指定的应用"
    echo "  $0 restart user-service.jar     # 重启应用"
    echo "  $0 status order-service.jar     # 查看应用状态"
    echo ""
    echo "注意事项:"
    echo "  - JAR路径参数是必需的，不能省略"
    echo "  - 停止、重启、查看状态时需要使用与启动时相同的JAR路径"
    echo "  - 应用名称会自动从JAR文件名中提取"
}

# ==============================================
# 主程序
# ==============================================

case "$1" in
    start)
        start_app
        ;;
    stop)
        stop_app
        ;;
    restart)
        restart_app
        ;;
    status)
        status_app
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        echo "错误: 必须指定命令"
        echo "使用 '$0 help' 查看帮助信息"
        exit 1
        ;;
    *)
        echo "无效命令: $1"
        echo "使用 '$0 help' 查看帮助信息"
        exit 1
        ;;
esac

exit $?
