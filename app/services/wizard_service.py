"""
Wizard Service for CanROC Completion Wizard.
Handles wizard state management, field operations, and completion logic.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from app.models import (
    Session,
    CanrocWizardState,
    CanrocFieldValue,
    FieldProvenance,
    FieldValueState,
    WizardCompletionStatus,
    WizardPageStatus,
)
from app.services.schema_service import get_schema_service, SchemaService

logger = logging.getLogger(__name__)


class WizardService:
    """Service for managing CanROC wizard state and operations."""

    def __init__(self, schema_service: Optional[SchemaService] = None):
        self.schema_service = schema_service or get_schema_service()

    def normalize_value(self, value: Any, field_type: str = "text", field_def: Optional[Dict] = None) -> Tuple[str, FieldValueState]:
        """
        Normalize a field value to canonical form.

        Args:
            value: The raw value
            field_type: The field type (text, integer, float, choice, etc.)
            field_def: Optional field definition for additional context

        Returns:
            Tuple of (normalized_value, state)
        """
        # Handle None and empty strings
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return ".", FieldValueState.NORMALIZED

        # Handle the missing marker
        if isinstance(value, str) and value.strip() == ".":
            return ".", FieldValueState.NORMALIZED

        # Type-specific normalization
        str_value = str(value).strip()

        if field_type == "integer":
            try:
                return str(int(float(str_value))), FieldValueState.FILLED
            except (ValueError, TypeError):
                return str_value, FieldValueState.FILLED

        elif field_type == "float":
            try:
                decimals = field_def.get("decimals", 2) if field_def else 2
                return f"{float(str_value):.{decimals}f}", FieldValueState.FILLED
            except (ValueError, TypeError):
                return str_value, FieldValueState.FILLED

        return str_value, FieldValueState.FILLED

    def initialize_wizard(
        self,
        session: Session,
        template_id: str,
        autofill_from_payload: bool = True
    ) -> CanrocWizardState:
        """
        Initialize wizard state for a session.

        Args:
            session: The session to initialize wizard for
            template_id: "master" or "pco"
            autofill_from_payload: Whether to pre-fill from existing payloads

        Returns:
            Initialized CanrocWizardState
        """
        schema = self.schema_service.load_schema(template_id)
        total_pages = len(schema.get("pages", []))

        wizard_state = CanrocWizardState(
            session_id=session.id,
            template_id=template_id,
            current_page=1,
            total_pages=total_pages,
            status=WizardCompletionStatus.IN_PROGRESS,
            started_at=datetime.now(),
            last_saved_at=datetime.now(),
        )

        # Initialize page statuses
        for page in schema.get("pages", []):
            page_id = page["page_id"]
            wizard_state.page_statuses[page_id] = WizardPageStatus.NOT_STARTED

        # Auto-fill from existing payloads if available
        if autofill_from_payload:
            self._autofill_from_payloads(wizard_state, session, template_id)

        # Auto-fill from session metrics for PCO template
        if template_id == "pco" and session.metrics:
            self._autofill_from_metrics(wizard_state, session)

        # Recompute completion status
        self._recompute_completion(wizard_state, template_id)

        return wizard_state

    def _autofill_from_payloads(
        self,
        wizard_state: CanrocWizardState,
        session: Session,
        template_id: str
    ) -> None:
        """Auto-fill wizard fields from existing CanROC payloads."""
        payload = None
        if template_id == "master" and session.canroc_master_payload:
            payload = session.canroc_master_payload
        elif template_id == "pco" and session.canroc_pco_payload:
            payload = session.canroc_pco_payload

        if not payload:
            return

        for field_id, value in payload.items():
            if value is not None:
                field_def = self.schema_service.get_field(template_id, field_id)
                field_type = field_def.get("type", "text") if field_def else "text"

                normalized_value, state = self.normalize_value(value, field_type, field_def)

                wizard_state.field_values[field_id] = CanrocFieldValue(
                    field_id=field_id,
                    value=normalized_value,
                    provenance=FieldProvenance.ZIP_AUTOFILL,
                    state=state,
                    updated_at=datetime.now(),
                )

    def _autofill_from_metrics(
        self,
        wizard_state: CanrocWizardState,
        session: Session
    ) -> None:
        """Auto-fill PCO wizard fields from session metrics."""
        metrics = session.metrics
        if not metrics:
            return

        # Map session metrics to PCO field IDs
        metrics_map = {
            "cr_cmprt1": metrics.cr_cmprt1,
            "cr_cmprt2": metrics.cr_cmprt2,
            "cr_cmprt3": metrics.cr_cmprt3,
            "cr_cmprt4": metrics.cr_cmprt4,
            "cr_cmprt5": metrics.cr_cmprt5,
            "cr_cmprt6": metrics.cr_cmprt6,
            "cr_cmprt7": metrics.cr_cmprt7,
            "cr_cmprt8": metrics.cr_cmprt8,
            "cr_cmprt9": metrics.cr_cmprt9,
            "cr_cmprt10": metrics.cr_cmprt10,
            "cr_cprff1": metrics.cr_cprff1,
            "cr_cprff2": metrics.cr_cprff2,
            "cr_cprff3": metrics.cr_cprff3,
            "cr_cprff4": metrics.cr_cprff4,
            "cr_cprff5": metrics.cr_cprff5,
            "cr_cprff6": metrics.cr_cprff6,
            "cr_cprff7": metrics.cr_cprff7,
            "cr_cprff8": metrics.cr_cprff8,
            "cr_cprff9": metrics.cr_cprff9,
            "cr_cprff10": metrics.cr_cprff10,
            "cr_cdpth1": metrics.cr_cdpth1,
            "cr_cdpth2": metrics.cr_cdpth2,
            "cr_cdpth3": metrics.cr_cdpth3,
            "cr_cdpth4": metrics.cr_cdpth4,
            "cr_cdpth5": metrics.cr_cdpth5,
            "cr_cdpth6": metrics.cr_cdpth6,
            "cr_cdpth7": metrics.cr_cdpth7,
            "cr_cdpth8": metrics.cr_cdpth8,
            "cr_cdpth9": metrics.cr_cdpth9,
            "cr_cdpth10": metrics.cr_cdpth10,
            "cr_etco21": metrics.cr_etco21,
            "cr_etco22": metrics.cr_etco22,
            "cr_etco23": metrics.cr_etco23,
            "cr_etco24": metrics.cr_etco24,
            "cr_etco25": metrics.cr_etco25,
            "cr_etco26": metrics.cr_etco26,
            "cr_etco27": metrics.cr_etco27,
            "cr_etco28": metrics.cr_etco28,
            "cr_etco29": metrics.cr_etco29,
            "cr_etco210": metrics.cr_etco210,
            "cr_secun1": metrics.cr_secun1,
            "cr_secun2": metrics.cr_secun2,
            "cr_secun3": metrics.cr_secun3,
            "cr_secun4": metrics.cr_secun4,
            "cr_secun5": metrics.cr_secun5,
            "cr_secun6": metrics.cr_secun6,
            "cr_secun7": metrics.cr_secun7,
            "cr_secun8": metrics.cr_secun8,
            "cr_secun9": metrics.cr_secun9,
            "cr_secun10": metrics.cr_secun10,
            # Aggregate metrics
            "cr_duration": metrics.duration,
            "cr_comprtag": metrics.compression_rate,
            "cr_cmpfrag": metrics.compression_fraction,
        }

        for field_id, value in metrics_map.items():
            if value is not None and field_id not in wizard_state.field_values:
                field_def = self.schema_service.get_field("pco", field_id)
                field_type = field_def.get("type", "float") if field_def else "float"

                normalized_value, state = self.normalize_value(value, field_type, field_def)

                wizard_state.field_values[field_id] = CanrocFieldValue(
                    field_id=field_id,
                    value=normalized_value,
                    provenance=FieldProvenance.ZIP_AUTOFILL,
                    state=state,
                    updated_at=datetime.now(),
                )

    def upsert_field(
        self,
        wizard_state: CanrocWizardState,
        field_id: str,
        value: Optional[str],
        provenance: FieldProvenance = FieldProvenance.WIZARD_MANUAL,
        cno_reason: Optional[str] = None
    ) -> CanrocFieldValue:
        """
        Insert or update a field value.

        Args:
            wizard_state: The wizard state to update
            field_id: The cr_* field code
            value: The new value
            provenance: Source of the value
            cno_reason: Optional reason if marking as CNO

        Returns:
            The updated CanrocFieldValue
        """
        template_id = wizard_state.template_id
        field_def = self.schema_service.get_field(template_id, field_id)
        field_type = field_def.get("type", "text") if field_def else "text"

        # Handle CNO marking
        if provenance == FieldProvenance.CANNOT_OBTAIN:
            cno_default = self.schema_service.get_cno_default(template_id, field_id)
            normalized_value = cno_default if cno_default else "."
            state = FieldValueState.CNO
        else:
            normalized_value, state = self.normalize_value(value, field_type, field_def)

        field_value = CanrocFieldValue(
            field_id=field_id,
            value=normalized_value,
            provenance=provenance,
            state=state,
            cno_reason=cno_reason,
            updated_at=datetime.now(),
        )

        wizard_state.field_values[field_id] = field_value
        wizard_state.last_saved_at = datetime.now()

        # Update page status
        if field_def:
            page_id = field_def.get("page_id")
            if page_id:
                self._update_page_status(wizard_state, template_id, page_id)

        return field_value

    def mark_field_cno(
        self,
        wizard_state: CanrocWizardState,
        field_id: str,
        reason: Optional[str] = None
    ) -> Optional[CanrocFieldValue]:
        """Mark a field as Cannot Obtain."""
        template_id = wizard_state.template_id

        # Check if CNO is allowed
        if not self.schema_service.is_cno_allowed(template_id, field_id):
            logger.warning(f"CNO not allowed for field {field_id}")
            return None

        return self.upsert_field(
            wizard_state,
            field_id,
            None,
            provenance=FieldProvenance.CANNOT_OBTAIN,
            cno_reason=reason
        )

    def clear_field_cno(
        self,
        wizard_state: CanrocWizardState,
        field_id: str
    ) -> CanrocFieldValue:
        """Clear CNO status from a field."""
        # Set to empty state
        return self.upsert_field(
            wizard_state,
            field_id,
            None,
            provenance=FieldProvenance.WIZARD_MANUAL
        )

    def _update_page_status(
        self,
        wizard_state: CanrocWizardState,
        template_id: str,
        page_id: int
    ) -> None:
        """Update the status of a page based on its fields."""
        page = self.schema_service.get_page(template_id, page_id)
        if not page:
            return

        fields = page.get("fields", [])
        if not fields:
            wizard_state.page_statuses[page_id] = WizardPageStatus.COMPLETE
            return

        # Get current field values as dict for dependency evaluation
        current_values = {
            fid: fv.value for fid, fv in wizard_state.field_values.items()
        }

        filled_count = 0
        required_count = 0
        required_filled_count = 0

        for field in fields:
            field_id = field.get("field_id")

            # Evaluate dependencies
            should_show, is_required = self.schema_service.evaluate_dependencies(
                template_id, field_id, current_values
            )

            if not should_show:
                continue  # Skip hidden fields

            field_value = wizard_state.field_values.get(field_id)
            is_filled = field_value and field_value.state in [
                FieldValueState.FILLED,
                FieldValueState.CNO,
            ]

            if is_filled:
                filled_count += 1

            if is_required:
                required_count += 1
                if is_filled:
                    required_filled_count += 1

        # Determine page status
        if required_count > 0 and required_filled_count == required_count:
            if filled_count == len(fields):
                wizard_state.page_statuses[page_id] = WizardPageStatus.COMPLETE
            else:
                wizard_state.page_statuses[page_id] = WizardPageStatus.PARTIAL
        elif filled_count > 0:
            wizard_state.page_statuses[page_id] = WizardPageStatus.PARTIAL
        else:
            wizard_state.page_statuses[page_id] = WizardPageStatus.NOT_STARTED

    def _recompute_completion(
        self,
        wizard_state: CanrocWizardState,
        template_id: str
    ) -> None:
        """Recompute overall completion status and percentage."""
        schema = self.schema_service.load_schema(template_id)
        required_fields = self.schema_service.get_required_fields(template_id)

        # Get current field values as dict
        current_values = {
            fid: fv.value for fid, fv in wizard_state.field_values.items()
        }

        # Calculate completion
        total_fields = len(self.schema_service.get_all_field_ids(template_id))
        filled_fields = 0
        missing_required = []

        for fid, fv in wizard_state.field_values.items():
            if fv.state in [FieldValueState.FILLED, FieldValueState.CNO]:
                filled_fields += 1

        # Check required fields
        for field_id in required_fields:
            field_value = wizard_state.field_values.get(field_id)
            is_filled = field_value and field_value.state in [
                FieldValueState.FILLED,
                FieldValueState.CNO,
            ]
            if not is_filled:
                missing_required.append(field_id)

        # Update wizard state
        wizard_state.completion_percent = (filled_fields / total_fields * 100) if total_fields > 0 else 0
        wizard_state.missing_required = missing_required

        # Update page statuses
        for page in schema.get("pages", []):
            self._update_page_status(wizard_state, template_id, page["page_id"])

        # Determine overall status
        if not missing_required and wizard_state.completion_percent >= schema.get("completion_rules", {}).get("minimum_completion_percent", 0) * 100:
            wizard_state.status = WizardCompletionStatus.COMPLETE
        elif filled_fields > 0:
            wizard_state.status = WizardCompletionStatus.IN_PROGRESS
        else:
            wizard_state.status = WizardCompletionStatus.NOT_STARTED

    def save_page(
        self,
        wizard_state: CanrocWizardState,
        page_id: int,
        field_values: Dict[str, Optional[str]]
    ) -> List[str]:
        """
        Save all fields for a wizard page.

        Args:
            wizard_state: The wizard state to update
            page_id: The page being saved
            field_values: Dict of field_id -> value

        Returns:
            List of validation error messages (empty if valid)
        """
        template_id = wizard_state.template_id
        errors = []

        # Get current values for dependency evaluation
        current_values = {
            fid: fv.value for fid, fv in wizard_state.field_values.items()
        }
        current_values.update(field_values)  # Include new values

        page = self.schema_service.get_page(template_id, page_id)
        if not page:
            errors.append(f"Page {page_id} not found")
            return errors

        # Validate and save each field
        for field in page.get("fields", []):
            field_id = field.get("field_id")
            value = field_values.get(field_id)

            # Evaluate dependencies
            should_show, is_required = self.schema_service.evaluate_dependencies(
                template_id, field_id, current_values
            )

            if not should_show:
                continue

            # Check if required and missing
            if is_required and (value is None or str(value).strip() == "" or str(value).strip() == "."):
                # Check if it's marked as CNO
                existing = wizard_state.field_values.get(field_id)
                if not (existing and existing.state == FieldValueState.CNO):
                    errors.append(f"Field '{field.get('label', field_id)}' is required")
                    continue

            # Validate choice fields - strict enforcement
            if value is not None and str(value).strip() not in ("", "."):
                field_type = field.get("type")
                if field_type == "choice":
                    choices = field.get("choices", [])
                    allowed_values = [c.get("value") for c in choices]
                    allowed_values.append(".")  # Missing marker always allowed
                    if str(value) not in allowed_values:
                        errors.append(f"Invalid value '{value}' for field '{field.get('label', field_id)}'. Allowed: {', '.join(allowed_values)}")
                        continue

            # Upsert the field
            if value is not None:
                self.upsert_field(wizard_state, field_id, value)

        # Update wizard state
        wizard_state.current_page = page_id
        self._recompute_completion(wizard_state, template_id)

        return errors

    def complete_wizard(
        self,
        wizard_state: CanrocWizardState
    ) -> Tuple[bool, List[str]]:
        """
        Mark wizard as complete and normalize all fields.

        Args:
            wizard_state: The wizard state to complete

        Returns:
            Tuple of (success, error_messages)
        """
        template_id = wizard_state.template_id
        errors = []

        # Check required fields
        required_fields = self.schema_service.get_required_fields(template_id)
        for field_id in required_fields:
            field_value = wizard_state.field_values.get(field_id)
            is_filled = field_value and field_value.state in [
                FieldValueState.FILLED,
                FieldValueState.CNO,
            ]
            if not is_filled:
                field_def = self.schema_service.get_field(template_id, field_id)
                label = field_def.get("label", field_id) if field_def else field_id
                errors.append(f"Required field '{label}' [{field_id}] is not filled")

        if errors:
            return False, errors

        # Normalize all empty fields to "."
        missing_marker = self.schema_service.get_missing_marker(template_id)
        all_field_ids = self.schema_service.get_all_field_ids(template_id)

        for field_id in all_field_ids:
            if field_id not in wizard_state.field_values:
                wizard_state.field_values[field_id] = CanrocFieldValue(
                    field_id=field_id,
                    value=missing_marker,
                    provenance=FieldProvenance.MISSING_MARKER,
                    state=FieldValueState.NORMALIZED,
                    updated_at=datetime.now(),
                )

        # Mark as complete
        wizard_state.status = WizardCompletionStatus.COMPLETE
        wizard_state.completed_at = datetime.now()
        wizard_state.last_saved_at = datetime.now()
        wizard_state.completion_percent = 100.0

        return True, []

    def get_wizard_summary(
        self,
        wizard_state: CanrocWizardState
    ) -> Dict[str, Any]:
        """Get a summary of wizard state for display."""
        template_id = wizard_state.template_id
        schema = self.schema_service.load_schema(template_id)

        pages_summary = []
        for page in schema.get("pages", []):
            page_id = page["page_id"]
            page_status = wizard_state.page_statuses.get(page_id, WizardPageStatus.NOT_STARTED)

            # Count fields
            fields = page.get("fields", [])
            filled = 0
            for field in fields:
                fv = wizard_state.field_values.get(field["field_id"])
                if fv and fv.state in [FieldValueState.FILLED, FieldValueState.CNO]:
                    filled += 1

            pages_summary.append({
                "page_id": page_id,
                "page_name": page["page_name"],
                "page_label": page["page_label"],
                "status": page_status.value,
                "fields_filled": filled,
                "fields_total": len(fields),
                "auto_filled": page.get("auto_filled", False),
            })

        return {
            "session_id": wizard_state.session_id,
            "template_id": template_id,
            "template_name": schema.get("template_name"),
            "status": wizard_state.status.value,
            "current_page": wizard_state.current_page,
            "total_pages": wizard_state.total_pages,
            "completion_percent": round(wizard_state.completion_percent, 1),
            "missing_required": wizard_state.missing_required,
            "can_complete": len(wizard_state.missing_required) == 0,
            "pages": pages_summary,
            "started_at": wizard_state.started_at.isoformat() if wizard_state.started_at else None,
            "last_saved_at": wizard_state.last_saved_at.isoformat() if wizard_state.last_saved_at else None,
            "completed_at": wizard_state.completed_at.isoformat() if wizard_state.completed_at else None,
        }

    def export_to_payload(
        self,
        wizard_state: CanrocWizardState
    ) -> Dict[str, Any]:
        """
        Export wizard field values to a payload dict for CanROC export.

        Returns:
            Dict of field_id -> value (suitable for canroc_master_payload or canroc_pco_payload)
        """
        payload = {}
        for field_id, field_value in wizard_state.field_values.items():
            # Only include fields with actual values (not normalized blanks for export)
            if field_value.state in [FieldValueState.FILLED, FieldValueState.CNO]:
                payload[field_id] = field_value.value
            elif field_value.state == FieldValueState.NORMALIZED:
                payload[field_id] = field_value.value  # Include "." for normalized

        return payload


# Singleton instance
_wizard_service: Optional[WizardService] = None


def get_wizard_service() -> WizardService:
    """Get the singleton WizardService instance."""
    global _wizard_service
    if _wizard_service is None:
        _wizard_service = WizardService()
    return _wizard_service
