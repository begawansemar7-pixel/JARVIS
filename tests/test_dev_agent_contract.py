def test_dev_agent_tool_contract():
    from actions.dev_agent import TOOL, dev_agent

    assert TOOL["name"] == "dev_agent"
    assert TOOL["handler"] is dev_agent
    assert TOOL["parameters"]["type"] == "OBJECT"
    assert "description" in TOOL["parameters"]["properties"]
