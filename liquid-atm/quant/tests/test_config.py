from liquid_atm_quant.config import Settings


def test_defaults_are_safe(monkeypatch):
    for var in ("ALPACA_PAPER", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.alpaca_paper is True
    assert not s.has_alpaca_keys
    assert s.llm_model == "qwen2.5:14b-instruct"
    assert s.llm_max_concurrency == 1


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER", "false")
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.setenv("LLM_MODEL", "qwen3:14b")
    s = Settings(_env_file=None)
    assert s.alpaca_paper is False
    assert s.has_alpaca_keys
    assert s.llm_model == "qwen3:14b"
