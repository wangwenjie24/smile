"""Agent 模块：创建 DeepAgents 实例"""

import os
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

from smile.config import AppConfig

# Skills 目录路径（相对于项目根目录）
_SKILLS_DIR = "skills"


def _resolve_skills_dir() -> Path | None:
    """定位 skills 目录。

    项目根目录下的 skills/。

    Returns:
        skills 目录路径，不存在时返回 None
    """
    # src/smile/agent.py → parents[2] = 项目根目录
    base = Path(__file__).resolve().parents[2]
    skills_dir = base / _SKILLS_DIR

    return skills_dir if skills_dir.is_dir() else None


def create_agent(config: AppConfig, model: BaseChatModel | None = None):
    """根据应用配置创建 DeepAgent。

    通过依赖注入支持传入预初始化的模型对象，便于测试。
    不传 model 时，自动从配置初始化 DeepSeek 模型。

    Args:
        config: 应用配置对象
        model: 可选的预初始化模型（用于测试）

    Returns:
        DeepAgent 实例
    """
    if model is None:
        model_kwargs = {
            "model": config.llm.model,
            "api_key": config.llm.api_key,
        }
        if config.llm.base_url:
            model_kwargs["base_url"] = config.llm.base_url
        model = init_chat_model(**model_kwargs)

    # 将 OA 凭据注入 os.environ，供 Skill 脚本通过环境变量读取
    os.environ["FINANCE_OA_USERNAME"] = config.oa.username
    os.environ["FINANCE_OA_PASSWORD"] = config.oa.password
    os.environ["FINANCE_OA_URL"] = config.oa.url

    skills_dir = _resolve_skills_dir()
    if skills_dir is not None:
        backend = LocalShellBackend(
            root_dir=str(skills_dir),
            virtual_mode=True,
        )
        agent = create_deep_agent(
            model=model,
            system_prompt="你是办公助手，帮助用户从 OA 系统导出财务数据。",
            skills=["/"],
            backend=backend,
        )
    else:
        # 没有 skills 目录时也能正常运行（优雅降级）
        agent = create_deep_agent(
            model=model,
            system_prompt="你是办公助手，帮助用户从 OA 系统导出财务数据。",
        )

    return agent
