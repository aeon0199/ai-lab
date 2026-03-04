from ailab_policy.registry import DEFAULT_TOOL_REGISTRY


def test_tool_registry_contains_v1_tools():
    assert {"python_exec", "shell_exec", "web_fetch", "model_inference", "dataset_read"}.issubset(
        set(DEFAULT_TOOL_REGISTRY.keys())
    )
