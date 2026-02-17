"""
Tests for the ingestion service.
Tests ZIP unpacking, validation, and metric computation.
"""
import csv
import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.services.ingestion_service import (
    IngestionService,
    IngestionError,
    process_session_import,
    get_ingestion_service,
)
from app.models import SessionStatus


class TestIngestionService:
    """Tests for IngestionService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = IngestionService()

    def _create_zoll_minute_csv(self, intervals: list[dict]) -> str:
        """
        Create CSV content matching real ZOLL MinuteByMinuteReport.csv format.

        Each interval represents one minute of data with columns:
        - Interval: "Interval N (timestamp - timestamp)"
        - Seconds Analyzed
        - Seconds Without Compression
        - Mean Compression Rate
        - Mean Compression Depth (cms)
        - Compression Fraction
        - Mean EtCO2
        - % Compressions in Target Depth
        - % Compressions in Target Rate
        """
        csv_buffer = io.StringIO()
        fieldnames = [
            "Interval",
            "Seconds Analyzed",
            "Seconds Without Compression",
            "Mean Compression Rate",
            "Mean Compression Depth (cms)",
            "Compression Fraction",
            "Mean EtCO2",
            "% Compressions in Target Depth",
            "% Compressions in Target Rate",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in intervals:
            writer.writerow(row)
        return csv_buffer.getvalue()

    def _create_case_statistics_csv(
        self,
        correct_depth_percent: float = 73.0,
        correct_rate_percent: float = 95.0,
        compression_rate: float = 110.0,
        compression_depth: float = 5.5,
        duration: float = 180.0,
        ccf: float = 85.0,
        total_compressions: int = 6000,
    ) -> str:
        """
        Create CSV content matching real ZOLL Case Statistics.csv format.
        This is the authoritative source for summary metrics.
        """
        csv_buffer = io.StringIO()
        fieldnames = [
            "Seconds to First Compression",
            "Seconds to First Shock",
            "Average length of post-shock pause (sec)",
            "Mean Compression Depth (cms)",
            "Mean Compression Rate",
            "Total CPR Period Duration",
            "Total Pause Period Duration",
            "CCF All % in CPR time",
            "CCF All % in pause time",
            "Manual CPR Period Duration (sec)",
            "Manual Pause Period Duration (sec)",
            "Total Number of Compressions",
            "Total Number of Compressions manual",
            "% of time Not in CPR",
            "Compressions in Target Depth manual",
            "Compressions Below Target Depth manual",
            "Compressions Above Target Depth manual",
            "% in Target Depth manual",
            "Standard Deviation Depth manual (cms)",
            "Compressions in Target Rate manual",
            "Compressions Below Target Rate manual",
            "Compressions Above Target Rate manual",
            "% in Target Rate manual",
            "Standard Deviation Rate manual",
            "Compressions in target % manual",
            "Mean Release Velocity manual",
            "Standard Deviation Release Velocity manual",
            "Mean EtCO2",
            "Maximum EtCO2",
            "Target Setting Compression Depth (cms)",
            "Target Setting Compression Rate",
            "Target Setting Compression Quality Percentage",
            "Target Setting Cpr Fraction Percentage",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()

        # Calculate counts from percentages
        compressions_in_depth = int(total_compressions * correct_depth_percent / 100)
        compressions_in_rate = int(total_compressions * correct_rate_percent / 100)

        writer.writerow({
            "Seconds to First Compression": 55.0,
            "Seconds to First Shock": 0,
            "Average length of post-shock pause (sec)": 0,
            "Mean Compression Depth (cms)": compression_depth,
            "Mean Compression Rate": compression_rate,
            "Total CPR Period Duration": duration,
            "Total Pause Period Duration": 20.0,
            "CCF All % in CPR time": ccf,
            "CCF All % in pause time": 15.0,
            "Manual CPR Period Duration (sec)": duration,
            "Manual Pause Period Duration (sec)": 20.0,
            "Total Number of Compressions": total_compressions,
            "Total Number of Compressions manual": total_compressions,
            "% of time Not in CPR": 7.5,
            "Compressions in Target Depth manual": compressions_in_depth,
            "Compressions Below Target Depth manual": 200,
            "Compressions Above Target Depth manual": total_compressions - compressions_in_depth - 200,
            "% in Target Depth manual": correct_depth_percent,
            "Standard Deviation Depth manual (cms)": 0.5,
            "Compressions in Target Rate manual": compressions_in_rate,
            "Compressions Below Target Rate manual": 100,
            "Compressions Above Target Rate manual": total_compressions - compressions_in_rate - 100,
            "% in Target Rate manual": correct_rate_percent,
            "Standard Deviation Rate manual": 5.5,
            "Compressions in target % manual": 70.0,
            "Mean Release Velocity manual": 400.0,
            "Standard Deviation Release Velocity manual": 50.0,
            "Mean EtCO2": 35.0,
            "Maximum EtCO2": 45.0,
            "Target Setting Compression Depth (cms)": "5 to 6",
            "Target Setting Compression Rate": "100 to 120",
            "Target Setting Compression Quality Percentage": 60,
            "Target Setting Cpr Fraction Percentage": 60,
        })
        return csv_buffer.getvalue()

    def _create_test_zip(
        self,
        intervals: list[dict],
        include_minute_csv: bool = True,
        include_case_stats: bool = True,
        extra_files: dict = None,
        csv_path: str = "MinuteByMinuteReport.csv",
        case_stats_kwargs: dict = None,
    ) -> Path:
        """
        Create a test ZIP file with MinuteByMinuteReport.csv and Case Statistics.csv.

        Args:
            intervals: List of dicts with ZOLL column values (one per minute)
            include_minute_csv: Whether to include MinuteByMinuteReport.csv
            include_case_stats: Whether to include Case Statistics.csv
            extra_files: Dict of filename -> content to add to ZIP
            csv_path: Path within ZIP for the MinuteByMinuteReport.csv file
            case_stats_kwargs: Optional kwargs for _create_case_statistics_csv

        Returns:
            Path to the created ZIP file
        """
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        with zipfile.ZipFile(zip_path, 'w') as zf:
            if include_minute_csv and intervals:
                csv_content = self._create_zoll_minute_csv(intervals)
                zf.writestr(csv_path, csv_content)

            if include_case_stats:
                # Create Case Statistics with default or custom values
                kwargs = case_stats_kwargs or {}
                case_stats_content = self._create_case_statistics_csv(**kwargs)
                zf.writestr("Case Statistics.csv", case_stats_content)

            if extra_files:
                for filename, content in extra_files.items():
                    zf.writestr(filename, content)

        return Path(zip_path)

    def _cleanup_zip(self, zip_path: Path):
        """Clean up test ZIP file."""
        if zip_path.exists():
            zip_path.unlink()

    def _make_interval(
        self,
        interval_num: int,
        seconds_analyzed: float = 60.0,
        seconds_without: float = 5.0,
        compression_rate: float = 110.0,
        compression_depth: float = 5.5,
        ccf: float = 85.0,
        etco2: float = 35.0,
        correct_depth: float = 75.0,
        correct_rate: float = 80.0,
    ) -> dict:
        """Create a single interval row with ZOLL column names."""
        return {
            "Interval": f"Interval {interval_num} (2025-01-01 00:{interval_num-1:02d}:00 - 2025-01-01 00:{interval_num:02d}:00)",
            "Seconds Analyzed": seconds_analyzed,
            "Seconds Without Compression": seconds_without,
            "Mean Compression Rate": compression_rate,
            "Mean Compression Depth (cms)": compression_depth,
            "Compression Fraction": ccf,
            "Mean EtCO2": etco2,
            "% Compressions in Target Depth": correct_depth,
            "% Compressions in Target Rate": correct_rate,
        }

    def test_ingest_valid_zip(self):
        """Test ingesting a valid ZIP file with both required CSVs."""
        # Create 3 intervals (3 minutes) of data for per-minute PCO metrics
        intervals = [
            self._make_interval(1, compression_rate=108, compression_depth=5.2, ccf=82),
            self._make_interval(2, compression_rate=112, compression_depth=5.5, ccf=88),
            self._make_interval(3, compression_rate=115, compression_depth=5.6, ccf=90),
        ]

        # Create ZIP with both MinuteByMinuteReport.csv and Case Statistics.csv
        zip_path = self._create_test_zip(
            intervals,
            case_stats_kwargs={
                "duration": 180.0,
                "compression_rate": 110.0,
                "compression_depth": 5.5,
                "ccf": 85.0,
                "correct_depth_percent": 73.0,
                "correct_rate_percent": 95.0,
            }
        )

        try:
            metrics, pco_payload = self.service.ingest_zip(zip_path)

            # Check summary metrics (from Case Statistics.csv)
            assert metrics["duration"] == 180.0
            assert metrics["compression_rate"] == 110.0
            assert metrics["compression_depth"] == 5.5
            assert metrics["compression_fraction"] == 85.0
            assert metrics["correct_depth_percent"] == 73.0
            assert metrics["correct_rate_percent"] == 95.0

            # Check PCO metrics for minutes 1-3 (from MinuteByMinuteReport.csv)
            assert metrics["cr_cmprt1"] == 108
            assert metrics["cr_cmprt2"] == 112
            assert metrics["cr_cmprt3"] == 115

            # Check PCO payload
            assert "cr_cmprt1" in pco_payload
            assert "cr_cdpth1" in pco_payload

        finally:
            self._cleanup_zip(zip_path)

    def test_ingest_missing_csv_fails(self):
        """Test that ingestion fails if MinuteByMinuteReport.csv is missing."""
        # Create ZIP without MinuteByMinuteReport.csv
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("SomeOtherFile.csv", "col1,col2\n1,2\n")

        zip_path = Path(zip_path)

        try:
            with pytest.raises(IngestionError) as exc_info:
                self.service.ingest_zip(zip_path)

            assert "MinuteByMinuteReport.csv" in str(exc_info.value)

        finally:
            self._cleanup_zip(zip_path)

    def test_ingest_invalid_zip_fails(self):
        """Test that ingestion fails for invalid ZIP files."""
        # Create a non-ZIP file
        fd, bad_path = tempfile.mkstemp(suffix=".zip")
        os.write(fd, b"This is not a ZIP file")
        os.close(fd)
        bad_path = Path(bad_path)

        try:
            with pytest.raises(IngestionError) as exc_info:
                self.service.ingest_zip(bad_path)

            assert "Invalid ZIP file" in str(exc_info.value)

        finally:
            if bad_path.exists():
                bad_path.unlink()

    def test_ingest_nonexistent_file_fails(self):
        """Test that ingestion fails for nonexistent files."""
        with pytest.raises(IngestionError) as exc_info:
            self.service.ingest_zip(Path("/nonexistent/path/file.zip"))

        assert "not found" in str(exc_info.value)

    def test_pco_metrics_computed_correctly(self):
        """Test that PCO metrics are computed correctly for each minute."""
        # Create exactly 10 intervals with known values
        intervals = []
        for minute in range(1, 11):
            intervals.append(self._make_interval(
                interval_num=minute,
                compression_rate=100 + minute,  # 101, 102, ..., 110 CPM
                compression_depth=5.0 + minute * 0.1,  # 5.1, 5.2, ..., 6.0 cm
                ccf=80 + minute,  # 81, 82, ..., 90%
                etco2=30 + minute,  # 31, 32, ..., 40 mmHg
                seconds_without=minute * 0.5,  # 0.5, 1.0, ..., 5.0 sec
            ))

        zip_path = self._create_test_zip(intervals)

        try:
            metrics, pco_payload = self.service.ingest_zip(zip_path)

            # Check that all 10 minutes have metrics
            for minute in range(1, 11):
                assert metrics.get(f"cr_cmprt{minute}") is not None
                assert metrics.get(f"cr_cprff{minute}") is not None
                assert metrics.get(f"cr_cdpth{minute}") is not None

            # Check specific values (exact match since each interval is 1 minute)
            assert metrics["cr_cmprt1"] == 101
            assert metrics["cr_cmprt10"] == 110
            assert metrics["cr_cdpth1"] == 5.1
            assert metrics["cr_cprff1"] == 81

        finally:
            self._cleanup_zip(zip_path)

    def test_correct_depth_percent_extraction(self):
        """Test that correct depth % is extracted from Case Statistics.csv."""
        intervals = [
            self._make_interval(1, correct_depth=50.0),
            self._make_interval(2, correct_depth=60.0),
        ]

        # Correct depth % now comes from Case Statistics.csv (authoritative source)
        zip_path = self._create_test_zip(
            intervals,
            case_stats_kwargs={"correct_depth_percent": 73.5}
        )

        try:
            metrics, _ = self.service.ingest_zip(zip_path)

            # Value should match Case Statistics.csv exactly
            assert metrics["correct_depth_percent"] == 73.5

        finally:
            self._cleanup_zip(zip_path)

    def test_correct_rate_percent_extraction(self):
        """Test that correct rate % is extracted from Case Statistics.csv."""
        intervals = [
            self._make_interval(1, correct_rate=70.0, seconds_analyzed=60),
            self._make_interval(2, correct_rate=80.0, seconds_analyzed=60),
        ]

        # Correct rate % now comes from Case Statistics.csv (authoritative source)
        zip_path = self._create_test_zip(
            intervals,
            case_stats_kwargs={"correct_rate_percent": 94.5}
        )

        try:
            metrics, _ = self.service.ingest_zip(zip_path)

            # Value should match Case Statistics.csv exactly
            assert metrics["correct_rate_percent"] == 94.5

        finally:
            self._cleanup_zip(zip_path)

    def test_option_a_interval_mapping(self):
        """Test Option A: Interval N directly maps to Minute N."""
        # Create data with intervals 1-5
        intervals = [
            self._make_interval(1, compression_rate=105),
            self._make_interval(2, compression_rate=110),
            self._make_interval(3, compression_rate=115),
            self._make_interval(4, compression_rate=108),
            self._make_interval(5, compression_rate=112),
        ]

        zip_path = self._create_test_zip(intervals)

        try:
            metrics, _ = self.service.ingest_zip(zip_path)

            # Interval 1 = Minute 1, Interval 2 = Minute 2, etc.
            assert metrics["cr_cmprt1"] == 105
            assert metrics["cr_cmprt2"] == 110
            assert metrics["cr_cmprt3"] == 115
            assert metrics["cr_cmprt4"] == 108
            assert metrics["cr_cmprt5"] == 112

            # Minutes 6-10 should be None (no data)
            assert metrics["cr_cmprt6"] is None
            assert metrics["cr_cmprt10"] is None

        finally:
            self._cleanup_zip(zip_path)

    def test_empty_csv_raises_error(self):
        """Test that empty MinuteByMinuteReport.csv (header only) raises IngestionError."""
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        with zipfile.ZipFile(zip_path, 'w') as zf:
            # MinuteByMinuteReport.csv with just headers, no data rows
            minute_headers = ",".join([
                "Interval",
                "Seconds Analyzed",
                "Seconds Without Compression",
                "Mean Compression Rate",
                "Mean Compression Depth (cms)",
                "Compression Fraction",
                "Mean EtCO2",
                "% Compressions in Target Depth",
                "% Compressions in Target Rate",
            ])
            zf.writestr("MinuteByMinuteReport.csv", minute_headers + "\n")

            # Include valid Case Statistics.csv
            case_stats_content = self._create_case_statistics_csv()
            zf.writestr("Case Statistics.csv", case_stats_content)

        zip_path = Path(zip_path)

        try:
            with pytest.raises(IngestionError) as exc_info:
                self.service.ingest_zip(zip_path)

            assert "No data rows" in str(exc_info.value)

        finally:
            self._cleanup_zip(zip_path)

    def test_nested_csv_in_zip(self):
        """Test finding CSV in nested directory within ZIP."""
        intervals = [self._make_interval(1, compression_rate=110)]

        zip_path = self._create_test_zip(
            intervals,
            csv_path="CPR_Data/Reports/MinuteByMinuteReport.csv"
        )

        try:
            metrics, _ = self.service.ingest_zip(zip_path)
            assert metrics["cr_cmprt1"] == 110

        finally:
            self._cleanup_zip(zip_path)

    def test_ignores_canroc_prefixed_csv(self):
        """Test that CanRoc-prefixed CSV files are ignored (Rule #4)."""
        # Create ZIP with both CanRoc and regular MinuteByMinuteReport.csv
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        # Regular version with correct data
        regular_intervals = [self._make_interval(1, compression_rate=110)]
        regular_csv = self._create_zoll_minute_csv(regular_intervals)

        # CanRoc version with different (wrong) data
        canroc_intervals = [self._make_interval(1, compression_rate=999)]
        canroc_csv = self._create_zoll_minute_csv(canroc_intervals)

        # Include valid Case Statistics.csv
        case_stats_content = self._create_case_statistics_csv()

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("MinuteByMinuteReport.csv", regular_csv)
            zf.writestr("CanRocMinuteByMinuteReport.csv", canroc_csv)
            zf.writestr("Case Statistics.csv", case_stats_content)

        zip_path = Path(zip_path)

        try:
            metrics, _ = self.service.ingest_zip(zip_path)
            # Should use the regular CSV (110), not the CanRoc one (999)
            assert metrics["cr_cmprt1"] == 110

        finally:
            self._cleanup_zip(zip_path)

    def test_ignores_canroc_zip_filename(self):
        """Test that ZIP files with 'CanRoc' in filename are rejected (Rule #5)."""
        intervals = [self._make_interval(1)]

        fd, zip_path = tempfile.mkstemp(suffix="_CanRoc_Export.zip")
        os.close(fd)

        csv_content = self._create_zoll_minute_csv(intervals)
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("MinuteByMinuteReport.csv", csv_content)

        zip_path = Path(zip_path)

        try:
            with pytest.raises(IngestionError) as exc_info:
                self.service.ingest_zip(zip_path)

            assert "CanRoc" in str(exc_info.value)

        finally:
            self._cleanup_zip(zip_path)

    def test_weighted_average_with_different_seconds_analyzed(self):
        """Test that summary metrics come from Case Statistics.csv, not calculated."""
        # MinuteByMinuteReport.csv intervals (for per-minute PCO data)
        intervals = [
            self._make_interval(1, compression_rate=100, seconds_analyzed=30),
            self._make_interval(2, compression_rate=110, seconds_analyzed=60),
        ]

        # Summary metrics come from Case Statistics.csv (authoritative source)
        zip_path = self._create_test_zip(
            intervals,
            case_stats_kwargs={"compression_rate": 106.7}
        )

        try:
            metrics, _ = self.service.ingest_zip(zip_path)

            # Summary rate should come from Case Statistics.csv
            assert metrics["compression_rate"] == 106.7

            # Per-minute rates should still come from MinuteByMinuteReport.csv
            assert metrics["cr_cmprt1"] == 100
            assert metrics["cr_cmprt2"] == 110

        finally:
            self._cleanup_zip(zip_path)

    def test_null_values_handled_gracefully(self):
        """Test that null/empty values in MinuteByMinuteReport.csv don't crash parsing."""
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        # Create MinuteByMinuteReport.csv with some empty values
        csv_content = """Interval,Seconds Analyzed,Seconds Without Compression,Mean Compression Rate,Mean Compression Depth (cms),Compression Fraction,Mean EtCO2,% Compressions in Target Depth,% Compressions in Target Rate
Interval 1 (2025-01-01 00:00:00 - 2025-01-01 00:01:00),60,5,110,5.5,85,,75,80
Interval 2 (2025-01-01 00:01:00 - 2025-01-01 00:02:00),60,,112,5.6,88,38,78,
"""

        # Create valid Case Statistics.csv
        case_stats_content = self._create_case_statistics_csv()

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("MinuteByMinuteReport.csv", csv_content)
            zf.writestr("Case Statistics.csv", case_stats_content)

        zip_path = Path(zip_path)

        try:
            metrics, pco_payload = self.service.ingest_zip(zip_path)

            # Should still parse successfully - per-minute metrics from MinuteByMinuteReport.csv
            assert metrics["cr_cmprt1"] == 110
            assert metrics["cr_cmprt2"] == 112

            # Null ETCO2 for minute 1
            assert metrics["cr_etco21"] is None
            assert metrics["cr_etco22"] == 38

        finally:
            self._cleanup_zip(zip_path)

    def test_file_hash_computation(self):
        """Test that file hash is computed correctly."""
        intervals = [self._make_interval(1)]
        zip_path = self._create_test_zip(intervals)

        try:
            hash1 = self.service.compute_file_hash(zip_path)
            hash2 = self.service.compute_file_hash(zip_path)

            # Hash should be consistent
            assert hash1 == hash2
            # Hash should be 64 characters (SHA-256 hex)
            assert len(hash1) == 64

        finally:
            self._cleanup_zip(zip_path)


class TestProcessSessionImport:
    """Tests for the process_session_import function."""

    def _create_zoll_minute_csv(self, intervals: list[dict]) -> str:
        """Create CSV content matching real ZOLL format."""
        csv_buffer = io.StringIO()
        fieldnames = [
            "Interval",
            "Seconds Analyzed",
            "Seconds Without Compression",
            "Mean Compression Rate",
            "Mean Compression Depth (cms)",
            "Compression Fraction",
            "Mean EtCO2",
            "% Compressions in Target Depth",
            "% Compressions in Target Rate",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in intervals:
            writer.writerow(row)
        return csv_buffer.getvalue()

    def _make_interval(self, interval_num: int, **kwargs) -> dict:
        """Create a single interval row."""
        defaults = {
            "Interval": f"Interval {interval_num} (2025-01-01 00:{interval_num-1:02d}:00 - 2025-01-01 00:{interval_num:02d}:00)",
            "Seconds Analyzed": 60.0,
            "Seconds Without Compression": 5.0,
            "Mean Compression Rate": 110.0,
            "Mean Compression Depth (cms)": 5.5,
            "Compression Fraction": 85.0,
            "Mean EtCO2": 35.0,
            "% Compressions in Target Depth": 75.0,
            "% Compressions in Target Rate": 80.0,
        }
        defaults.update(kwargs)
        return defaults

    def _create_case_statistics_csv(self) -> str:
        """Create Case Statistics.csv content."""
        csv_buffer = io.StringIO()
        fieldnames = [
            "Seconds to First Compression",
            "Mean Compression Depth (cms)",
            "Mean Compression Rate",
            "Total CPR Period Duration",
            "CCF All % in CPR time",
            "% in Target Depth manual",
            "% in Target Rate manual",
            "Compressions in target % manual",
            "Total Number of Compressions manual",
            "Mean EtCO2",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({
            "Seconds to First Compression": 55.0,
            "Mean Compression Depth (cms)": 5.5,
            "Mean Compression Rate": 110.0,
            "Total CPR Period Duration": 120.0,
            "CCF All % in CPR time": 85.0,
            "% in Target Depth manual": 73.0,
            "% in Target Rate manual": 95.0,
            "Compressions in target % manual": 70.0,
            "Total Number of Compressions manual": 6000,
            "Mean EtCO2": 35.0,
        })
        return csv_buffer.getvalue()

    def _create_test_zip(self, intervals: list) -> Path:
        """Create a test ZIP file with both required CSVs."""
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        csv_content = self._create_zoll_minute_csv(intervals)
        case_stats_content = self._create_case_statistics_csv()

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("MinuteByMinuteReport.csv", csv_content)
            zf.writestr("Case Statistics.csv", case_stats_content)

        return Path(zip_path)

    def test_process_session_import_success(self):
        """Test successful session import."""
        from app.mock_data import create_session, get_session_by_id, SESSIONS
        from app.models import SessionType

        # Create a test session
        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
            time="12:00:00",
            event_type="Cardiac Arrest",
        )
        session_id = session["id"]

        # Create test ZIP with 2 intervals
        intervals = [
            self._make_interval(1),
            self._make_interval(2),
        ]
        zip_path = self._create_test_zip(intervals)

        try:
            success, message, metrics = process_session_import(session_id, zip_path)

            assert success is True
            assert metrics is not None
            assert "compression_rate" in metrics

            # Check session was updated
            updated_session = get_session_by_id(session_id)
            assert updated_session["status"] == SessionStatus.COMPLETE.value

        finally:
            if zip_path.exists():
                zip_path.unlink()
            # Clean up session from SESSIONS
            SESSIONS[:] = [s for s in SESSIONS if s["id"] != session_id]

    def test_process_session_import_failure(self):
        """Test session import failure marks session as failed."""
        from app.mock_data import create_session, get_session_by_id, SESSIONS
        from app.models import SessionType

        # Create a test session
        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
            time="12:00:00",
            event_type="Cardiac Arrest",
        )
        session_id = session["id"]

        # Create invalid ZIP (missing required CSV)
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("WrongFile.csv", "test")
        zip_path = Path(zip_path)

        try:
            success, message, metrics = process_session_import(session_id, zip_path)

            assert success is False
            assert "MinuteByMinuteReport.csv" in message
            assert metrics is None

            # Check session was marked as failed
            updated_session = get_session_by_id(session_id)
            assert updated_session["status"] == SessionStatus.FAILED.value
            assert updated_session["error_message"] is not None

        finally:
            if zip_path.exists():
                zip_path.unlink()
            # Clean up session from SESSIONS
            SESSIONS[:] = [s for s in SESSIONS if s["id"] != session_id]


class TestIngestionServiceSingleton:
    """Test singleton behavior."""

    def test_get_ingestion_service_returns_same_instance(self):
        """Test that get_ingestion_service returns the same instance."""
        service1 = get_ingestion_service()
        service2 = get_ingestion_service()
        assert service1 is service2
