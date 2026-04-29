"""Redpanda relay and projection-worker adapters for workflow events."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import psycopg
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

from chorus.contracts.generated.events.workflow_event import WorkflowEvent
from chorus.persistence.migrate import database_url_from_env
from chorus.persistence.outbox import OutboxStore, OutboxWorkflowEvent
from chorus.persistence.projection import ProjectionStore

DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_SCHEMA_REGISTRY_URL = "http://localhost:8081"
DEFAULT_WORKFLOW_TOPIC = "chorus.workflow.events.v1"
DEFAULT_CONSUMER_GROUP = "chorus.projection-worker.v1"
ROOT = Path(__file__).resolve().parents[2]


class WorkflowEventPublishError(RuntimeError):
    """Raised when Redpanda rejects a workflow event publish."""


def bootstrap_servers_from_env() -> str:
    return os.environ.get("CHORUS_REDPANDA_BOOTSTRAP_SERVERS", DEFAULT_BOOTSTRAP_SERVERS)


def schema_registry_url_from_env() -> str:
    explicit_url = os.environ.get("CHORUS_SCHEMA_REGISTRY_URL")
    if explicit_url:
        return explicit_url
    port = os.environ.get("REDPANDA_SCHEMA_REGISTRY_PORT")
    if port:
        return f"http://localhost:{port}"
    return DEFAULT_SCHEMA_REGISTRY_URL


def _event_schema_subjects() -> dict[str, str]:
    subjects: dict[str, str] = {}
    for path in sorted((ROOT / "contracts" / "events").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        subject = schema.get("x-subject")
        if isinstance(subject, str) and subject:
            subjects[str(path)] = subject
    return subjects


def register_event_schemas_once(*, schema_registry_url: str | None = None) -> int:
    """Register event JSON Schemas with Redpanda Schema Registry."""

    base_url = (schema_registry_url or schema_registry_url_from_env()).rstrip("/")
    registered = 0
    for path_text, subject in _event_schema_subjects().items():
        path = Path(path_text)
        schema_text = path.read_text(encoding="utf-8")
        body = json.dumps(
            {
                "schemaType": "JSON",
                "schema": schema_text,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/subjects/{subject}/versions",
            data=body,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status not in {200, 201}:
                    raise WorkflowEventPublishError(
                        f"Schema Registry returned {response.status} for {subject}"
                    )
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WorkflowEventPublishError(
                f"Schema Registry rejected {subject}: HTTP {exc.code} {detail}"
            ) from exc
        registered += 1
    return registered


def _event_bytes(event: WorkflowEvent) -> bytes:
    return json.dumps(
        event.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _headers(outbox_event: OutboxWorkflowEvent) -> list[tuple[str, str | bytes | None]]:
    headers = {
        "schema_name": "workflow_event",
        "schema_version": outbox_event.event.schema_version,
        "event_id": str(outbox_event.event.event_id),
        "tenant_id": outbox_event.event.tenant_id,
        "correlation_id": outbox_event.event.correlation_id,
        "workflow_id": outbox_event.event.workflow_id,
        **{key: str(value) for key, value in outbox_event.headers.items()},
    }
    return [(key, value.encode("utf-8")) for key, value in headers.items()]


class RedpandaWorkflowEventPublisher:
    """Publishes canonical workflow_event payloads to Redpanda."""

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        client_id: str = "chorus-outbox-relay",
        producer_factory: Callable[[dict[str, Any]], Producer] = Producer,
    ) -> None:
        self._producer = producer_factory(
            {
                "bootstrap.servers": bootstrap_servers or bootstrap_servers_from_env(),
                "client.id": client_id,
                "enable.idempotence": True,
                "acks": "all",
            }
        )

    def publish(self, outbox_event: OutboxWorkflowEvent, *, timeout: float = 10.0) -> None:
        errors: list[str] = []

        def delivery_report(err: Any, _msg: Any) -> None:
            if err is not None:
                errors.append(str(err))

        self._producer.produce(
            outbox_event.topic,
            key=outbox_event.message_key.encode("utf-8"),
            value=_event_bytes(outbox_event.event),
            headers=_headers(outbox_event),
            on_delivery=delivery_report,
        )
        remaining = self._producer.flush(timeout)

        if remaining:
            raise WorkflowEventPublishError("Timed out waiting for Redpanda delivery")
        if errors:
            raise WorkflowEventPublishError(errors[0])


def relay_outbox_once(
    *,
    database_url: str | None = None,
    bootstrap_servers: str | None = None,
    limit: int = 100,
) -> int:
    """Publish one batch of due outbox rows and update lifecycle state."""

    published = 0
    publisher = RedpandaWorkflowEventPublisher(bootstrap_servers=bootstrap_servers)
    with psycopg.connect(database_url or database_url_from_env()) as conn:
        outbox = OutboxStore(conn)
        outbox.release_stale_publishing()
        claimed = outbox.claim_pending(limit=limit)

        for event in claimed:
            try:
                publisher.publish(event)
            except Exception as exc:
                outbox.mark_failed(
                    event.outbox_id,
                    error=str(exc),
                    retry_delay=_retry_delay(event.attempts),
                )
                continue

            outbox.mark_sent(event.outbox_id)
            published += 1

    return published


def _retry_delay(attempts: int) -> timedelta:
    capped_attempts = min(max(attempts, 1), 6)
    return timedelta(seconds=2 ** (capped_attempts - 1))


@dataclass(frozen=True)
class ConsumedWorkflowEvent:
    event: WorkflowEvent
    topic: str
    partition: int
    offset: int


class RedpandaWorkflowEventConsumer:
    """Consumes schema-governed workflow events from Redpanda."""

    def __init__(
        self,
        *,
        bootstrap_servers: str | None = None,
        group_id: str = DEFAULT_CONSUMER_GROUP,
        topics: Sequence[str] = (DEFAULT_WORKFLOW_TOPIC,),
        consumer_factory: Callable[[dict[str, Any]], Consumer] = Consumer,
    ) -> None:
        self._consumer = consumer_factory(
            {
                "bootstrap.servers": bootstrap_servers or bootstrap_servers_from_env(),
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,
            }
        )
        self._consumer.subscribe(list(topics))

    def poll(self, *, timeout: float = 1.0) -> ConsumedWorkflowEvent | None:
        message = self._consumer.poll(timeout)
        if message is None:
            return None

        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                return None
            raise KafkaException(error)

        payload = message.value()
        if not isinstance(payload, bytes):
            raise TypeError("Workflow event message value must be bytes")

        event = WorkflowEvent.model_validate(json.loads(payload.decode("utf-8")))
        return ConsumedWorkflowEvent(
            event=event,
            topic=cast(str, message.topic()),
            partition=cast(int, message.partition()),
            offset=cast(int, message.offset()),
        )

    def commit(self) -> None:
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        self._consumer.close()


def project_workflow_events_once(
    *,
    database_url: str | None = None,
    bootstrap_servers: str | None = None,
    group_id: str = DEFAULT_CONSUMER_GROUP,
    max_messages: int = 100,
    poll_timeout: float = 1.0,
) -> int:
    """Consume a bounded batch of workflow events and apply read-model projections."""

    applied = 0
    consumer = RedpandaWorkflowEventConsumer(
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
    )
    try:
        with psycopg.connect(database_url or database_url_from_env()) as conn:
            store = ProjectionStore(conn)
            while applied < max_messages:
                consumed = consumer.poll(timeout=poll_timeout)
                if consumed is None:
                    break
                with conn.transaction():
                    store.apply_workflow_event(consumed.event)
                consumer.commit()
                applied += 1
    finally:
        consumer.close()

    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relay or project Chorus workflow events.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schemas = subparsers.add_parser(
        "register-schemas",
        help="Register event JSON Schemas with Redpanda Schema Registry.",
    )
    schemas.add_argument("--schema-registry-url", default=None)

    relay = subparsers.add_parser("relay-once", help="Publish one due outbox batch to Redpanda.")
    relay.add_argument("--database-url", default=None)
    relay.add_argument("--bootstrap-servers", default=None)
    relay.add_argument("--limit", type=int, default=100)

    project = subparsers.add_parser(
        "project-once",
        help="Consume one bounded Redpanda batch into Postgres projections.",
    )
    project.add_argument("--database-url", default=None)
    project.add_argument("--bootstrap-servers", default=None)
    project.add_argument("--group-id", default=DEFAULT_CONSUMER_GROUP)
    project.add_argument("--max-messages", type=int, default=100)
    project.add_argument("--poll-timeout", type=float, default=1.0)

    args = parser.parse_args(argv)
    if args.command == "register-schemas":
        count = register_event_schemas_once(schema_registry_url=args.schema_registry_url)
        print(f"Registered {count} event schema subject(s).")
        return 0

    if args.command == "relay-once":
        count = relay_outbox_once(
            database_url=args.database_url,
            bootstrap_servers=args.bootstrap_servers,
            limit=args.limit,
        )
        print(f"Published {count} workflow event(s).")
        return 0

    count = project_workflow_events_once(
        database_url=args.database_url,
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        max_messages=args.max_messages,
        poll_timeout=args.poll_timeout,
    )
    print(f"Projected {count} workflow event(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
