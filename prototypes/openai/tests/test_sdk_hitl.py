"""Framework HITL is not the COMPUTER security authority."""

import asyncio
from agents import Agent, Runner, RunConfig
from computer.adapters.openai_agent import DemoModel, OpenAIAgent
from computer.runtime import Runtime
from computer.contracts import Run, Provider


async def test_sdk_native_pause_resume_still_requires_computer_broker(tmp_path):
    rt = Runtime(tmp_path)
    session = rt.new_session()
    run = Run("sdk-probe", session.id, Provider())
    tools = OpenAIAgent(rt.registry).build_tools(run, rt.registry.dispatch)
    tool = next(t for t in tools if t.name == "execute_probe")
    tool.needs_approval = True
    agent = Agent(name="COMPUTER test", model=DemoModel(), tools=[tool])
    result = await Runner.run(agent, "/execute", run_config=RunConfig(tracing_disabled=True))
    assert result.interruptions and not run.results
    state = result.to_state()
    state.approve(result.interruptions[0])
    resumed = asyncio.create_task(Runner.run(agent, state, run_config=RunConfig(tracing_disabled=True)))
    try:
        for _ in range(100):
            pending = rt.broker.list_for(session.id)
            if pending:
                break
            await asyncio.sleep(0.01)
        assert pending and not run.results  # SDK approval alone did not execute the tool.
        p = pending[0]
        await rt.broker.decide(session.id, p["id"], p["digest"], "", False)
        final = await resumed
        assert "denied" in str(final.final_output)
        assert not run.results
    finally:
        resumed.cancel()
        await asyncio.gather(resumed, return_exceptions=True)
        await rt.close()
