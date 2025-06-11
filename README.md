# health endpoint

This project provides a best-practice solution for exposing a `/health` HTTP endpoint, making it easy to monitor the health of your system. It consists of a simple Flask web application that serves health status information as JSON, protected by an API token.

## Features

- Exposes `/health` and `/health/detailed` endpoints for system health checks.
- Health data is served as JSON and access is restricted via a predefined API token.
- Health metrics are collected by a separate script and stored as a JSON file, ensuring strong separation between the web app (minimal system access) and the collector (which may require root privileges).
- Configurable health checks (currently supports counting files in a directory and checking systemd services/timers for enabled/active status).


## Usage

### Create config file `health.toml`

```
api-token = '123456'
health-data = 'health-data.json'
# max-age = 600

[log_files]
type = "number_files"
directory = "/data/logs"
max_files = 20

[dnf_automatic]
type = "systemd"
unit = "dnf-automatic timer"
```

### Create a systemd timer for the collector

The timer should run this command:

`collect-health-metrics --detailed --config=health.toml --output=health-data.json`

This will produce the `health-data.json` file which will be read by the web server.


### Use a WSGI server to run the flask server

Example:

`/usr/bin/gunicorn health_endpoint:wsgi_app`

You need to define the environment variable `HEALTH_CONFIG=/path/to/health.toml`


## Dependencies

- Python 3.9+
- `flask`
- `tomli` (for Python < 3.11)
- A WSGI server (e.g., `gunicorn`)
