"""
Ingestion service for parsing ZOLL CPR Report ZIP files.
Handles ZIP extraction, CSV parsing, and metric computation for PCO minutes 1-10.

Option A: Minutes 1-10 start at earliest timestamp in MinuteByMinuteReport.csv.
Weighted averages use "Seconds Analyzed" column when available.
"""
import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.config import get_settings
from app.models import SessionStatus


class IngestionError(Exception):
    """Exception raised when ingestion fails."""
    pass


class IngestionService:
    """Service for ingesting ZOLL CPR Report ZIP files."""

    # Authoritative input CSVs (Rule #4)
    AUTHORITATIVE_CSVS = [
        "Case Statistics.csv",
        "MinuteByMinuteReport.csv",
        "IndividualCompressions.csv",
        "IndividualPauses.csv",
    ]

    # CanROC-formatted CSVs (these have CanROC field names like cr_dpth, cr_cmprt)
    CANROC_CSVS = [
        "CanRocMinuteByMinuteReport.csv",
        "CanRocCPRSegmentsReport.csv",
    ]

    # Required CSVs for import
    REQUIRED_CSVS = ["MinuteByMinuteReport.csv", "Case Statistics.csv"]

    # Column mappings for Case Statistics.csv (authoritative summary metrics)
    # These are ALL the columns from ZOLL export - we store everything but only display key metrics
    CASE_STATS_COLUMNS = {
        # Key display metrics (shown in UI)
        "correct_depth_percent": "% in Target Depth manual",
        "correct_rate_percent": "% in Target Rate manual",
        "compression_rate": "Mean Compression Rate",
        "compression_depth": "Mean Compression Depth (cms)",
        "duration": "Total CPR Period Duration",
        "compression_fraction": "CCF All % in CPR time",

        # Additional metrics (stored, shown in expanded view)
        "seconds_to_first_compression": "Seconds to First Compression",
        "seconds_to_first_shock": "Seconds to First Shock",
        "avg_post_shock_pause": "Average length of post-shock pause (sec)",
        "total_pause_duration": "Total Pause Period Duration",
        "manual_cpr_duration": "Manual CPR Period Duration (sec)",
        "manual_pause_duration": "Manual Pause Period Duration (sec)",
        "total_compressions": "Total Number of Compressions",
        "total_compressions_manual": "Total Number of Compressions manual",
        "percent_not_in_cpr": "% of time Not in CPR",

        # Depth breakdown
        "compressions_in_target_depth": "Compressions in Target Depth manual",
        "compressions_below_target_depth": "Compressions Below Target Depth manual",
        "compressions_above_target_depth": "Compressions Above Target Depth manual",
        "depth_std_dev": "Standard Deviation Depth manual (cms)",

        # Rate breakdown
        "compressions_in_target_rate": "Compressions in Target Rate manual",
        "compressions_below_target_rate": "Compressions Below Target Rate manual",
        "compressions_above_target_rate": "Compressions Above Target Rate manual",
        "rate_std_dev": "Standard Deviation Rate manual",

        # Overall quality
        "compressions_in_target_percent": "Compressions in target % manual",

        # Release velocity
        "mean_release_velocity": "Mean Release Velocity manual",
        "release_velocity_std_dev": "Standard Deviation Release Velocity manual",

        # EtCO2
        "mean_etco2": "Mean EtCO2",
        "max_etco2": "Maximum EtCO2",

        # Target settings (for reference)
        "target_depth_setting": "Target Setting Compression Depth (cms)",
        "target_rate_setting": "Target Setting Compression Rate",
        "target_quality_percent": "Target Setting Compression Quality Percentage",
        "target_ccf_percent": "Target Setting Cpr Fraction Percentage",

        # Tags (semicolon-separated event tags for sorting/visual cues)
        "tags": "Tag(s)",
    }

    # Column mappings for real ZOLL MinuteByMinuteReport.csv (for per-minute PCO data)
    # These are the exact column names from the ZOLL export
    MINUTE_REPORT_COLUMNS = {
        "interval": "Interval",
        "seconds_analyzed": "Seconds Analyzed",
        "seconds_without": "Seconds Without Compression",
        "compression_rate": "Mean Compression Rate",
        "compression_depth": "Mean Compression Depth (cms)",
        "ccf": "Compression Fraction",
        "etco2": "Mean EtCO2",
        "correct_depth_percent": "% Compressions in Target Depth",
        "correct_rate_percent": "% Compressions in Target Rate",
    }

    # CanROC MinuteByMinuteReport columns (Row 0 = CanROC field names, Row 1 = human-readable)
    # Format: CanROC field name -> our internal name
    CANROC_MINUTE_COLUMNS = {
        "cr_dpth": "compression_depth",      # Mean Compression Depth(cm)
        "cr_cmprt": "compression_rate",      # Mean Compression Rate
        "cr_etco2": "etco2",                 # Maximum EtCO2
        "cr_secun": "seconds_without",       # Seconds Without Compression
        "cr_crpff": "ccf",                   # Compression Fraction
    }

    # CanROC CPRSegmentsReport columns - segment start/stop times and reasons
    # Up to 26 segments with 4 fields each: start time, stop time, reason for pause, shock seconds
    CANROC_SEGMENT_FIELDS = ["cr_ecstrttm", "cr_esctoptm", "cr_rsnstp", "cr_rsnkshk"]

    def __init__(self):
        self.settings = get_settings()

    def should_ignore_zip(self, zip_path: Path) -> bool:
        """
        Check if ZIP should be ignored (Rule #5: ignore ZIPs with 'CanRoc' in filename).
        """
        return "canroc" in zip_path.name.lower()

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def ingest_zip(self, zip_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Ingest a ZOLL CPR Report ZIP file.

        Returns:
            Tuple of (metrics_dict, pco_payload)
            - metrics_dict: Flattened metrics for session storage
            - pco_payload: PCO-formatted data for CanROC export

        Raises:
            IngestionError: If ingestion fails for any reason
        """
        if not zip_path.exists():
            raise IngestionError(f"ZIP file not found: {zip_path}")

        # Rule #5: Ignore ZIPs with "CanRoc" in filename
        if self.should_ignore_zip(zip_path):
            raise IngestionError(f"ZIP file ignored: contains 'CanRoc' in filename")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                file_list = zf.namelist()

                # Validate required CSVs are present
                self._validate_required_csvs(file_list)

                # ===== Parse Case Statistics.csv for authoritative summary metrics =====
                case_stats_name = self._find_authoritative_csv(file_list, "Case Statistics.csv")
                if not case_stats_name:
                    raise IngestionError("Case Statistics.csv not found in ZIP")

                with zf.open(case_stats_name) as f:
                    case_stats_content = f.read().decode('utf-8-sig')  # Handle BOM

                # Parse Case Statistics (single row with summary data)
                summary_metrics = self._parse_case_statistics(case_stats_content)

                # ===== Parse MinuteByMinuteReport.csv for per-minute PCO data =====
                minute_csv_name = self._find_authoritative_csv(file_list, "MinuteByMinuteReport.csv")
                if not minute_csv_name:
                    raise IngestionError("MinuteByMinuteReport.csv not found in ZIP")

                with zf.open(minute_csv_name) as f:
                    minute_content = f.read().decode('utf-8-sig')  # Handle BOM

                # Parse the minute-by-minute data
                minute_data = self._parse_minute_by_minute(minute_content)

                if not minute_data:
                    raise IngestionError("No data rows found in MinuteByMinuteReport.csv")

                # Compute PCO metrics for minutes 1-10 with Option A start
                pco_metrics = self._compute_pco_metrics_weighted(minute_data)

                # ===== Parse IndividualPauses.csv for pause quality metrics =====
                pause_metrics = {"pause_count": None, "mean_pause_duration": None,
                                 "max_pause_duration": None, "pauses_over_10s": None}
                pauses_csv_name = self._find_authoritative_csv(file_list, "IndividualPauses.csv")
                if pauses_csv_name:
                    with zf.open(pauses_csv_name) as f:
                        pauses_content = f.read().decode('utf-8-sig')
                    pause_metrics = self._parse_individual_pauses(pauses_content)

                # Build metrics dict for session storage (summary from Case Statistics + PCO data + pauses)
                metrics_dict = {**summary_metrics, **pco_metrics, **pause_metrics}

                # Build PCO payload for CanROC export
                pco_payload = self._build_pco_payload(pco_metrics)

                # ===== Parse CanROC CSV files if present =====
                canroc_minute_data = {}
                canroc_segment_data = {}

                # Parse CanRocMinuteByMinuteReport.csv
                canroc_minute_name = self._find_canroc_csv(file_list, "CanRocMinuteByMinuteReport.csv")
                if canroc_minute_name:
                    with zf.open(canroc_minute_name) as f:
                        canroc_minute_content = f.read().decode('utf-8-sig')
                    canroc_minute_data = self._parse_canroc_minute_by_minute(canroc_minute_content)
                    # Merge CanROC minute data into PCO payload (these have CanROC field names already)
                    if canroc_minute_data:
                        pco_payload.update(canroc_minute_data)

                # Parse CanRocCPRSegmentsReport.csv
                canroc_segment_name = self._find_canroc_csv(file_list, "CanRocCPRSegmentsReport.csv")
                if canroc_segment_name:
                    with zf.open(canroc_segment_name) as f:
                        canroc_segment_content = f.read().decode('utf-8-sig')
                    canroc_segment_data = self._parse_canroc_segments(canroc_segment_content)
                    # Store segment data in metrics for reference
                    if canroc_segment_data:
                        metrics_dict["canroc_segments"] = canroc_segment_data
                        # Also add segment fields to PCO payload (only first 6 segments for PCO template)
                        for seg_num in range(1, 7):
                            for field_base in ["cr_ecstrttm", "cr_esctoptm", "cr_rsnstp", "cr_rsnshk"]:
                                field = f"{field_base}{seg_num}"
                                if field in canroc_segment_data:
                                    pco_payload[field] = canroc_segment_data[field]

                return metrics_dict, pco_payload

        except zipfile.BadZipFile:
            raise IngestionError("Invalid ZIP file format")
        except UnicodeDecodeError as e:
            raise IngestionError(f"Error decoding CSV content: {e}")
        except IngestionError:
            raise
        except Exception as e:
            raise IngestionError(f"Unexpected error during ingestion: {e}")

    def _validate_required_csvs(self, file_list: List[str]) -> None:
        """Validate that all required CSVs are present in the ZIP."""
        for required_csv in self.REQUIRED_CSVS:
            if not self._find_authoritative_csv(file_list, required_csv):
                raise IngestionError(f"Required file '{required_csv}' not found in ZIP")

    def _find_authoritative_csv(self, file_list: List[str], csv_name: str) -> Optional[str]:
        """
        Find an authoritative CSV file in the ZIP (not CanRoc prefixed versions).
        Rule #4: Only use Case Statistics.csv, MinuteByMinuteReport.csv,
                 IndividualCompressions.csv, IndividualPauses.csv
        """
        csv_lower = csv_name.lower()
        for f in file_list:
            fname = f.split('/')[-1].lower()
            # Match exact name, not CanRoc prefixed version
            if fname == csv_lower and not fname.startswith("canroc"):
                return f
        return None

    def _find_canroc_csv(self, file_list: List[str], csv_name: str) -> Optional[str]:
        """
        Find a CanROC CSV file in the ZIP.
        These are the CanRoc-prefixed versions with CanROC field names.
        """
        csv_lower = csv_name.lower()
        for f in file_list:
            fname = f.split('/')[-1].lower()
            if fname == csv_lower:
                return f
        return None

    def _parse_minute_by_minute(self, csv_content: str) -> List[Dict[str, Any]]:
        """
        Parse MinuteByMinuteReport.csv content from ZOLL export.

        Returns list of dictionaries with parsed interval data.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = []

        for row_num, row in enumerate(reader):
            parsed_row = {"row_index": row_num}

            # Extract interval number from "Interval X (datetime - datetime)" format
            interval_str = row.get(self.MINUTE_REPORT_COLUMNS["interval"], "")
            interval_match = re.match(r'Interval\s+(\d+)', interval_str)
            if interval_match:
                parsed_row["interval_num"] = int(interval_match.group(1))
            else:
                parsed_row["interval_num"] = row_num + 1  # Fallback to 1-indexed row

            # Parse numeric columns with null handling
            for internal_name, csv_col in self.MINUTE_REPORT_COLUMNS.items():
                if internal_name == "interval":
                    continue

                value = row.get(csv_col, "")
                if value == "" or value is None:
                    parsed_row[internal_name] = None
                else:
                    try:
                        parsed_row[internal_name] = float(value)
                    except ValueError:
                        # Can't parse as float, leave as None (Rule #1: no hallucination)
                        parsed_row[internal_name] = None

            rows.append(parsed_row)

        return rows

    def _compute_pco_metrics_weighted(self, minute_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute PCO metrics for minutes 1-10 using Option A start and weighted averages.

        Option A: Minutes 1-10 correspond to Interval 1-10 in MinuteByMinuteReport.csv.
        The first interval starts at the earliest timestamp.

        Weighted averages use "Seconds Analyzed" as weights when available.

        PCO fields:
        - cr_cmprt1..10: Compression rate per minute
        - cr_cprff1..10: CPR fraction per minute (CCF)
        - cr_cdpth1..10: Compression depth per minute
        - cr_etco21..10: ETCO2 per minute
        - cr_secun1..10: Seconds without compressions per minute
        """
        pco_metrics = {}

        # Build minute lookup (Option A: Interval N = Minute N)
        minute_lookup = {}
        for row in minute_data:
            interval_num = row.get("interval_num")
            if interval_num and 1 <= interval_num <= 10:
                minute_lookup[interval_num] = row

        # Extract metrics for minutes 1-10
        for minute_num in range(1, 11):
            if minute_num in minute_lookup:
                row = minute_lookup[minute_num]

                # Direct mapping - each interval is one minute
                # No weighted average needed since each row IS one minute
                pco_metrics[f"cr_cmprt{minute_num}"] = self._safe_round(row.get("compression_rate"), 1)
                pco_metrics[f"cr_cprff{minute_num}"] = self._safe_round(row.get("ccf"), 1)
                pco_metrics[f"cr_cdpth{minute_num}"] = self._safe_round(row.get("compression_depth"), 2)
                pco_metrics[f"cr_etco2{minute_num}"] = self._safe_round(row.get("etco2"), 1)
                pco_metrics[f"cr_secun{minute_num}"] = self._safe_round(row.get("seconds_without"), 1)
            else:
                # No data for this minute - leave as None (Rule #1)
                pco_metrics[f"cr_cmprt{minute_num}"] = None
                pco_metrics[f"cr_cprff{minute_num}"] = None
                pco_metrics[f"cr_cdpth{minute_num}"] = None
                pco_metrics[f"cr_etco2{minute_num}"] = None
                pco_metrics[f"cr_secun{minute_num}"] = None

        return pco_metrics

    def _parse_case_statistics(self, csv_content: str) -> Dict[str, Any]:
        """
        Parse Case Statistics.csv for authoritative summary metrics.
        This file has a single data row with the official ZOLL CPR Performance Summary values.

        Captures ALL metrics from ZOLL export for storage. Key metrics are displayed in UI,
        additional metrics available in expanded/detailed view.

        Returns dict with all summary metrics that match ZOLL's reported values.
        """
        reader = csv.DictReader(io.StringIO(csv_content))

        # Case Statistics has only one row
        row = None
        for r in reader:
            row = r
            break

        if not row:
            raise IngestionError("No data row found in Case Statistics.csv")

        metrics = {}

        # Parse ALL metrics from Case Statistics
        for internal_name, csv_col in self.CASE_STATS_COLUMNS.items():
            value = row.get(csv_col, "")
            if value == "" or value is None:
                metrics[internal_name] = None
            else:
                try:
                    parsed = float(value)
                    # Round appropriately based on metric type
                    if internal_name in ["compression_depth", "depth_std_dev"]:
                        metrics[internal_name] = round(parsed, 2)
                    elif internal_name.endswith("_percent") or internal_name.startswith("percent_"):
                        # Percentages - round to 1 decimal
                        metrics[internal_name] = round(parsed, 1)
                    elif internal_name in ["total_compressions", "total_compressions_manual",
                                           "compressions_in_target_depth", "compressions_below_target_depth",
                                           "compressions_above_target_depth", "compressions_in_target_rate",
                                           "compressions_below_target_rate", "compressions_above_target_rate"]:
                        # Counts - round to integer
                        metrics[internal_name] = int(round(parsed))
                    else:
                        # Other numeric values - round to 1 decimal
                        metrics[internal_name] = round(parsed, 1)
                except ValueError:
                    # Non-numeric value (like "5 to 6" for target settings) - store as string
                    metrics[internal_name] = value.strip() if value else None

        return metrics

    def _parse_individual_pauses(self, content: str) -> Dict[str, Any]:
        """
        Parse IndividualPauses.csv for pause quality metrics.

        Reads 'Total pause duration (sec)' column.
        Returns dict with pause_count, mean_pause_duration, max_pause_duration,
        pauses_over_10s. All values None if file is empty or column missing.
        """
        import logging
        _logger = logging.getLogger(__name__)

        empty = {
            "pause_count": None,
            "mean_pause_duration": None,
            "max_pause_duration": None,
            "pauses_over_10s": None,
        }

        try:
            reader = csv.DictReader(io.StringIO(content))
            durations = []

            for row in reader:
                raw = row.get("Total pause duration (sec)")
                if raw is None:
                    return empty
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    durations.append(float(raw))
                except ValueError:
                    _logger.warning(f"IndividualPauses: skipping non-numeric duration: {raw}")

            if not durations:
                return empty

            return {
                "pause_count": len(durations),
                "mean_pause_duration": round(sum(durations) / len(durations), 2),
                "max_pause_duration": round(max(durations), 2),
                "pauses_over_10s": sum(1 for d in durations if d > 10.0),
            }
        except Exception as e:
            _logger.warning(f"IndividualPauses parsing failed: {e}")
            return empty

    def _safe_round(self, value: Any, decimals: int) -> Optional[float]:
        """Safely round a value, returning None if value is None."""
        if value is None:
            return None
        try:
            return round(float(value), decimals)
        except (TypeError, ValueError):
            return None

    def _parse_canroc_minute_by_minute(self, csv_content: str) -> Dict[str, Any]:
        """
        Parse CanRocMinuteByMinuteReport.csv content.

        This file has a unique structure:
        - Row 0: CanROC field names (cr_dpth, cr_cmprt, cr_etco2, cr_secun, cr_crpff)
        - Row 1: Human-readable descriptions
        - Row 2+: Data rows, one per interval (minute)

        The first column is "Interval" with format "Interval N (datetime - datetime)"

        Returns dict with CanROC-formatted field names (cr_dpth1, cr_cmprt1, etc.)
        """
        lines = csv_content.strip().split('\n')
        if len(lines) < 3:
            return {}

        # Row 0 has the CanROC field names
        header_row = lines[0].split(',')
        # Clean headers
        headers = [h.strip() for h in header_row]

        result = {}

        # Data rows start at line 2 (index 2)
        for line_idx, line in enumerate(lines[2:], start=1):
            if not line.strip():
                continue

            # Parse CSV row
            reader = csv.reader(io.StringIO(line))
            try:
                values = next(reader)
            except StopIteration:
                continue

            # Extract interval number from first column
            interval_str = values[0] if values else ""
            interval_match = re.match(r'Interval\s+(\d+)', interval_str)
            if not interval_match:
                continue

            interval_num = int(interval_match.group(1))
            if interval_num > 10:  # Only minutes 1-10 for PCO
                continue

            # Map each CanROC column to numbered field
            for col_idx, header in enumerate(headers):
                if col_idx == 0:  # Skip Interval column
                    continue
                if col_idx >= len(values):
                    continue

                # Header is the CanROC field name (e.g., cr_dpth)
                canroc_field = header.strip()
                if not canroc_field.startswith("cr_"):
                    continue

                value = values[col_idx].strip() if values[col_idx] else ""
                if value:
                    try:
                        # Create numbered field (cr_dpth -> cr_cdpth1 for PCO format)
                        # Note: CanROC uses cr_dpth but PCO template uses cr_cdpth
                        field_mapping = {
                            "cr_dpth": f"cr_cdpth{interval_num}",
                            "cr_cmprt": f"cr_cmprt{interval_num}",
                            "cr_etco2": f"cr_etco2{interval_num}",
                            "cr_secun": f"cr_secun{interval_num}",
                            "cr_crpff": f"cr_cprff{interval_num}",  # Note: crpff -> cprff
                        }
                        if canroc_field in field_mapping:
                            result[field_mapping[canroc_field]] = self._safe_round(float(value), 2)
                    except ValueError:
                        pass

        return result

    def _parse_canroc_segments(self, csv_content: str) -> Dict[str, Any]:
        """
        Parse CanRocCPRSegmentsReport.csv content.

        This file has segment timing data:
        - Row 0: CanROC field names (cr_ecstrttm1, cr_esctoptm1, cr_rsnstp1, cr_rsnkshk1, ...)
        - Row 1: Human-readable descriptions
        - Row 2: Actual data values (datetime values, reasons)
        - Row 3: Additional data (like "Other" reasons)

        Returns dict with segment data for PCO template export.
        Note: PCO template uses cr_rsnshk (not cr_rsnkshk) for shock fields.
        """
        lines = csv_content.strip().split('\n')
        if len(lines) < 3:
            return {}

        # Row 0 has the CanROC field names
        header_row = lines[0].split(',')
        headers = [h.strip() for h in header_row]

        result = {
            "segment_count": 0,
            "segments": [],
        }

        # Data row is at line 2
        if len(lines) > 2:
            reader = csv.reader(io.StringIO(lines[2]))
            try:
                data_values = next(reader)
            except StopIteration:
                return result

            # Also get reason row if available (line 3)
            reason_values = []
            if len(lines) > 3:
                reader2 = csv.reader(io.StringIO(lines[3]))
                try:
                    reason_values = next(reader2)
                except StopIteration:
                    pass

            # Parse segments (up to 26 in CSV, but PCO only has 6)
            for seg_num in range(1, 27):
                # CSV field names
                csv_start = f"cr_ecstrttm{seg_num}"
                csv_stop = f"cr_esctoptm{seg_num}"
                csv_reason = f"cr_rsnstp{seg_num}"
                csv_shock = f"cr_rsnkshk{seg_num}"

                # PCO template field names (slightly different for shock)
                pco_start = f"cr_ecstrttm{seg_num}"
                pco_stop = f"cr_esctoptm{seg_num}"
                pco_reason = f"cr_rsnstp{seg_num}"
                pco_shock = f"cr_rsnshk{seg_num}"  # Note: rsnshk not rsnkshk

                segment_data = {}

                # Map CSV fields to values
                csv_fields = [(csv_start, pco_start), (csv_stop, pco_stop),
                              (csv_reason, pco_reason), (csv_shock, pco_shock)]

                for csv_field, pco_field in csv_fields:
                    if csv_field in headers:
                        col_idx = headers.index(csv_field)
                        if col_idx < len(data_values):
                            val = data_values[col_idx].strip() if data_values[col_idx] else ""
                            if val:
                                segment_data[pco_field] = val
                                # Store with PCO field name
                                result[pco_field] = val

                        # Check reason row for reason text
                        if csv_field == csv_reason and col_idx < len(reason_values):
                            reason_val = reason_values[col_idx].strip() if reason_values[col_idx] else ""
                            if reason_val:
                                segment_data[f"{pco_reason}_text"] = reason_val
                                result[f"{pco_reason}_text"] = reason_val

                # Only add segment if it has start time
                if pco_start in segment_data and segment_data[pco_start]:
                    result["segment_count"] += 1
                    result["segments"].append(segment_data)

        return result

    def _build_pco_payload(self, pco_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build PCO payload for CanROC export.
        Only includes non-None values.
        """
        payload = {}

        for minute_num in range(1, 11):
            for prefix in ["cr_cmprt", "cr_cprff", "cr_cdpth", "cr_etco2", "cr_secun"]:
                key = f"{prefix}{minute_num}"
                value = pco_metrics.get(key)
                if value is not None:
                    payload[key] = value

        return payload


def process_session_import(session_id: str, artifact_path: Path) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Process a session import using the stored artifact.

    Args:
        session_id: The session ID to process
        artifact_path: Path to the stored ZIP artifact

    Returns:
        Tuple of (success, message, metrics_dict)
    """
    from app.services.session_service import get_session_service

    service = get_session_service()
    ingestion = IngestionService()

    try:
        # Ingest the ZIP file
        metrics_dict, pco_payload = ingestion.ingest_zip(artifact_path)

        # Calculate JcLS score for real-call sessions
        session_data = service.get_session(session_id)
        if session_data and session_data.get("session_type") == "real_call":
            from app.services.jcls_service import calculate_jcls_score
            jcls_result = calculate_jcls_score(
                metrics_dict,
                shocks_delivered=session_data.get("shocks_delivered"),
            )
            metrics_dict["jcls_score"] = jcls_result["jcls_score"]
            metrics_dict["jcls_breakdown"] = jcls_result

        # Mark session as complete with metrics
        session = service.mark_session_complete(
            session_id=session_id,
            metrics=metrics_dict,
            canroc_pco_payload=pco_payload,
        )

        # Initialize CanROC wizard states for the session
        if session:
            _initialize_canroc_wizards(session, pco_payload)

        return True, "Import successful", metrics_dict

    except IngestionError as e:
        # Mark session as failed with error message
        service.mark_session_failed(session_id, str(e))
        return False, str(e), None

    except Exception as e:
        # Mark session as failed with unexpected error
        error_msg = f"Unexpected error: {e}"
        service.mark_session_failed(session_id, error_msg)
        return False, error_msg, None


def _initialize_canroc_wizards(session: Dict[str, Any], pco_payload: Dict[str, Any]) -> None:
    """
    Initialize CanROC wizard states for a newly imported session.

    Creates wizard states for both Master and PCO templates with:
    - PCO fields auto-filled from ZIP parsing (provenance=zip_autofill)
    - Master fields left empty (user must complete manually)
    """
    from app.services.wizard_service import get_wizard_service
    from app.models import Session, FieldProvenance
    from app.mock_data import update_session

    try:
        wizard_service = get_wizard_service()

        # Convert dict to Session model
        session_model = Session(**session)

        # Initialize PCO wizard (with autofilled data from ZIP)
        pco_wizard = wizard_service.initialize_wizard(session_model, "pco")

        # Pre-fill PCO wizard with ZIP autofill data
        if pco_payload:
            for field_id, value in pco_payload.items():
                if value is not None:
                    wizard_service.upsert_field(
                        pco_wizard,
                        field_id,
                        str(value),
                        provenance=FieldProvenance.ZIP_AUTOFILL
                    )

        # Initialize Master wizard (mostly empty, user must complete)
        master_wizard = wizard_service.initialize_wizard(session_model, "master")

        # Pre-fill some Master fields from session data
        if session.get("date"):
            wizard_service.upsert_field(
                master_wizard,
                "cr_epdt",
                session["date"],
                provenance=FieldProvenance.ZIP_AUTOFILL
            )

        # Save wizard states to session
        update_session(session["id"], {
            "canroc_wizard_pco": pco_wizard.model_dump(),
            "canroc_wizard_master": master_wizard.model_dump(),
        })

    except Exception as e:
        # Log but don't fail the import if wizard init fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to initialize CanROC wizards for session {session.get('id')}: {e}")


def parse_simulated_csv(content: str) -> List[Dict[str, Any]]:
    """
    Parse CSV/text data from simulated manikin software.

    Expected Claude-generated format (17 columns):
    0: Date, 1: Provider, 2: Team_Members (blank), 3: Event_Type (Simulated),
    4: Compressions, 5: Duration_Sec, 6: Mean_Depth_cm,
    7: Depth_Compliance_Strict_%, 8: Depth_Compliance_Lenient_%,
    9: Mean_Rate_CPM, 10: Rate_Compliance_Strict_%, 11: Rate_Compliance_Lenient_%,
    12: Overall_Compliance_Strict_%, 13: Overall_Compliance_Lenient_%,
    14: Grade_Strict, 15: Grade_Lenient, 16: Notes

    Returns list of parsed session data dictionaries.
    """
    parsed_rows = []

    lines = content.strip().split('\n')
    if not lines:
        return []

    # Skip empty lines
    data_lines = [line.strip() for line in lines if line.strip()]
    if not data_lines:
        return []

    # Check if first line looks like a header
    first_line = data_lines[0].lower()
    has_header = any(header in first_line for header in ['date', 'provider', 'name', 'duration', 'rate', 'depth', 'compliance'])
    start_idx = 1 if has_header else 0

    for line in data_lines[start_idx:]:
        # Handle both comma and tab delimiters
        if '\t' in line:
            parts = line.split('\t')
        else:
            reader = csv.reader(io.StringIO(line))
            try:
                parts = next(reader)
            except StopIteration:
                continue

        if len(parts) < 3:
            continue

        # Clean up parts
        parts = [p.strip() for p in parts]
        row_data = {}

        # Column 0: Date
        if parts[0]:
            row_data["date"] = parts[0]

        # Column 1: Provider name
        if len(parts) > 1 and parts[1]:
            row_data["provider_name"] = parts[1]

        # Claude-generated format with 17 columns
        if len(parts) >= 12:
            # Column 5: Duration_Sec
            if len(parts) > 5 and parts[5]:
                try:
                    row_data["duration"] = int(float(parts[5]))
                except ValueError:
                    pass

            # Column 6: Mean_Depth_cm
            if len(parts) > 6 and parts[6]:
                try:
                    row_data["compression_depth"] = round(float(parts[6]), 2)
                except ValueError:
                    pass

            # Column 7: Depth_Compliance_Strict_% (we use strict as primary)
            if len(parts) > 7 and parts[7]:
                try:
                    row_data["correct_depth_percent"] = round(float(parts[7]), 1)
                except ValueError:
                    pass

            # Column 9: Mean_Rate_CPM
            if len(parts) > 9 and parts[9]:
                try:
                    row_data["compression_rate"] = round(float(parts[9]), 1)
                except ValueError:
                    pass

            # Column 10: Rate_Compliance_Strict_% (we use strict as primary)
            if len(parts) > 10 and parts[10]:
                try:
                    row_data["correct_rate_percent"] = round(float(parts[10]), 1)
                except ValueError:
                    pass

            # Column 16: Notes
            if len(parts) > 16 and parts[16]:
                row_data["notes"] = parts[16]

        else:
            # Simple format - try to detect columns by value ranges
            numeric_cols = []
            for i, part in enumerate(parts):
                if i < 2:
                    continue
                if part and part.lower() not in ['simulated', 'real_call', '']:
                    try:
                        numeric_cols.append((i, float(part)))
                    except ValueError:
                        if i >= len(parts) - 2 and len(part) > 5:
                            row_data["notes"] = part

            for idx, val in numeric_cols:
                if "duration" not in row_data and 10 <= val <= 600:
                    row_data["duration"] = int(val)
                elif "compression_depth" not in row_data and 3 <= val <= 8:
                    row_data["compression_depth"] = round(val, 2)
                elif "compression_rate" not in row_data and 80 <= val <= 160:
                    row_data["compression_rate"] = round(val, 1)
                elif "correct_depth_percent" not in row_data and 0 <= val <= 100:
                    row_data["correct_depth_percent"] = round(val, 1)
                elif "correct_rate_percent" not in row_data and 0 <= val <= 100:
                    row_data["correct_rate_percent"] = round(val, 1)

        # Only add rows that have at least a date or provider
        if row_data.get("date") or row_data.get("provider_name"):
            parsed_rows.append(row_data)

    return parsed_rows


def process_simulated_import(
    content: str,
    fallback_date: Optional[str] = None,
    fallback_provider_id: Optional[str] = None,
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """
    Process simulated session import from CSV/paste text.

    Args:
        content: CSV or pasted text content
        fallback_date: Date to use if not in CSV row
        fallback_provider_id: Provider ID to use if name not matched

    Returns:
        Tuple of (success, message, list of created session dictionaries)
    """
    from app.mock_data import PROVIDERS, create_session, update_session_status
    from app.models import SessionType, SessionStatus

    try:
        parsed_rows = parse_simulated_csv(content)

        if not parsed_rows:
            return False, "No valid data rows found in the input", []

        created_sessions = []

        for row in parsed_rows:
            # Determine date
            date = row.get("date") or fallback_date
            if not date:
                continue

            # Try to match provider name to existing provider
            provider_id = None
            provider_name = row.get("provider_name", "")
            if provider_name:
                # Find matching provider (case-insensitive partial match)
                provider_name_lower = provider_name.lower()
                for provider in PROVIDERS:
                    if provider.get("status") == "active":
                        prov_name = provider.get("name", "")
                        if provider_name_lower in prov_name.lower() or prov_name.lower() in provider_name_lower:
                            provider_id = provider["id"]
                            break

            # Fall back to provided provider ID
            if not provider_id:
                provider_id = fallback_provider_id

            # Create the session
            session = create_session(
                session_type=SessionType.SIMULATED,
                date=date,
                time=None,
                event_type="Simulated",
                primary_provider_id=provider_id,
                participant_ids=[provider_id] if provider_id else [],
            )

            # Build metrics from parsed data
            metrics = {
                "duration": row.get("duration", 0),
                "compression_rate": row.get("compression_rate", 0),
                "compression_depth": row.get("compression_depth", 0),
                "correct_depth_percent": row.get("correct_depth_percent", 0),
                "correct_rate_percent": row.get("correct_rate_percent", 0),
            }

            # Mark session complete with metrics
            update_session_status(
                session_id=session["id"],
                status=SessionStatus.COMPLETE,
                metrics=metrics,
            )
            session["status"] = SessionStatus.COMPLETE.value
            session["metrics"] = metrics

            created_sessions.append(session)

        if created_sessions:
            return True, f"Successfully imported {len(created_sessions)} session(s)", created_sessions
        else:
            return False, "No sessions could be created from the input data", []

    except Exception as e:
        return False, f"Error parsing data: {e}", []


# Singleton instance
_ingestion_service: Optional[IngestionService] = None


def get_ingestion_service() -> IngestionService:
    """Get the singleton ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service
