#!/usr/bin/env python3
"""
collect-health-metrics.py [--detailed] --config=/path/to/config.toml
"""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from datetime import datetime as DateTime, timezone


try:
    import tomllib
except ImportError:
    import tomli as tomllib


def collect_health_metrics_main():
    parser = argparse.ArgumentParser(description='Collect health metrics.')
    parser.add_argument('--detailed', action='store_true', help='Output detailed health JSON.')
    parser.add_argument('--config', required=True, help='Path to TOML config file.')
    args = parser.parse_args()

    with open(args.config, 'rb') as toml_fp:
        config = tomllib.load(toml_fp)
    if args.detailed:
        health_data = generate_detailed_health_json(config)
    else:
        health_data = generate_basic_health_json(config)

    print(json.dumps(health_data, indent=2))
    is_degraded = (health_data['status'] == 'degraded')
    sys.exit(1 if is_degraded else 0)


def is_systemd_unit_enabled(unit_name: str) -> bool:
    cmd = ['systemctl', 'is-enabled', unit_name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout.strip() in ('enabled', 'static')
    except Exception:
        return False


def is_systemd_unit_active(unit_name: str) -> bool:
    cmd = ['systemctl', 'is-active', unit_name]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout.strip() == 'active'
    except Exception:
        return False


def generate_detailed_health_json(config: Mapping) -> dict:
    components = {}
    for check_name, check in config.items():
        if not isinstance(check, dict):
            # web-related config: api-token, health-data, ...
            continue
        check_type = check['type']
        if check_type == 'number_files':
            directory = check['directory']
            max_files = check['max_files']
            _result = check_file_count(directory, max_files=max_files)
        elif check_type == 'systemd':
            unit = check['unit']
            _result = check_systemd_unit(unit)
        else:
            raise ValueError(f'Unknown check type: {check_type}')
        components[check_name] = _result

    is_overall_healthy = ('degraded' not in {_c['status'] for _c in components.values()})
    return {
        'status': 'healthy' if is_overall_healthy else 'degraded',
        'timestamp': DateTime.now(timezone.utc).isoformat(timespec='seconds') + 'Z',
        'components': components
    }


def generate_basic_health_json(config: Mapping) -> dict:
    health_data = generate_detailed_health_json(config)
    del health_data['components']
    return health_data


def _count_files_in_directory(directory: str) -> int | None:
    try:
        return len([f for f in os.listdir(directory)])
    except (OSError, PermissionError):
        return None

def check_file_count(directory_path: str, max_files: int) -> dict:
    try:
        file_count = _count_files_in_directory(directory_path)
        if (file_count is None) or (file_count > max_files):
            status = 'degraded'
        else:
            status = 'healthy'
        return {'status': status}
    except (OSError, PermissionError) as e:
        return {'status': 'degraded', 'details': str(e)}


def check_systemd_unit(unit: str) -> dict:
    if not unit.endswith(('.service', '.timer')):
        unit_name = unit + '.service'
    else:
        unit_name = unit

    is_enabled = is_systemd_unit_enabled(unit_name)
    if unit_name.endswith('.timer'):
        is_running = is_enabled
    else:
        is_running = is_systemd_unit_active(unit_name)

    is_healthy = is_enabled and is_running
    return {
        'status': 'healthy' if is_healthy else 'degraded',
        'unit': unit_name,
    }


if __name__ == '__main__':
    collect_health_metrics_main()
