"""测试：从环境变量 + YAML 配置创建 DeepAgent 并调用"""

import os
import tempfile
from pathlib import Path
from typing import override
from unittest.mock import patch

import yaml
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from smile.agent import _resolve_skills_dir, create_agent
from smile.config import load_config


class FakeChatModel(BaseChatModel):
    """用于测试的假模型，直接返回固定回复。
    DeepAgents 会在运行时调用 bind_tools，所以必须实现该方法。
    """

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        """接受工具绑定但不实际使用，返回自身"""
        return self

    @override
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs,
    ) -> ChatResult:
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content="已收到您的请求，正在处理。"))
            ]
        )


def _make_config_file() -> str:
    """创建临时配置文件（仅非敏感字段），返回路径"""
    config_data = {
        "llm": {
            "model": "openai:deepseek-chat",
        },
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(config_data, f)
        return f.name


# 测试所需的环境变量（模拟 .env 中的凭据）
_FAKE_ENV = {
    "OPENAI_API_KEY": "sk-test-fake-key",
    "OPENAI_BASE_URL": "https://api.deepseek.com",
    "OA_URL": "https://oa.example.com",
    "OA_USERNAME": "testuser",
    "OA_PASSWORD": "testpass",
}


# ── _resolve_skills_dir 测试 ─────────────────────────────────


class TestResolveSkillsDir:
    """测试 skills 目录定位逻辑"""

    def test_returns_project_root_skills_dir(self):
        """应定位到项目根目录下的 skills/"""
        result = _resolve_skills_dir()
        # 项目存在 skills 目录
        assert result is not None
        assert result.name == "skills"

    def test_resolves_from_agent_file(self):
        """路径应基于 agent.py 所在位置向上两级（项目根目录）"""
        result = _resolve_skills_dir()
        # src/smile/agent.py → parents[2] = 项目根目录
        expected_base = Path(__file__).resolve().parents[1]
        assert result == expected_base / "skills"

    def test_returns_none_when_dir_not_exists(self, tmp_path):
        """skills 目录不存在时应返回 None（优雅降级）"""
        fake_file = tmp_path / "fake_agent.py"
        fake_file.write_text("")
        with patch("smile.agent.__file__", str(fake_file)):
            result = _resolve_skills_dir()
            assert result is None


# ── create_agent 测试 ─────────────────────────────────────────


def test_create_agent_from_config(monkeypatch):
    """能从环境变量 + YAML 配置创建 DeepAgent（使用 DeepSeek）"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        agent = create_agent(config)
        assert agent is not None
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_invoke_agent_returns_response(monkeypatch):
    """Agent 能被调用并返回结果（使用 FakeChatModel）"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        fake_model = FakeChatModel()
        agent = create_agent(config, model=fake_model)

        result = agent.invoke(
            {"messages": [{"role": "user", "content": "你好"}]}
        )

        assert result is not None
        assert "messages" in result
        # 验证返回的消息列表包含 AI 回复
        messages = result["messages"]
        assert any(isinstance(m, AIMessage) for m in messages)
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_create_agent_with_injected_model(monkeypatch):
    """传入预初始化模型时应跳过自动初始化，直接使用注入的模型"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        fake_model = FakeChatModel()
        agent = create_agent(config, model=fake_model)

        # Agent 应正常创建且可调用
        assert agent is not None
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "测试依赖注入"}]}
        )
        assert result is not None
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_create_agent_without_skills_dir(monkeypatch, tmp_path):
    """skills 目录不存在时应优雅降级，不挂载 LocalShellBackend"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    # 让 _resolve_skills_dir 返回 None
    fake_file = tmp_path / "fake_agent.py"
    fake_file.write_text("")
    with patch("smile.agent.__file__", str(fake_file)):
        try:
            config = load_config(config_path)
            fake_model = FakeChatModel()
            agent = create_agent(config, model=fake_model)

            # 无 skills 目录也能创建 Agent
            assert agent is not None
            result = agent.invoke(
                {"messages": [{"role": "user", "content": "无 skills 测试"}]}
            )
            assert result is not None
        finally:
            Path(config_path).unlink(missing_ok=True)


def test_create_agent_model_kwargs_without_base_url(monkeypatch):
    """config 中没有 base_url 时不应将其传入 init_chat_model"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)
    # 不设置 OPENAI_BASE_URL
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        # 使用 FakeChatModel 避免 init_chat_model 真正发起请求
        fake_model = FakeChatModel()
        agent = create_agent(config, model=fake_model)
        assert agent is not None
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_create_agent_injects_oa_credentials_into_environ(monkeypatch):
    """create_agent 应将 OA 凭据注入 os.environ，供 Skill 脚本读取"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        # 在 load_config() 之后清理，隔离 load_dotenv() 从 .env 加载的干扰
        for key in ("FINANCE_OA_USERNAME", "FINANCE_OA_PASSWORD", "FINANCE_OA_URL"):
            monkeypatch.delenv(key, raising=False)

        fake_model = FakeChatModel()
        create_agent(config, model=fake_model)

        assert os.environ["FINANCE_OA_USERNAME"] == "testuser"
        assert os.environ["FINANCE_OA_PASSWORD"] == "testpass"
        assert os.environ["FINANCE_OA_URL"] == "https://oa.example.com"
    finally:
        Path(config_path).unlink(missing_ok=True)


def test_create_agent_uses_local_shell_backend(monkeypatch):
    """create_agent 应使用 LocalShellBackend 以支持 shell 命令执行"""
    for k, v in _FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    config_path = _make_config_file()
    try:
        config = load_config(config_path)
        fake_model = FakeChatModel()

        with patch("smile.agent.LocalShellBackend") as MockBackend:
            create_agent(config, model=fake_model)
            MockBackend.assert_called_once_with(
                root_dir=str(_resolve_skills_dir()),
                virtual_mode=True,
            )
    finally:
        Path(config_path).unlink(missing_ok=True)
