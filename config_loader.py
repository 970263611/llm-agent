import os
import sys
import logging
import yaml  
from pathlib import Path
from logging.handlers import RotatingFileHandler


def _setup_logging(config):
    """根据配置设置日志系统"""
    if not config["log_config"]["enabled"]:
        # 完全禁用日志输出
        logging.disable(logging.CRITICAL)
        return

    log_level = getattr(logging, config["log_config"]["level"])
    format_str = config["log_config"]["format"]
    
    # 清除所有现有handler
    logging.basicConfig(level=log_level, handlers=[])
    
    # 创建根记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 文件日志
    if "filename" in config["log_config"]:
        file_handler = RotatingFileHandler(
            config["log_config"]["filename"],
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(format_str))
        root_logger.addHandler(file_handler)
    
    # 控制台日志
    if config["log_config"]["console_output"]:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(format_str))
        root_logger.addHandler(console_handler)


def get_config_path():
    # 如果是打包后的exe
    if getattr(sys, 'frozen', False):
        # EXE所在目录
        exe_dir = Path(sys.executable).parent
        # 外部配置文件路径
        external_config = exe_dir / "config.yaml"
        
        # 如果外部配置文件存在，优先使用
        if external_config.exists():
            return str(external_config)
        
        # 否则使用打包的内部配置
        internal_config = Path(sys._MEIPASS) / "config.yaml"
        return str(internal_config)
    else:
        # 开发环境使用脚本同目录下的配置
        return str(Path(__file__).parent / "config.yaml")


    
def load_config():
    config_path  = get_config_path()
    # 加载配置文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        _setup_logging(config)  
        return config
    
# 全局配置对象
CONFIG = load_config()