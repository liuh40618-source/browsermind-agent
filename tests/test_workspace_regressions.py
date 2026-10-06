import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import config
import main
import settings_store as settings_module
from agent.agent_loop import AgentLoop
from settings_store import ConfigValidationError, SettingsStore
from store import TaskStore


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    settings = SettingsStore(tmp_path / 'settings.json')
    tasks = TaskStore(tmp_path / 'tasks.db')
    monkeypatch.setattr(main, 'settings_store', settings)
    monkeypatch.setattr(settings_module, 'settings_store', settings)
    monkeypatch.setattr(main, 'store', tasks)
    monkeypatch.setattr(main.llm_client, 'reload', lambda: None)
    monkeypatch.setattr(config, 'environment_settings', config.Settings(_env_file=None, llm_api_key=''))
    monkeypatch.setattr(main, 'environment_settings', config.environment_settings)
    monkeypatch.setattr(main, 'settings', config.Settings(_env_file=None, auth_token='', llm_api_key=''))
    return settings, tasks, TestClient(main.app)


def save(tasks, task='test', status='done', report='report'):
    return tasks.save_task(task, status, [], [], [], report, [])


@pytest.mark.parametrize('change', [
    {'llm_provider': 'bad', 'llm_api_key': 'new'},
    {'llm_model': '', 'provider_api_keys': {'qwen': 'new'}},
    {'llm_api_key': 'invalid key'},
    {'provider_api_keys': {'qwen': 'invalid key'}},
    {'llm_base_url': 'https://'},
    {'llm_base_url': 'https://user:password@example.com'},
])
def test_invalid_settings_are_atomic(tmp_path, change):
    settings = SettingsStore(tmp_path / 'settings.json')
    settings.update({'llm_provider': 'deepseek', 'llm_api_key': 'original'})
    before = settings.path.read_bytes()
    with pytest.raises(ConfigValidationError):
        settings.update(change)
    assert settings.path.read_bytes() == before
    assert settings.get_key_for_provider('deepseek') == 'original'
    assert settings.get_key_for_provider('qwen') == ''


def test_failed_write_preserves_memory(tmp_path, monkeypatch):
    settings = SettingsStore(tmp_path / 'settings.json')
    settings.update({'llm_provider': 'deepseek', 'llm_api_key': 'original'})
    before = settings.get_all_with_key()
    def fail(*args):
        raise OSError('disk unavailable')
    monkeypatch.setattr(settings_module.os, 'replace', fail)
    with pytest.raises(OSError):
        settings.update({'llm_api_key': 'new'})
    assert settings.get_all_with_key() == before


def test_provider_switch_and_reload_do_not_leak_key(tmp_path):
    settings = SettingsStore(tmp_path / 'settings.json')
    settings.update({'llm_provider': 'deepseek', 'llm_api_key': 'secret'})
    settings.update({'llm_provider': 'qwen'})
    reloaded = SettingsStore(settings.path)
    assert reloaded.get_key_for_provider('qwen') == ''
    assert reloaded.get_key_for_provider('deepseek') == 'secret'


def test_empty_api_inputs_preserve_keys(isolated):
    settings, _, client = isolated
    settings.update({'llm_provider': 'openai', 'llm_api_key': 'secret', 'tavily_api_key': 'search'})
    response = client.post('/api/settings', json={'llm_model': 'custom-model', 'llm_api_key': '', 'tavily_api_key': ''})
    assert response.status_code == 200
    assert settings.get_key_for_provider('openai') == 'secret'
    assert settings.get('tavily_api_key') == 'search'
    assert 'secret' not in response.text


def test_invalid_api_settings_do_not_partially_save(isolated):
    settings, _, client = isolated
    response = client.post('/api/settings', json={'llm_model': '', 'provider_api_keys': {'qwen': 'secret'}})
    assert response.status_code == 422
    assert settings.get_key_for_provider('qwen') == ''


def test_environment_key_is_only_for_environment_provider(isolated, monkeypatch):
    monkeypatch.setattr(config.environment_settings, 'llm_provider', 'deepseek')
    monkeypatch.setattr(config.environment_settings, 'llm_api_key', 'env-secret')
    assert config.resolve_api_key('deepseek') == 'env-secret'
    assert config.resolve_api_key('qwen') == ''


def test_history_search_pagination_and_summary(isolated):
    _, tasks, client = isolated
    first = save(tasks, 'Alpha', report='unique needle ' + 'x' * 1000)
    save(tasks, 'Beta', 'cancelled')
    save(tasks, 'ALPHA later')
    result = client.get('/api/tasks', params={'q': 'alpha', 'limit': 1, 'offset': 1, 'summary': True}).json()
    assert result['total'] == 2
    assert result['tasks'][0]['id'] == first
    assert len(result['tasks'][0]['report_excerpt']) <= 240
    assert 'logs' not in result['tasks'][0]
    assert 'final_report' not in result['tasks'][0]
    assert client.get('/api/tasks', params={'q': 'needle', 'status': 'done'}).json()['total'] == 1
    assert client.get('/api/tasks', params={'q': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/api/tasks', params={'q': '%'}).json()['total'] == 0
    assert client.get('/api/tasks').json()['tasks'][0]['logs'] == []


def test_auth_keeps_static_assets_accessible(isolated, monkeypatch):
    _, _, client = isolated
    monkeypatch.setattr(main.settings, 'auth_token', 'secret')
    assert client.get('/').status_code == 200
    assert client.get('/static/workspace.js').status_code == 200
    assert client.get('/api/health').json()['auth_required'] is True
    assert client.get('/api/tasks').status_code == 401
    assert client.get('/api/tasks', headers={'X-Auth-Token': 'secret'}).status_code == 200


@pytest.mark.parametrize('task', ['', '   ', 'x' * 12001, None, []])
def test_invalid_task_rejected(isolated, task):
    _, _, client = isolated
    assert client.post('/api/agent/run', json={'task': task}).status_code == 422
    with client.websocket_connect('/api/agent/stream') as ws:
        ws.send_json({'task': task})
        assert ws.receive_json()['type'] == 'error'


def test_missing_tasks_return_404(isolated):
    _, _, client = isolated
    assert client.get('/api/tasks/9999').status_code == 404
    assert client.delete('/api/tasks/9999').status_code == 404


@pytest.mark.parametrize('phase', ['planner', 'llm', 'reflection', 'analyst', 'decision'])
def test_cancel_interrupts_inflight_wait(phase):
    async def scenario():
        entered = asyncio.Event()
        cancelled = asyncio.Event()
        async def slow(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()
        llm = AsyncMock()
        llm.decide_action.return_value = {'done': True, 'answer': 'complete'}
        planner, reflection, analyst = AsyncMock(), AsyncMock(), AsyncMock()
        planner.plan.return_value = []
        reflection.evaluate.return_value = {'success': True, 'score': 100}
        loop = AgentLoop(AsyncMock(), llm, planner, reflection, analyst)
        loop.set_cancel_event(cancelled)
        if phase == 'planner':
            planner.plan.side_effect = slow
        elif phase == 'llm':
            llm.decide_action.side_effect = slow
        elif phase == 'analyst':
            analyst.generate_report.side_effect = slow
        else:
            llm.decide_action.return_value = {'tool': 'get_text', 'arguments': {}}
            loop.browser.get_text.return_value = {'status': 'success', 'data': {'text': 'evidence'}}
            llm.extract_info.return_value = {'fact': 'evidence'}
            if phase == 'reflection':
                reflection.evaluate.side_effect = slow
            else:
                loop.on_decision(asyncio.Queue(), lambda _: entered.set())
        task = asyncio.create_task(loop.run('test cancellation'))
        await asyncio.wait_for(entered.wait(), 1)
        cancelled.set()
        state = await asyncio.wait_for(task, 1)
        assert state.status == 'cancelled'
        assert state.final_report
        if phase in ('decision', 'reflection'):
            assert state.extracted_info
    asyncio.run(scenario())


def test_disconnect_signals_cancel_and_wakes_followup():
    async def scenario():
        ws = AsyncMock()
        ws.receive_json.side_effect = main.WebSocketDisconnect()
        disconnected, cancelled = asyncio.Event(), asyncio.Event()
        decisions, instructions = asyncio.Queue(), asyncio.Queue()
        await main._message_listener(ws, decisions, instructions, disconnected, cancelled)
        assert disconnected.is_set() and cancelled.is_set()
        assert await asyncio.wait_for(instructions.get(), 0.1) == ''
    asyncio.run(scenario())


def test_log_sender_drains_before_completion():
    async def scenario():
        queue, ws = asyncio.Queue(), AsyncMock()
        for index in range(10):
            queue.put_nowait({'agent': 'System', 'action': str(index)})
        queue.put_nowait(None)
        sender = asyncio.create_task(main._log_sender(ws, queue))
        await asyncio.wait_for(queue.join(), 1)
        await sender
        assert ws.send_json.await_count == 10
    asyncio.run(scenario())
