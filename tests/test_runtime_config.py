import yaml

import jarvis.config_runtime as runtime


def test_local_overrides_do_not_modify_tracked_defaults(tmp_path, monkeypatch):
    base = tmp_path / "config.yaml"
    local = tmp_path / "local_config.yaml"
    base.write_text(
        "stt:\n  model: base\n  device: cpu\n"
        "llm:\n  active_provider: ollama\n  providers:\n    ollama:\n      model: qwen\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "_BASE_CONFIG", base)
    monkeypatch.setattr(runtime, "_LOCAL_CONFIG", local)

    effective = runtime.load_config()
    effective["stt"]["model"] = "small"
    effective["llm"]["providers"]["cloud"] = {
        "type": "openai",
        "model": "example",
        "api_key": "local-secret",
    }
    runtime.save_effective_config(effective)

    assert yaml.safe_load(base.read_text(encoding="utf-8"))["stt"]["model"] == "base"
    saved = yaml.safe_load(local.read_text(encoding="utf-8"))
    assert saved["stt"] == {"model": "small"}
    assert saved["llm"]["providers"]["cloud"]["api_key"] == "local-secret"

    reloaded = runtime.load_config()
    assert reloaded["stt"]["device"] == "cpu"
    assert reloaded["stt"]["model"] == "small"
    assert reloaded["llm"]["providers"]["ollama"]["model"] == "qwen"
    assert reloaded["llm"]["providers"]["cloud"]["api_key"] == "local-secret"


def test_no_override_file_when_effective_equals_base(tmp_path, monkeypatch):
    base = tmp_path / "config.yaml"
    local = tmp_path / "local_config.yaml"
    base.write_text("performance:\n  profile: cpu_test\n", encoding="utf-8")
    monkeypatch.setattr(runtime, "_BASE_CONFIG", base)
    monkeypatch.setattr(runtime, "_LOCAL_CONFIG", local)

    runtime.save_effective_config(runtime.load_config())
    assert not local.exists()
