# OTUS Advanced Basics

## deco.py

This script contains examples of decorators

## log_analyzer.py

This script is for parsing NGINX logs.

Log format:
```
$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" $request_time
```
The script requires a settings file in `ini` format. By default `config.ini`

Example settings file:
```ini
[DEFAULT]
REPORT_SIZE = 1000
REPORT_DIR = ./reports
LOG_DIR = ./log
LOG_FILE = debug.log
```

Example of running script:
```shell
python log_analyzer.py --config config.ini
```
