#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import shutil
import logging
import argparse
from datetime import datetime
from typing import List, Optional, Tuple
import pymysql
from pymysql.cursors import SSCursor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mysql_export.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MySQLExporter:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.max_file_size = 2 * 1024 * 1024 * 1024  # 2GB
        self.min_disk_space = 10 * 1024 * 1024 * 1024  # 10GB
        self.batch_size = 10000  # 每次查询的记录数
        
    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=SSCursor  # 使用服务器端游标，减少内存占用
            )
            logger.info(f"成功连接到数据库: {self.host}:{self.port}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    def check_disk_space(self, path: str = '.') -> bool:
        """检查磁盘剩余空间"""
        try:
            total, used, free = shutil.disk_usage(path)
            logger.info(f"磁盘空间 - 总计: {total/1024/1024/1024:.2f}GB, "
                       f"已用: {used/1024/1024/1024:.2f}GB, "
                       f"剩余: {free/1024/1024/1024:.2f}GB")
            
            if free < self.min_disk_space:
                logger.warning(f"磁盘剩余空间不足10GB，当前剩余: {free/1024/1024/1024:.2f}GB")
                return False
            return True
        except Exception as e:
            logger.error(f"检查磁盘空间失败: {e}")
            return False
    
    def get_table_info(self, table: str) -> Tuple[List[str], str]:
        """获取表信息，包括字段列表和主键"""
        try:
            cursor = self.connection.cursor()
            
            # 获取表结构
            cursor.execute(f"DESCRIBE `{table}`")
            columns = []
            primary_key = None
            
            for row in cursor.fetchall():
                field_name = row[0]
                columns.append(field_name)
                if row[3] == 'PRI':  # Primary Key
                    primary_key = field_name
            
            cursor.close()
            logger.info(f"表 {table} 包含 {len(columns)} 个字段，主键: {primary_key}")
            return columns, primary_key
            
        except Exception as e:
            logger.error(f"获取表信息失败: {e}")
            return [], None
    
    def get_table_count(self, table: str) -> int:
        """获取表总记录数"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            count = cursor.fetchone()[0]
            cursor.close()
            logger.info(f"表 {table} 总记录数: {count}")
            return count
        except Exception as e:
            logger.error(f"获取表记录数失败: {e}")
            return 0
    
    def load_progress(self, table: str) -> dict:
        """加载导出进度"""
        progress_file = f"{table}_export_progress.json"
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
                logger.info(f"加载导出进度: 已处理 {progress.get('processed_rows', 0)} 行")
                return progress
            except Exception as e:
                logger.warning(f"加载进度文件失败: {e}")
        return {
            'file_index': 1,
            'processed_rows': 0,
            'last_primary_key': None,
            'current_file_size': 0
        }
    
    def save_progress(self, table: str, progress: dict):
        """保存导出进度"""
        progress_file = f"{table}_export_progress.json"
        try:
            with open(progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
            logger.debug(f"保存进度: {progress}")
        except Exception as e:
            logger.error(f"保存进度失败: {e}")
    
    def generate_insert_statement(self, table: str, columns: List[str], row: tuple) -> str:
        """生成INSERT语句"""
        # 处理NULL值和特殊字符
        values = []
        for value in row:
            if value is None:
                values.append('NULL')
            elif isinstance(value, str):
                # 转义特殊字符
                escaped_value = value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
                values.append(f"'{escaped_value}'")
            elif isinstance(value, (int, float)):
                values.append(str(value))
            elif isinstance(value, datetime):
                values.append(f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'")
            else:
                values.append(f"'{str(value)}'")
        
        columns_str = ', '.join([f'`{col}`' for col in columns])
        values_str = ', '.join(values)
        return f"INSERT INTO `{table}` ({columns_str}) VALUES ({values_str});\n"
    
    def export_table(self, table: str, exclude_columns: Optional[List[str]] = None, 
                    resume: bool = False) -> bool:
        """导出表数据"""
        if not self.check_disk_space():
            logger.error("磁盘空间不足，请清理磁盘后重新运行")
            return False
        
        # 获取表信息
        all_columns, primary_key = self.get_table_info(table)
        if not all_columns:
            logger.error(f"无法获取表 {table} 的信息")
            return False
        
        if not primary_key:
            logger.warning(f"表 {table} 没有主键，可能影响断点续传功能")
        
        # 过滤排除的字段
        if exclude_columns:
            columns = [col for col in all_columns if col not in exclude_columns]
            logger.info(f"排除字段: {exclude_columns}")
        else:
            columns = all_columns
        
        logger.info(f"导出字段: {columns}")
        
        # 加载进度
        progress = self.load_progress(table) if resume else {
            'file_index': 1,
            'processed_rows': 0,
            'last_primary_key': None,
            'current_file_size': 0
        }
        
        # 构建SQL查询
        columns_str = ', '.join([f'`{col}`' for col in columns])
        base_query = f"SELECT {columns_str} FROM `{table}`"
        
        # 如果有主键且是续传，添加WHERE条件
        if primary_key and progress['last_primary_key'] is not None:
            base_query += f" WHERE `{primary_key}` > {progress['last_primary_key']}"
        
        if primary_key:
            base_query += f" ORDER BY `{primary_key}`"
        
        # 获取总记录数
        total_rows = self.get_table_count(table)
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(base_query)
            
            # 打开输出文件
            output_file = f"{table}_export_{progress['file_index']}.sql"
            current_file_size = progress['current_file_size']
            
            with open(output_file, 'a' if resume and progress['file_index'] == 1 else 'w') as f:
                if not resume or progress['processed_rows'] == 0:
                    # 写入文件头
                    f.write(f"-- MySQL数据导出\n")
                    f.write(f"-- 表: {table}\n")
                    f.write(f"-- 导出时间: {datetime.now()}\n")
                    f.write(f"-- 排除字段: {exclude_columns or '无'}\n\n")
                    f.write(f"SET NAMES utf8mb4;\n")
                    f.write(f"SET FOREIGN_KEY_CHECKS = 0;\n\n")
                
                batch_count = 0
                last_primary_key_value = progress['last_primary_key']
                
                while True:
                    rows = cursor.fetchmany(self.batch_size)
                    if not rows:
                        break
                    
                    for row in rows:
                        # 检查磁盘空间
                        if progress['processed_rows'] % 1000 == 0:  # 每1000条记录检查一次
                            if not self.check_disk_space():
                                logger.error("磁盘空间不足，程序退出")
                                self.save_progress(table, progress)
                                cursor.close()
                                return False
                        
                        # 生成INSERT语句
                        insert_stmt = self.generate_insert_statement(table, columns, row)
                        stmt_size = len(insert_stmt.encode('utf-8'))
                        
                        # 检查文件大小，如果超过2GB则新建文件
                        if current_file_size + stmt_size > self.max_file_size:
                            f.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
                            f.close()
                            
                            logger.info(f"文件 {output_file} 已达到大小限制，创建新文件")
                            progress['file_index'] += 1
                            progress['current_file_size'] = 0
                            current_file_size = 0
                            
                            output_file = f"{table}_export_{progress['file_index']}.sql"
                            f = open(output_file, 'w')
                            f.write(f"-- MySQL数据导出 (续)\n")
                            f.write(f"-- 表: {table}\n")
                            f.write(f"-- 文件序号: {progress['file_index']}\n")
                            f.write(f"-- 导出时间: {datetime.now()}\n\n")
                            f.write(f"SET NAMES utf8mb4;\n")
                            f.write(f"SET FOREIGN_KEY_CHECKS = 0;\n\n")
                        
                        f.write(insert_stmt)
                        current_file_size += stmt_size
                        progress['processed_rows'] += 1
                        progress['current_file_size'] = current_file_size
                        
                        # 更新主键值（用于断点续传）
                        if primary_key:
                            pk_index = columns.index(primary_key) if primary_key in columns else all_columns.index(primary_key)
                            if pk_index < len(row):
                                last_primary_key_value = row[pk_index] if primary_key in columns else None
                        
                        # 定期保存进度和显示状态
                        if progress['processed_rows'] % 1000 == 0:
                            progress['last_primary_key'] = last_primary_key_value
                            self.save_progress(table, progress)
                            
                            percentage = (progress['processed_rows'] / total_rows * 100) if total_rows > 0 else 0
                            logger.info(f"导出进度: {progress['processed_rows']}/{total_rows} "
                                       f"({percentage:.1f}%) - 文件: {output_file}")
                
                f.write("\nSET FOREIGN_KEY_CHECKS = 1;\n")
            
            cursor.close()
            
            # 导出完成，删除进度文件
            progress_file = f"{table}_export_progress.json"
            if os.path.exists(progress_file):
                os.remove(progress_file)
            
            logger.info(f"表 {table} 导出完成！")
            logger.info(f"总共导出 {progress['processed_rows']} 行记录")
            logger.info(f"共生成 {progress['file_index']} 个文件")
            
            return True
            
        except Exception as e:
            logger.error(f"导出过程中发生错误: {e}")
            self.save_progress(table, progress)
            return False

def main():
    parser = argparse.ArgumentParser(description='MySQL大表数据导出工具')
    parser.add_argument('--host', required=True, help='数据库主机')
    parser.add_argument('--port', type=int, default=3306, help='数据库端口')
    parser.add_argument('--user', required=True, help='数据库用户名')
    parser.add_argument('--password', required=True, help='数据库密码')
    parser.add_argument('--database', required=True, help='数据库名')
    parser.add_argument('--table', required=True, help='要导出的表名')
    parser.add_argument('--exclude', nargs='*', help='要排除的字段列表')
    parser.add_argument('--resume', action='store_true', help='从上次中断处继续导出')
    
    args = parser.parse_args()
    
    # 创建导出器实例
    exporter = MySQLExporter(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
    
    try:
        # 连接数据库
        if not exporter.connect():
            sys.exit(1)
        
        # 导出表数据
        success = exporter.export_table(
            table=args.table,
            exclude_columns=args.exclude,
            resume=args.resume
        )
        
        if success:
            logger.info("导出任务完成！")
            sys.exit(0)
        else:
            logger.error("导出任务失败！")
            sys.exit(1)
            
    finally:
        exporter.disconnect()

if __name__ == '__main__':
    main()
