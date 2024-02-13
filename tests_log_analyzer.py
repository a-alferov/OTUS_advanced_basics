from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase
import gzip
import tempfile

from log_analyzer import get_last_sample, get_lines, get_preparatory_data, get_report_data


class TestLogAnalyzer(TestCase):
    def test_get_last_sample_empty_dir(self):
        with tempfile.TemporaryDirectory() as log_dir:
            filename, data = get_last_sample(log_dir=Path(log_dir))
            self.assertIsNone(filename)
            self.assertIsNone(data)

    def test_get_last_sample_not_supported_format(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)

            with open(log_dir / "nginx-access-ui.log-20170630.bz", "wb") as f:
                f.write(b"")

            filename, data = get_last_sample(log_dir=Path(log_dir))
            self.assertIsNone(filename)
            self.assertIsNone(data)

    def test_get_last_sample_txt_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)

            with open(log_dir / "nginx-access-ui.log-20170630.txt", "wb") as f:
                f.write(b"")

            filename, data = get_last_sample(log_dir=Path(log_dir))
            self.assertIsNotNone(filename)
            self.assertTrue(filename.is_file())
            self.assertEqual(datetime.strptime("20170630", "%Y%m%d").replace(tzinfo=timezone.utc), data)

    def test_get_last_sample_gz_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)

            with open(log_dir / "nginx-access-ui.log-20170630.gz", "wb") as f:
                f.write(b"")

            filename, data = get_last_sample(log_dir=Path(log_dir))
            self.assertIsNotNone(filename)
            self.assertTrue(filename.is_file())
            self.assertEqual(datetime.strptime("20170630", "%Y%m%d").replace(tzinfo=timezone.utc), data)

    def test_get_lines_empty_txt_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)
            filename = log_dir / "nginx-access-ui.log-20170630.txt"

            with open(filename, "w") as f:
                f.write("")

            lines = get_lines(filename=filename)
            self.assertEqual(0, len(list(lines)))

    def test_get_lines_empty_gz_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)
            filename = log_dir / "nginx-access-ui.log-20170630.gz"

            with gzip.open(filename, "wb") as f:
                f.write(b"")

            lines = get_lines(filename=filename)
            self.assertEqual(0, len(list(lines)))

    def test_get_lines_not_empty_txt_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)
            filename = log_dir / "nginx-access-ui.log-20170630.txt"

            with open(filename, "w") as f:
                f.writelines(
                    [
                        '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927'
                        ' "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-"'
                        ' "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390'
                    ]
                )

            lines = list(get_lines(filename=filename))
            self.assertEqual(1, len(lines))
            self.assertEqual(("/api/v2/banner/25019354", 0.39), lines[0])

    def test_get_lines_not_empty_gz_file(self):
        with tempfile.TemporaryDirectory() as log_dir:
            log_dir = Path(log_dir)
            filename = log_dir / "nginx-access-ui.log-20170630.gz"

            with gzip.open(filename, "wb") as f:
                f.writelines(
                    [
                        b'1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927'
                        b' "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-"'
                        b' "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390'
                    ]
                )

            lines = list(get_lines(filename=filename))
            self.assertEqual(1, len(lines))
            self.assertEqual(("/api/v2/banner/25019354", 0.39), lines[0])

    def test_get_preparatory_data(self):
        lines = (log_item for log_item in [("/api/v2/banner/25019354", 0.39)])

        total_count, total_time, data = get_preparatory_data(lines=lines)

        self.assertEqual(1, total_count)
        self.assertEqual(0.39, total_time)
        self.assertDictEqual({"/api/v2/banner/25019354": {"count": 1, "times": [0.39]}}, data)

    def test_get_report_data(self):
        preparatory_data = {"/api/v2/banner/25019354": {"count": 1, "times": [0.39]}}

        data = list(get_report_data(total_count=1, total_time=0.39, data=preparatory_data))

        self.assertEqual(1, len(data))
        self.assertDictEqual(
            {
                "count": 1,
                "count_perc": 1.0,
                "time_avg": 0.39,
                "time_max": 0.39,
                "time_med": 0.39,
                "time_perc": 1.0,
                "time_sum": 0.39,
                "url": "/api/v2/banner/25019354",
            },
            data[0],
        )
