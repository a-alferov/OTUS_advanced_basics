#!/usr/bin/env python
from argparse import ArgumentParser
from collections import defaultdict
from configparser import ConfigParser, SectionProxy
from datetime import datetime, timezone
from operator import itemgetter
from pathlib import Path
from statistics import median
from string import Template
from typing import Generator, TypeAlias
import re
import gzip
import json
import logging

PreparatoryData: TypeAlias = dict[str, dict[str, int | list]]

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

LOG_FORMAT_PATTERN = r'".+? (.+?) .+?" .+ (\d+\.\d+)'
FILENAME_PATTERN = r"(nginx-access-ui.log-)(\d{8})\.(gz|txt)"
ERROR_RATE = 0.2
NUMBER_OF_MISTAKES = 0


def get_last_sample(log_dir: Path) -> tuple[Path | None, datetime | None]:
    date = None
    filename = None

    for file in log_dir.iterdir():
        if not file.is_file():
            continue

        match = re.match(pattern=FILENAME_PATTERN, string=file.name)
        if match is None:
            continue

        new_filename = file
        new_date = datetime.strptime(match.groups()[1], "%Y%m%d").replace(tzinfo=timezone.utc)

        if date is None:
            date = new_date
            filename = new_filename
        else:
            if new_date > date:
                date = new_date
                filename = file

    return filename, date


def get_lines(filename: Path) -> Generator[tuple[str, float], None, None]:
    opener = gzip.open if filename.suffix == ".gz" else open
    global NUMBER_OF_MISTAKES

    with opener(filename, mode="rb") as f:
        for line in f.readlines():
            match = re.search(LOG_FORMAT_PATTERN, line.decode("UTF-8"))

            if match is None:
                NUMBER_OF_MISTAKES += 1
                logging.error("Logging format has been changed")
                continue
            try:
                request, request_time = match.group(1), float(match.group(2))
            except ValueError:
                NUMBER_OF_MISTAKES += 1
                logging.exception("Logging format could not be parsed")
                continue

            yield request, request_time


def get_preparatory_data(lines: Generator[tuple[str, float], None, None]) -> tuple[int, float, PreparatoryData]:
    data = defaultdict(lambda: {"count": 0, "times": []})
    total_count = 0
    total_time = 0.0

    for request, request_time in lines:
        request_time = request_time
        data[request]["count"] += 1
        data[request]["times"].append(request_time)
        total_count += 1
        total_time += request_time

    return total_count, total_time, data


def get_report_data(total_count: int, total_time: float, data: PreparatoryData) -> Generator[dict, None, None]:
    for url, preparatory_data in data.items():
        count = preparatory_data["count"]
        time_sum = round(sum(preparatory_data["times"]), 3)

        yield {
            "url": url,
            "count": count,
            "time_avg": round(time_sum / count, 3),
            "time_max": round(max(preparatory_data["times"]), 3),
            "time_sum": time_sum,
            "time_med": round(median(preparatory_data["times"]), 3),
            "time_perc": round(time_sum / total_time, 3),
            "count_perc": round(count / total_count, 3),
        }


def prepare_report(
    data: Generator[dict, None, None], report_file: Path, report_size: int, report_template: Path
) -> None:
    with report_file.open("w") as file:
        file.write(
            Template(template=report_template.read_text(encoding="UTF-8")).safe_substitute(
                table_json=json.dumps(sorted(data, key=itemgetter("time_sum"), reverse=True)[:report_size])
            )
        )

    logging.info(f"Wrote report to '{report_file}'")


def main(config: SectionProxy) -> None:
    filename, date = get_last_sample(log_dir=Path(config.get("LOG_DIR")))

    if filename is None:
        logging.info("No log file")
        return

    logging.info(f"Parsing file '{filename}'")

    report_dir = Path(config.get("REPORT_DIR"))
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f'report-{date.strftime(format="%Y.%m.%d")}.html'

    if report_file.exists():
        logging.info("The report already exists")
        return

    lines = get_lines(filename=filename)
    total_count, total_time, preparatory_data = get_preparatory_data(lines=lines)

    if total_count != 0 and NUMBER_OF_MISTAKES / total_count > ERROR_RATE:
        logging.error("The number of errors exceeds the acceptable threshold")
        return

    logging.info(f"Error rate: {NUMBER_OF_MISTAKES / total_count if total_count != 0 else 0}")

    data = get_report_data(total_count=total_count, total_time=total_time, data=preparatory_data)
    prepare_report(
        data=data,
        report_file=report_file,
        report_size=config.getint("REPORT_SIZE"),
        report_template=Path(config.get("REPORT_TEMPLATE")),
    )


if __name__ == "__main__":
    try:
        parser = ArgumentParser(description="Prepare report for NGINX logs")
        parser.add_argument(
            "--config",
            type=str,
            default="config.ini",
            help="Path to config file. Default: config.ini",
        )
        args = parser.parse_args()

        config_file = Path(args.config)
        if not config_file.exists():
            raise FileNotFoundError("Config file not found.")

        config_parser = ConfigParser()
        config_parser.read_dict(
            {
                "DEFAULT": {
                    "REPORT_SIZE": 1000,
                    "REPORT_DIR": "./reports",
                    "LOG_DIR": "./log",
                    "REPORT_TEMPLATE": "./report.html",
                }
            }
        )
        config = config_parser["DEFAULT"]
        config_parser.read(config_file)

        logging.basicConfig(
            filename=config.get("LOG_FILE"), format="[%(asctime)s] %(levelname).1s %(message)s", level=logging.INFO
        )

        if Path(config.get("REPORT_TEMPLATE")).exists():
            main(config=config)
        else:
            logging.error("No such report template file: 'report.html'")

    except Exception:
        logging.exception("Found an error")
    except KeyboardInterrupt:
        logging.exception("Program interrupted by user.")
    except SystemExit:
        logging.exception("Request to exit from the interpreter.")
