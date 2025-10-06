#!/bin/bash

# 定义日志文件路径
LOG_FILE="run.log"
BACKUP_DIR="logs_backup"

case "$1" in
    start)
        # 检查是否已经在运行
        if [ -f "python_pid.txt" ]; then
            PID=$(cat python_pid.txt)
            if ps -p $PID > /dev/null 2>&1
            then
                echo "Python程序已经在运行 (PID: $PID)"
                exit 1
            fi
        fi

        # 创建备份目录（如果不存在）
        mkdir -p "$BACKUP_DIR"

        # 备份旧日志（如果存在）
        if [ -f "$LOG_FILE" ]; then
            TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
            BACKUP_FILE="$BACKUP_DIR/run_${TIMESTAMP}.log"
            mv "$LOG_FILE" "$BACKUP_FILE"
            echo "已备份旧日志到: $BACKUP_FILE"
        fi

        # 启动Python程序并记录PID
        nohup python -X utf8 main.py >> "$LOG_FILE" 2>&1 &
        echo $! > python_pid.txt
        echo "Python程序已启动 (PID: $!), 日志输出到: $LOG_FILE"
        ;;
    stop)
        # 停止Python程序
        if [ -f "python_pid.txt" ]; then
            PID=$(cat python_pid.txt)
            kill $PID
            rm python_pid.txt
            echo "Python程序已停止 (PID: $PID)"
        else
            echo "没有找到运行的Python程序"
        fi
        ;;
    status)
        # 检查程序状态
        if [ -f "python_pid.txt" ]; then
            PID=$(cat python_pid.txt)
            if ps -p $PID > /dev/null 2>&1
            then
                echo "Python程序正在运行 (PID: $PID)"
                echo "当前日志大小: $(du -h "$LOG_FILE" | cut -f1)"
            else
                echo "Python程序已停止"
            fi
        else
            echo "Python程序未运行"
        fi
        ;;
    logs)
        # 查看最近日志
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "日志文件不存在: $LOG_FILE"
        fi
        ;;
    *)
        echo "使用方法: $0 {start|stop|status|logs}"
        echo "  start   启动程序并备份旧日志"
        echo "  stop    停止程序"
        echo "  status  查看程序状态"
        echo "  logs    实时查看日志"
        exit 1
        ;;
esac

exit 0