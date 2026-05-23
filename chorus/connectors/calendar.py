"""Local Radicale/CalDAV calendar connector used behind the Tool Gateway."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote
from uuid import uuid4
from xml.etree import ElementTree

import httpx
from pydantic import BaseModel, ConfigDict, Field

from chorus.connectors.local import ConnectorError, ConnectorResult, ConnectorTransientError
from chorus.contracts.generated.connector.calendar_availability_lookup_args import (
    CalendarAvailabilityLookupArgs,
)
from chorus.contracts.generated.connector.calendar_hold_cancellation_args import (
    CalendarHoldCancellationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_creation_args import (
    CalendarHoldCreationArgs,
)
from chorus.contracts.generated.connector.calendar_hold_proposal_args import (
    CalendarHoldProposalArgs,
)

_DAV_NAMESPACE = "DAV:"
_CALDAV_NAMESPACE = "urn:ietf:params:xml:ns:caldav"
_ICAL_DT_FORMAT = "%Y%m%dT%H%M%SZ"
_DEFAULT_TIMEOUT_SECONDS = 5.0


class CalendarConnectorSettings(BaseModel):
    """Configuration for the local CalDAV sandbox connector."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default="http://localhost:5232", min_length=1)
    timeout_seconds: float = Field(default=_DEFAULT_TIMEOUT_SECONDS, gt=0, le=30)


@dataclass(frozen=True)
class _BusyRange:
    event_uid_ref: str | None
    starts_at: datetime
    ends_at: datetime


class RadicaleCalendarConnector:
    """Protocol-backed local calendar connector for the Radicale sandbox."""

    def __init__(self, settings: CalendarConnectorSettings | None = None) -> None:
        self._settings = settings or CalendarConnectorSettings(
            base_url=os.environ.get("CHORUS_CALDAV_BASE_URL", "http://localhost:5232"),
            timeout_seconds=float(
                os.environ.get("CHORUS_CALDAV_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS))
            ),
        )

    def lookup_availability(self, arguments: CalendarAvailabilityLookupArgs) -> ConnectorResult:
        self._ensure_calendar(arguments.calendar_ref)
        busy_ranges = self._calendar_busy_ranges(
            calendar_ref=arguments.calendar_ref,
            window_start=arguments.window_start,
            window_end=arguments.window_end,
            exclude_event_uid_refs={
                _root_value(ref) for ref in arguments.exclude_event_uid_refs or []
            },
        )
        slots = _available_slots(
            arguments=arguments,
            busy_ranges=busy_ranges,
        )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "radicale.caldav.local",
                "calendar_ref": arguments.calendar_ref,
                "availability_status": "slots_available" if slots else "no_slots_available",
                "window_ref": _safe_ref(
                    "window",
                    arguments.calendar_ref,
                    arguments.window_start.isoformat(),
                    arguments.window_end.isoformat(),
                    arguments.availability_policy_ref,
                ),
                "slot_count": len(slots),
                "slots": slots,
            },
        )

    def propose_hold(self, arguments: CalendarHoldProposalArgs) -> ConnectorResult:
        self._ensure_calendar(arguments.calendar_ref)
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "radicale.caldav.local",
                "calendar_ref": arguments.calendar_ref,
                "hold_ref": arguments.hold_ref,
                "slot_ref": arguments.slot_ref,
                "proposal_status": "proposed",
                "event_created": False,
                "meeting_type": arguments.meeting_type.value,
                "summary_category": arguments.summary_category.value,
                "participant_ref_count": len(arguments.participant_refs),
            },
        )

    def create_hold(self, arguments: CalendarHoldCreationArgs) -> ConnectorResult:
        if arguments.ends_at <= arguments.starts_at:
            raise ConnectorError("calendar_hold_invalid_time_window")

        self._ensure_calendar(arguments.calendar_ref)
        path = self._event_path(arguments.calendar_ref, arguments.event_uid_ref)
        existing = self._request("GET", path, expected_statuses={200, 404})
        if existing.status_code == 200:
            if not _event_context_matches(existing.text, arguments):
                raise ConnectorError("caldav_duplicate_uid_context_mismatch")
            return ConnectorResult(
                connector_invocation_id=uuid4(),
                output={
                    "connector": "radicale.caldav.local",
                    "calendar_ref": arguments.calendar_ref,
                    "hold_ref": arguments.hold_ref,
                    "slot_ref": arguments.slot_ref,
                    "event_uid_ref": arguments.event_uid_ref,
                    "event_status": "already_exists",
                    "idempotency_category": "duplicate_event_uid_ref_matching_context",
                },
            )

        response = self._request(
            "PUT",
            path,
            content=_event_body(arguments),
            headers={"Content-Type": "text/calendar; charset=utf-8"},
            expected_statuses={200, 201, 204},
        )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "radicale.caldav.local",
                "calendar_ref": arguments.calendar_ref,
                "hold_ref": arguments.hold_ref,
                "slot_ref": arguments.slot_ref,
                "event_uid_ref": arguments.event_uid_ref,
                "event_status": "created" if response.status_code == 201 else "updated",
                "busy_status": arguments.busy_status.value,
                "visibility": arguments.visibility.value
                if arguments.visibility is not None
                else None,
            },
        )

    def cancel_hold(self, arguments: CalendarHoldCancellationArgs) -> ConnectorResult:
        self._ensure_calendar(arguments.calendar_ref)
        response = self._request(
            "DELETE",
            self._event_path(arguments.calendar_ref, arguments.event_uid_ref),
            expected_statuses={200, 204, 404},
        )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "radicale.caldav.local",
                "calendar_ref": arguments.calendar_ref,
                "hold_ref": arguments.hold_ref,
                "event_uid_ref": arguments.event_uid_ref,
                "cancellation_status": "cancelled" if response.status_code != 404 else "missing",
                "cancellation_reason_category": arguments.cancellation_reason_category.value,
                "compensation_ref": arguments.compensation_ref,
            },
        )

    def _ensure_calendar(self, calendar_ref: str) -> None:
        path = self._calendar_path(calendar_ref)
        response = self._request(
            "PROPFIND", path, headers={"Depth": "0"}, expected_statuses={207, 404}
        )
        if response.status_code == 207:
            return

        self._request(
            "MKCOL",
            path,
            content=_calendar_collection_body(calendar_ref),
            headers={"Content-Type": "application/xml; charset=utf-8"},
            expected_statuses={201, 207, 405},
        )

    def _calendar_busy_ranges(
        self,
        *,
        calendar_ref: str,
        window_start: datetime,
        window_end: datetime,
        exclude_event_uid_refs: set[str],
    ) -> list[_BusyRange]:
        response = self._request(
            "REPORT",
            self._calendar_path(calendar_ref),
            content=_calendar_query_body(window_start, window_end),
            headers={"Content-Type": "application/xml; charset=utf-8", "Depth": "1"},
            expected_statuses={207},
        )
        return [
            busy
            for body in _calendar_data_values(response.text)
            for busy in _busy_ranges_from_ics(body)
            if busy.event_uid_ref not in exclude_event_uid_refs
        ]

    def _request(
        self,
        method: str,
        path: str,
        *,
        content: str | None = None,
        headers: dict[str, str] | None = None,
        expected_statuses: set[int],
    ) -> httpx.Response:
        url = f"{self._settings.base_url.rstrip('/')}{path}"
        try:
            response = httpx.request(
                method,
                url,
                content=content,
                headers=headers,
                timeout=self._settings.timeout_seconds,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ConnectorTransientError("caldav_transient_unavailable") from exc
        except httpx.HTTPError as exc:
            raise ConnectorError("caldav_protocol_error") from exc

        if response.status_code in expected_statuses:
            return response
        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise ConnectorTransientError("caldav_transient_unavailable")
        raise ConnectorError("caldav_rejected")

    @staticmethod
    def _calendar_path(calendar_ref: str) -> str:
        return f"/{quote(calendar_ref, safe='')}/"

    @staticmethod
    def _event_path(calendar_ref: str, event_uid_ref: str) -> str:
        return f"/{quote(calendar_ref, safe='')}/{quote(event_uid_ref, safe='')}.ics"


def _calendar_collection_body(calendar_ref: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="{_DAV_NAMESPACE}" xmlns:C="{_CALDAV_NAMESPACE}">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <C:calendar />
      </resourcetype>
      <C:supported-calendar-component-set>
        <C:comp name="VEVENT" />
      </C:supported-calendar-component-set>
      <displayname>{calendar_ref}</displayname>
      <C:calendar-description>Chorus local CalDAV sandbox calendar</C:calendar-description>
    </prop>
  </set>
</create>"""


def _calendar_query_body(window_start: datetime, window_end: datetime) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<C:calendar-query xmlns:D="{_DAV_NAMESPACE}" xmlns:C="{_CALDAV_NAMESPACE}">
  <D:prop>
    <D:getetag />
    <C:calendar-data />
  </D:prop>
  <C:filter>
    <C:comp-filter name="VCALENDAR">
      <C:comp-filter name="VEVENT">
        <C:time-range start="{_ical_datetime(window_start)}" end="{_ical_datetime(window_end)}" />
      </C:comp-filter>
    </C:comp-filter>
  </C:filter>
</C:calendar-query>"""


def _event_body(arguments: CalendarHoldCreationArgs) -> str:
    participant_refs = ",".join(_root_value(ref) for ref in arguments.participant_refs)
    visibility = arguments.visibility.value if arguments.visibility is not None else "private"
    now = _ical_datetime(datetime.now(UTC))
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Chorus//Local CalDAV Sandbox//EN",
            "BEGIN:VEVENT",
            f"UID:{arguments.event_uid_ref}@chorus.local",
            f"DTSTAMP:{now}",
            f"DTSTART:{_ical_datetime(arguments.starts_at)}",
            f"DTEND:{_ical_datetime(arguments.ends_at)}",
            f"SUMMARY:Chorus {arguments.summary_category.value}",
            "TRANSP:OPAQUE",
            f"STATUS:{'TENTATIVE' if arguments.busy_status.value == 'tentative' else 'CONFIRMED'}",
            f"CLASS:{'PRIVATE' if visibility == 'private' else 'PUBLIC'}",
            f"X-CHORUS-CALENDAR-REF:{arguments.calendar_ref}",
            f"X-CHORUS-HOLD-REF:{arguments.hold_ref}",
            f"X-CHORUS-SLOT-REF:{arguments.slot_ref}",
            f"X-CHORUS-EVENT-UID-REF:{arguments.event_uid_ref}",
            f"X-CHORUS-MEETING-TYPE:{arguments.meeting_type.value}",
            f"X-CHORUS-SUMMARY-CATEGORY:{arguments.summary_category.value}",
            f"X-CHORUS-PARTICIPANT-REFS:{participant_refs}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def _event_context_matches(ics_body: str, arguments: CalendarHoldCreationArgs) -> bool:
    expected = {
        "UID": f"{arguments.event_uid_ref}@chorus.local",
        "X-CHORUS-CALENDAR-REF": arguments.calendar_ref,
        "X-CHORUS-HOLD-REF": arguments.hold_ref,
        "X-CHORUS-SLOT-REF": arguments.slot_ref,
        "X-CHORUS-EVENT-UID-REF": arguments.event_uid_ref,
        "X-CHORUS-MEETING-TYPE": arguments.meeting_type.value,
        "X-CHORUS-SUMMARY-CATEGORY": arguments.summary_category.value,
        "X-CHORUS-PARTICIPANT-REFS": ",".join(
            _root_value(ref) for ref in arguments.participant_refs
        ),
    }
    current: dict[str, str] | None = None
    for line in _unfold_ics_lines(ics_body):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            return current is not None and all(
                current.get(key) == value for key, value in expected.items()
            )
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.split(";", 1)[0].upper()] = value
    return False


def _calendar_data_values(multistatus_xml: str) -> list[str]:
    try:
        root = ElementTree.fromstring(multistatus_xml)
    except ElementTree.ParseError as exc:
        raise ConnectorError("caldav_invalid_report_response") from exc

    values: list[str] = []
    for element in root.iter(f"{{{_CALDAV_NAMESPACE}}}calendar-data"):
        if element.text:
            values.append(element.text)
    return values


def _busy_ranges_from_ics(ics_body: str) -> list[_BusyRange]:
    ranges: list[_BusyRange] = []
    current: dict[str, str] | None = None
    for line in _unfold_ics_lines(ics_body):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                busy = _busy_range_from_props(current)
                if busy is not None:
                    ranges.append(busy)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        current[key.split(";", 1)[0].upper()] = value
    return ranges


def _unfold_ics_lines(ics_body: str) -> list[str]:
    lines: list[str] = []
    for raw_line in ics_body.replace("\r\n", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        elif raw_line:
            lines.append(raw_line)
    return lines


def _busy_range_from_props(props: dict[str, str]) -> _BusyRange | None:
    starts_at = _parse_ical_datetime(props.get("DTSTART"))
    ends_at = _parse_ical_datetime(props.get("DTEND"))
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return None
    return _BusyRange(
        event_uid_ref=props.get("X-CHORUS-EVENT-UID-REF"),
        starts_at=starts_at,
        ends_at=ends_at,
    )


def _parse_ical_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        return datetime.strptime(value, _ICAL_DT_FORMAT).replace(tzinfo=UTC)
    return None


def _available_slots(
    *,
    arguments: CalendarAvailabilityLookupArgs,
    busy_ranges: list[_BusyRange],
) -> list[dict[str, Any]]:
    duration = timedelta(minutes=arguments.duration_minutes)
    count = arguments.required_slot_count or 3
    window_start = _utc(arguments.window_start)
    window_end = _utc(arguments.window_end)
    slots: list[dict[str, Any]] = []
    cursor = window_start
    while cursor + duration <= window_end and len(slots) < count:
        candidate_end = cursor + duration
        if not any(_overlaps(cursor, candidate_end, busy) for busy in busy_ranges):
            slots.append(
                {
                    "slot_ref": _safe_ref(
                        "slot",
                        arguments.calendar_ref,
                        cursor.isoformat(),
                        candidate_end.isoformat(),
                    ),
                    "starts_at": cursor.isoformat(),
                    "ends_at": candidate_end.isoformat(),
                    "status": "available",
                }
            )
        cursor = candidate_end
    return slots


def _overlaps(starts_at: datetime, ends_at: datetime, busy: _BusyRange) -> bool:
    return starts_at < _utc(busy.ends_at) and ends_at > _utc(busy.starts_at)


def _ical_datetime(value: datetime) -> str:
    return _utc(value).strftime(_ICAL_DT_FORMAT)


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _safe_ref(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _root_value(value: Any) -> str:
    root = getattr(value, "root", None)
    return root if isinstance(root, str) else str(value)
