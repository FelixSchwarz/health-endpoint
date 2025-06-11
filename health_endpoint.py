
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

import tomllib
from flask import Flask, abort, current_app, request


class ServerConfig(NamedTuple):
    path_health_json: Path
    api_token: str | None


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
    )
    _flask.extensions['health-endpoint'] = server_config
    return _flask


# ,--- flask handlers ---------------------------------------------------------
@_flask.route('/health')
def health():
    if not is_authorized():
        abort(401)
    health_data = load_health_json()
    return health_data


@_flask.route('/health/detailed')
def health_detailed():
    if not is_authorized():
        abort(401)
    health_data = load_health_json(detailed=True)
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
    debug = sys.stdin.isatty()
    app.run(host='0.0.0.0', port=5005, debug=debug)
