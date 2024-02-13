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
TEMPLATE_STRING = """
<!doctype html>

<html lang="en">
<head>
    <meta charset="utf-8">
    <title>rbui log analysis report</title>
    <meta name="description" content="rbui log analysis report">
    <style type="text/css">
        html, body {
            background-color: black;
        }

        th {
            text-align: center;
            color: silver;
            font-style: bold;
            padding: 5px;
            cursor: pointer;
        }

        table {
            width: auto;
            border-collapse: collapse;
            margin: 1%;
            color: silver;
        }

        td {
            text-align: right;
            font-size: 1.1em;
            padding: 5px;
        }

        .report-table-body-cell-url {
            text-align: left;
            width: 20%;
        }

        .clipped {
            white-space: nowrap;
            text-overflow: ellipsis;
            overflow: hidden !important;
            max-width: 700px;
            word-wrap: break-word;
            display: inline-block;
        }

        .url {
            cursor: pointer;
            color: #729FCF;
        }

        .alert {
            color: red;
        }
    </style>
</head>

<body>
<table border="1" class="report-table">
    <thead>
    <tr class="report-table-header-row">
    </tr>
    </thead>
    <tbody class="report-table-body">
    </tbody>

    <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/3.2.1/jquery.min.js"></script>
    <script type="text/javascript" src="jquery.tablesorter.min.js"></script>
    <script type="text/javascript">
        !function ($) {
            var table = $table_json;
            var reportDates;
            var columns = new Array();
            var lastRow = 150;
            var $table = $(".report-table-body");
            var $header = $(".report-table-header-row");
            var $selector = $(".report-date-selector");

            $(document).ready(function () {
                $(window).bind("scroll", bindScroll);
                var row = table[0];
                for (k in row) {
                    columns.push(k);
                }
                columns = columns.sort();
                columns = columns.slice(
                    columns.length - 1, columns.length).concat(columns.slice(0, columns.length - 1));
                drawColumns();
                drawRows(table.slice(0, lastRow));
                $(".report-table").tablesorter();
            });

            function drawColumns() {
                for (var i = 0; i < columns.length; i++) {
                    var $th = $("<th></th>").text(columns[i])
                        .addClass("report-table-header-cell")
                    $header.append($th);
                }
            }

            function drawRows(rows) {
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var $row = $("<tr></tr>").addClass("report-table-body-row");
                    for (var j = 0; j < columns.length; j++) {
                        var columnName = columns[j];
                        var $cell = $("<td></td>").addClass("report-table-body-cell");
                        if (columnName == "url") {
                            var url = "https://rb.mail.ru" + row[columnName];
                            var $link = $("<a></a>").attr("href", url)
                                .attr("title", url)
                                .attr("target", "_blank")
                                .addClass("clipped")
                                .addClass("url")
                                .text(row[columnName]);
                            $cell.addClass("report-table-body-cell-url");
                            $cell.append($link);
                        } else {
                            $cell.text(row[columnName]);
                            if (columnName == "time_avg" && row[columnName] > 0.9) {
                                $cell.addClass("alert");
                            }
                        }
                        $row.append($cell);
                    }
                    $table.append($row);
                }
                $(".report-table").trigger("update");
            }

            function bindScroll() {
                if ($(window).scrollTop() == $(document).height() - $(window).height()) {
                    if (lastRow < 1000) {
                        drawRows(table.slice(lastRow, lastRow + 50));
                        lastRow += 50;
                    }
                }
            }

        }(window.jQuery)
    </script>
</body>
</html>
"""
REPORT_TEMPLATE = Template(template=TEMPLATE_STRING)
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
    opener = open
    global NUMBER_OF_MISTAKES

    if filename.suffix == ".gz":
        opener = gzip.open

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


def prepare_report(data: Generator[dict, None, None], report_file: Path, report_size: int) -> None:
    with report_file.open("w") as file:
        file.write(
            REPORT_TEMPLATE.safe_substitute(
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
    prepare_report(data=data, report_file=report_file, report_size=config.getint("REPORT_SIZE"))


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
                }
            }
        )

        config = config_parser["DEFAULT"]
        config_parser.read(config_file)
        logging.basicConfig(
            filename=config.get("LOG_FILE"), format="[%(asctime)s] %(levelname).1s %(message)s", level=logging.INFO
        )

        main(config=config)

    except Exception:
        logging.exception("Found an error")
    except KeyboardInterrupt:
        logging.exception("Program interrupted by user.")
    except SystemExit:
        logging.exception("Request to exit from the interpreter.")
