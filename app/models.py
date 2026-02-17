"""
Pydantic models for CPR Tracking System.
These models define the data structures for sessions, providers, and related entities.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SessionType(str, Enum):
    """Type of CPR session."""
    REAL_CALL = "real_call"
    SIMULATED = "simulated"


class SessionStatus(str, Enum):
    """Status of session import/processing."""
    IMPORTING = "importing"
    COMPLETE = "complete"
    FAILED = "failed"


class ResuscitationStatus(str, Enum):
    """Whether resuscitation was attempted on a cardiac arrest call."""
    YES = "yes"
    NO = "no"


class ZollMissingReason(str, Enum):
    """Reason why Zoll data is not available."""
    NOT_UPLOADED = "not_uploaded"           # Device data not uploaded yet
    DEVICE_MALFUNCTION = "device_malfunction"  # Device failed to record
    NO_RESUSCITATION = "no_resuscitation"   # No CPR performed (auto-set when resus=no)
    UNKNOWN = "unknown"                     # Other/unknown reason


# ============================================================
# CanROC Wizard Models - Schema-Driven Completion Wizard
# ============================================================

class FieldProvenance(str, Enum):
    """Source of field value."""
    ZIP_AUTOFILL = "zip_autofill"       # Auto-extracted from ZOLL ZIP
    WIZARD_MANUAL = "wizard_manual"      # User-entered in wizard
    CANNOT_OBTAIN = "cannot_obtain"      # Marked as CNO by user
    MISSING_MARKER = "missing_marker"    # Normalized blank to "."


class FieldValueState(str, Enum):
    """State of a field value."""
    EMPTY = "empty"           # No value yet
    FILLED = "filled"         # Has a value
    CNO = "cno"               # Cannot Obtain
    NORMALIZED = "normalized" # Blank normalized to "."


class WizardCompletionStatus(str, Enum):
    """Wizard completion status."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class WizardPageStatus(str, Enum):
    """Individual page status."""
    NOT_STARTED = "not_started"
    PARTIAL = "partial"
    COMPLETE = "complete"
    SKIPPED = "skipped"


class CanrocFieldValue(BaseModel):
    """Individual field value with provenance tracking."""
    field_id: str             # cr_* code from Row 1 of Excel template
    value: Optional[str] = None  # Actual value or "." for normalized blank
    provenance: FieldProvenance = FieldProvenance.WIZARD_MANUAL
    state: FieldValueState = FieldValueState.EMPTY
    cno_reason: Optional[str] = None  # Optional reason for CNO
    updated_at: datetime = Field(default_factory=datetime.now)


class CanrocWizardState(BaseModel):
    """Tracks wizard progress for a session."""
    session_id: str
    template_id: str                    # "master" or "pco"
    current_page: int = 1
    total_pages: int = 18               # Master has 18 pages, PCO has 13
    status: WizardCompletionStatus = WizardCompletionStatus.NOT_STARTED
    page_statuses: Dict[int, WizardPageStatus] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_saved_at: Optional[datetime] = None
    completion_percent: float = 0.0

    # Field values stored by field_id (cr_* code)
    field_values: Dict[str, CanrocFieldValue] = Field(default_factory=dict)

    # Missing required fields for completion
    missing_required: List[str] = Field(default_factory=list)


class SessionMetrics(BaseModel):
    """CPR performance metrics for a session."""
    duration: Optional[float] = None  # seconds
    compression_rate: Optional[float] = None  # CPM
    compression_depth: Optional[float] = None  # cm
    compression_fraction: Optional[float] = None  # percentage (legacy, kept for data)
    release_percent: Optional[float] = None  # percentage
    correct_depth_percent: Optional[float] = None  # Depth compliance %
    correct_rate_percent: Optional[float] = None  # Rate compliance %

    # Extended metrics for Real Calls (minutes 1-10)
    # Compression rate per minute
    cr_cmprt1: Optional[float] = None
    cr_cmprt2: Optional[float] = None
    cr_cmprt3: Optional[float] = None
    cr_cmprt4: Optional[float] = None
    cr_cmprt5: Optional[float] = None
    cr_cmprt6: Optional[float] = None
    cr_cmprt7: Optional[float] = None
    cr_cmprt8: Optional[float] = None
    cr_cmprt9: Optional[float] = None
    cr_cmprt10: Optional[float] = None

    # CPR fraction per minute
    cr_cprff1: Optional[float] = None
    cr_cprff2: Optional[float] = None
    cr_cprff3: Optional[float] = None
    cr_cprff4: Optional[float] = None
    cr_cprff5: Optional[float] = None
    cr_cprff6: Optional[float] = None
    cr_cprff7: Optional[float] = None
    cr_cprff8: Optional[float] = None
    cr_cprff9: Optional[float] = None
    cr_cprff10: Optional[float] = None

    # Compression depth per minute
    cr_cdpth1: Optional[float] = None
    cr_cdpth2: Optional[float] = None
    cr_cdpth3: Optional[float] = None
    cr_cdpth4: Optional[float] = None
    cr_cdpth5: Optional[float] = None
    cr_cdpth6: Optional[float] = None
    cr_cdpth7: Optional[float] = None
    cr_cdpth8: Optional[float] = None
    cr_cdpth9: Optional[float] = None
    cr_cdpth10: Optional[float] = None

    # ETCO2 per minute
    cr_etco21: Optional[float] = None
    cr_etco22: Optional[float] = None
    cr_etco23: Optional[float] = None
    cr_etco24: Optional[float] = None
    cr_etco25: Optional[float] = None
    cr_etco26: Optional[float] = None
    cr_etco27: Optional[float] = None
    cr_etco28: Optional[float] = None
    cr_etco29: Optional[float] = None
    cr_etco210: Optional[float] = None

    # Seconds without compressions per minute
    cr_secun1: Optional[float] = None
    cr_secun2: Optional[float] = None
    cr_secun3: Optional[float] = None
    cr_secun4: Optional[float] = None
    cr_secun5: Optional[float] = None
    cr_secun6: Optional[float] = None
    cr_secun7: Optional[float] = None
    cr_secun8: Optional[float] = None
    cr_secun9: Optional[float] = None
    cr_secun10: Optional[float] = None

    # ── Pause metrics (from IndividualPauses.csv) ──
    pause_count: Optional[int] = None
    mean_pause_duration: Optional[float] = None  # seconds
    max_pause_duration: Optional[float] = None   # seconds
    pauses_over_10s: Optional[int] = None

    # ── JcLS Score (real-call only) ──
    jcls_score: Optional[int] = None             # 0-100, scaled
    jcls_breakdown: Optional[Dict[str, Any]] = None  # full tier breakdown


class SessionParticipant(BaseModel):
    """A practitioner participating in a session."""
    provider_id: str
    provider_name: str
    is_primary: bool = False  # True if this is the primary practitioner


class SessionArtifact(BaseModel):
    """Reference to an uploaded artifact (ZIP file, CSV, etc.)."""
    filename: str
    original_filename: str
    file_path: str
    content_type: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    """CPR session record."""
    id: str
    session_type: SessionType
    status: SessionStatus = SessionStatus.IMPORTING
    date: str  # YYYY-MM-DD
    time: Optional[str] = None  # HH:MM:SS
    event_type: Optional[str] = None  # Cardiac Arrest, Simulated, etc.
    outcome: Optional[str] = None  # ROSC, No ROSC, etc.

    # Provider linkage (primary provider for backwards compatibility)
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None

    # Multiple participants support
    participants: List[SessionParticipant] = []

    # Team assignment
    team_id: Optional[str] = None

    # Platoon assignment (A, B, C, D)
    platoon: Optional[str] = None

    # Zoll data availability (for Real Call sessions)
    zoll_data_available: bool = True  # Default True - most sessions have data
    resuscitation_attempted: Optional[str] = None  # ResuscitationStatus value or None
    zoll_missing_reason: Optional[str] = None  # ZollMissingReason value or None
    shocks_delivered: Optional[int] = None  # Number of shocks (if no Zoll data but known)

    # Performance metrics
    metrics: SessionMetrics = Field(default_factory=SessionMetrics)

    # Import artifact reference (for retry capability)
    artifact: Optional[SessionArtifact] = None

    # Error tracking for failed imports
    error_message: Optional[str] = None

    # CanROC payload data (stored after processing)
    canroc_master_payload: Optional[Dict[str, Any]] = None
    canroc_pco_payload: Optional[Dict[str, Any]] = None

    # CanROC Wizard state for completion wizard
    canroc_wizard_master: Optional[CanrocWizardState] = None
    canroc_wizard_pco: Optional[CanrocWizardState] = None

    # CanROC completion flags
    canroc_master_complete: bool = False
    canroc_pco_complete: bool = False

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Request/Response models for API endpoints

class SessionCreateRequest(BaseModel):
    """Request model for creating a new session."""
    session_type: SessionType
    date: str
    time: Optional[str] = None
    event_type: Optional[str] = None
    primary_provider_id: Optional[str] = None
    participant_ids: List[str] = []


class SimulatedSessionData(BaseModel):
    """Data for simulated session (from CSV or paste)."""
    provider_name: str
    date: str
    event_type: str = "Simulated"
    metrics: SessionMetrics


class SessionRetryRequest(BaseModel):
    """Request model for retrying a failed session import."""
    session_id: str


class SessionResponse(BaseModel):
    """Response model for session data."""
    id: str
    session_type: SessionType
    status: SessionStatus
    date: str
    time: Optional[str] = None
    event_type: Optional[str] = None
    provider_name: Optional[str] = None
    participants: List[SessionParticipant] = []
    metrics: SessionMetrics
    error_message: Optional[str] = None
    created_at: datetime
