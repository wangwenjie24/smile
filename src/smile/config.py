"""配置模块：从 .env 读取敏感凭据，从 YAML 读取非敏感业务配置"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass
class OAConfig:
    """OA 系统连接配置（从环境变量读取）"""

    url: str
    username: str
    password: str


@dataclass
class LLMConfig:
    """大模型 API 配置（凭据从环境变量读取，模型名从 YAML 读取）"""

    model: str
    api_key: str = ""
    base_url: str = ""


@dataclass
class ExportConfig:
    """导出设置"""

    save_path: str = "~/Desktop"
    filename_template: str = "财务数据_{date}.xlsx"


@dataclass
class AppConfig:
    """应用总配置"""

    oa: OAConfig
    llm: LLMConfig
    export: ExportConfig = field(default_factory=ExportConfig)


def _require_env(name: str) -> str:
    """读取必填环境变量，缺失时抛出明确错误。"""
    value = os.environ.get(name, "")
    if not value:
        raise KeyError(
            f"缺少必填环境变量: {name}。"
            f"请在 .env 文件中设置 {name}=xxx"
        )
    return value


def load_config(path: str = "config.yaml") -> AppConfig:
    """从环境变量 + YAML 文件加载配置，返回类型化的 AppConfig 对象。

    敏感凭据（LLM API Key、OA 密码等）从 .env 环境变量读取；
    非敏感业务配置（模型名称、导出设置）从 YAML 文件读取。

    Args:
        path: YAML 配置文件路径（默认: config.yaml）。
              文件不存在时使用默认值。

    Returns:
        AppConfig 实例

    Raises:
        KeyError: 缺少必填环境变量
    """
    # 加载 .env 文件（如果存在）
    load_dotenv()

    # 从环境变量读取敏感凭据
    oa = OAConfig(
        url=_require_env("OA_URL"),
        username=_require_env("OA_USERNAME"),
        password=_require_env("OA_PASSWORD"),
    )

    llm_creds = LLMConfig(
        model="",  # 从 YAML 填充
        api_key=_require_env("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL", ""),
    )

    # 从 YAML 读取非敏感业务配置
    config_path = Path(path)
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    llm_raw = raw.get("llm", {})
    export_raw = raw.get("export", {})

    llm_creds.model = llm_raw.get("model", "openai:deepseek-chat")

    export = ExportConfig(
        save_path=export_raw.get("save_path", "~/Desktop"),
        filename_template=export_raw.get(
            "filename_template", "财务数据_{date}.xlsx"
        ),
    )

    return AppConfig(oa=oa, llm=llm_creds, export=export)
