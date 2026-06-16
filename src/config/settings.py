import os
from pathlib import Path
from dataclasses import dataclass, field

# 尝试导入 python-dotenv，如果没安装也不强制报错，方便直接使用环境变量
try:
    from dotenv import load_dotenv
    # 尝试寻找并加载根目录的 .env 文件
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

@dataclass
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    user: str = os.getenv("DB_USER", "postgres")
    password: str = os.getenv("DB_PASSWORD", "mysecretpassword")
    name: str = os.getenv("DB_NAME", "mydb")
    
    @property
    def database_url(self) -> str:
        """为 SQLAlchemy 或其他 ORM 提供的标准 PostgreSQL 连接字符串"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

@dataclass
class TushareConfig:
    token: str = os.getenv("TUSHARE_TOKEN", "")
    # 可选：自定义 HTTP 代理地址 (用于绕过频率限制或网络加速)
    http_url: str = os.getenv("TUSHARE_HTTP_URL", "")

@dataclass
class PathConfig:
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    results_dir: Path = base_dir / "results"
    backtest_dir: Path = results_dir / "backtest"
    reports_dir: Path = results_dir / "reports"
    logs_dir: Path = base_dir / "logs"
    configs_dir: Path = base_dir / "configs"
    
    def ensure_dirs(self):
        """确保必要的目录存在"""
        for d in [self.results_dir, self.backtest_dir, self.reports_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

@dataclass
class Settings:
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    tushare: TushareConfig = field(default_factory=TushareConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    
# 暴露全局设置实例
settings = Settings()
settings.paths.ensure_dirs()
