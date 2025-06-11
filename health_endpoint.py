
import json
import os
import sys
from datetime import datetime as DateTime, timezone
from pathlib import Path
from typing import NamedTuple


try:
    import tomllib
except ImportError:
    import tomli as tomllib
from flask import Flask, abort, current_app, request


class ServerConfig(NamedTuple):
    path_health_json: Path
    api_token: str | None
    max_data_age: int


_flask = Flask('health-endpoint', static_folder=None, template_folder=None)

def init_app() -> Flask:
    config_path = os.environ.get('HEALTH_CONFIG')
    if not config_path:
        raise ValueError('HEALTH_CONFIG environment variable is not set')
    try:
        with open(config_path, 'rb') as toml_fp:
            toml_config = tomllib.load(toml_fp)
    except Exception as e:
        sys.stderr.write(f'Error loading config from {config_path}: {e}\n')
        sys.exit(1)

    server_config = ServerConfig(
        path_health_json  = Path(toml_config['health-data']),
        api_token         = toml_config.get('api-token'),
        max_data_age      = toml_config.get('max-age', 600)
    )
    _flask.extensions['health-endpoint'] = server_config
    return _flask


# ,--- flask handlers ---------------------------------------------------------
@_flask.route('/health')
def health():
    if not is_authorized():
        abort(401)
    health_data = load_health_json()
    if health_data.get('status') != 'healthy':
        return health_data, 503
    return health_data


@_flask.route('/health/detailed')
def health_detailed():
    if not is_authorized():
        abort(401)
    health_data = load_health_json(detailed=True)
    if health_data.get('status') != 'healthy':
        return health_data, 503
    return health_data
# `--- flask handlers ---------------------------------------------------------


def load_health_json(*, detailed: bool = False) -> dict:
    config = current_app.extensions['health-endpoint']
    try:
        with config.path_health_json.open() as json_fp:
           health_data = json.load(json_fp)
    except FileNotFoundError:
        return {'status': 'unknown', 'error': 'Not health data available'}
    if not detailed:
        health_data.pop('components')

    is_health_data_recent = False
    generation_time = health_data.get('timestamp')
    if generation_time:
        generation_time = DateTime.fromisoformat(generation_time.rstrip('Z'))
        now = DateTime.now(timezone.utc)
        age = (now - generation_time).total_seconds()
        is_health_data_recent = (age < (10 * 60))  # less than 10 minutes
    if not is_health_data_recent:
        return {'status': 'unknown', 'error': 'Health data is too old'}
    return health_data


def is_authorized() -> bool:
    if current_app.debug:
        return True
    config = current_app.extensions['health-endpoint']
    if not config.api_token:
        return False
    token = request.headers.get('X-API-Token')
    return token and (token == config.api_token)

if __name__ == '__main__':
    app = init_app()
    debug = ('--debug' in sys.argv)
    app.run(host='0.0.0.0', port=5005, debug=debug)
