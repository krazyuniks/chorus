"""UC1 connector adapters.

Six sandbox adapters cover the UC1 connector inventory: quoting queue,
referral inbox, decline ledger, outbound comms, customer profile, product
catalogue.

The R3 surface is deliberately thin: each adapter validates against its
UC1 connector contract, computes a deterministic verdict reference for
audit, and returns a shape that proves the registry round-trip. The
broker-firm-side persistence (`local_quoting_queue_routes`,
`local_referral_inbox_routes`, `local_decline_ledger_routes`,
`local_customer_profiles`, `local_product_catalogue`) is wired in R4
when UC1 runs end-to-end against the local POC sandbox. Until then the
read adapters return canned target-market / vulnerability data per the
domain model fixture set.
"""

from __future__ import annotations

import os
import smtplib
from collections.abc import Sequence
from email.message import EmailMessage
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from chorus.connectors.types import (
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    ConnectorTransientError,
    ToolSpec,
)
from chorus.contracts.generated.connector.uc1.customer_profile_lookup_args import (
    CustomerProfileLookupArgs,
)
from chorus.contracts.generated.connector.uc1.decline_ledger_route_args import (
    DeclineLedgerRouteArgs,
)
from chorus.contracts.generated.connector.uc1.outbound_comms_message_args import (
    OutboundCommsMessageArgs,
)
from chorus.contracts.generated.connector.uc1.product_catalogue_lookup_args import (
    ProductCatalogueLookupArgs,
)
from chorus.contracts.generated.connector.uc1.quoting_queue_route_args import (
    QuotingQueueRouteArgs,
)
from chorus.contracts.generated.connector.uc1.referral_inbox_route_args import (
    ReferralInboxRouteArgs,
)


def _ref(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


class SandboxQuotingQueueAdapter:
    """`sandbox-crm` adapter; receives the UC1 `accept` verdict.

    Routes an enquiry into the broker firm's standard quoting queue and
    returns a queued-route reference for downstream evidence.
    """

    adapter_id = "sandbox_crm"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="crm.route_to_quoting_queue",
                argument_contract=QuotingQueueRouteArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/quoting_queue_route_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "crm.route_to_quoting_queue":
            raise ConnectorError(
                f"SandboxQuotingQueueAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, QuotingQueueRouteArgs):
            raise TypeError(
                f"SandboxQuotingQueueAdapter expected QuotingQueueRouteArgs for {tool_name!r}"
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_crm.local",
                "mode": mode,
                "enquiry_ref": arguments.enquiry_ref,
                "customer_ref": arguments.customer_ref,
                "verdict_ref": arguments.verdict_ref,
                "product_family_category": arguments.product_family_category.value,
                "routing_destination_category": "broker_firm_quoting_queue",
                "queued_route_ref": _ref("qroute", arguments.enquiry_ref, arguments.verdict_ref),
            },
        )


class SandboxReferralInboxAdapter:
    """`sandbox-referral-inbox` adapter; receives the UC1 `refer` verdict.

    Settles the R1-deferred shape: a separate sandbox adapter (not a
    tagged subscription on the quoting-queue adapter). Refer is a routing
    destination with its own audit trail and downstream consumer
    (specialist or partner channel), distinct from accepting into the
    standard quoting queue; conflating them through a subscription tag
    would hide the routing-intent boundary the policy snapshot grants
    over.
    """

    adapter_id = "sandbox_referral_inbox"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="referral_inbox.route",
                argument_contract=ReferralInboxRouteArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/referral_inbox_route_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "referral_inbox.route":
            raise ConnectorError(
                f"SandboxReferralInboxAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, ReferralInboxRouteArgs):
            raise TypeError(
                f"SandboxReferralInboxAdapter expected ReferralInboxRouteArgs for {tool_name!r}"
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_referral_inbox.local",
                "mode": mode,
                "enquiry_ref": arguments.enquiry_ref,
                "customer_ref": arguments.customer_ref,
                "verdict_ref": arguments.verdict_ref,
                "referral_destination_category": arguments.referral_destination_category.value,
                "referral_reason_category": arguments.referral_reason_category.value,
                "referral_route_ref": _ref("rroute", arguments.enquiry_ref, arguments.verdict_ref),
            },
        )


class SandboxDeclineLedgerAdapter:
    """`sandbox-decline-ledger` adapter; receives the UC1 `decline` verdict."""

    adapter_id = "sandbox_decline_ledger"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="decline_ledger.route",
                argument_contract=DeclineLedgerRouteArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/decline_ledger_route_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del context
        if tool_name != "decline_ledger.route":
            raise ConnectorError(
                f"SandboxDeclineLedgerAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, DeclineLedgerRouteArgs):
            raise TypeError(
                f"SandboxDeclineLedgerAdapter expected DeclineLedgerRouteArgs for {tool_name!r}"
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_decline_ledger.local",
                "mode": mode,
                "enquiry_ref": arguments.enquiry_ref,
                "customer_ref": arguments.customer_ref,
                "verdict_ref": arguments.verdict_ref,
                "decline_reason_category": arguments.decline_reason_category.value,
                "decline_route_ref": _ref("droute", arguments.enquiry_ref, arguments.verdict_ref),
            },
        )


class SandboxOutboundCommsAdapter:
    """`sandbox-outbound-comms` adapter; drives the gated missing-data-request send.

    Modelled as a local Mailpit-style capture for the R3 surface. The
    same tool covers both modes: propose-mode records the draft for the
    adviser approval gate, write-mode (post-approval) actually sends the
    message via the local Mailpit SMTP server.
    """

    adapter_id = "sandbox_outbound_comms"

    def __init__(
        self,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        sender: str = "broker-firm@chorus.local",
    ) -> None:
        self._smtp_host = smtp_host or os.environ.get("CHORUS_MAILPIT_SMTP_HOST", "localhost")
        self._smtp_port = smtp_port or int(os.environ.get("CHORUS_MAILPIT_SMTP_PORT", "1025"))
        self._sender = sender

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="outbound_comms.message",
                argument_contract=OutboundCommsMessageArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/outbound_comms_message_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        if tool_name != "outbound_comms.message":
            raise ConnectorError(
                f"SandboxOutboundCommsAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, OutboundCommsMessageArgs):
            raise TypeError(
                f"SandboxOutboundCommsAdapter expected OutboundCommsMessageArgs for {tool_name!r}"
            )

        connector_invocation_id = uuid4()
        if _is_outbound_comms_failure_fixture(arguments):
            raise ConnectorTransientError(
                "fixture-scoped transient Mailpit SMTP failure for missing-data request"
            )

        if mode == "propose":
            return ConnectorResult(
                connector_invocation_id=connector_invocation_id,
                output={
                    "connector": "sandbox_outbound_comms.mailpit",
                    "mode": mode,
                    "enquiry_ref": arguments.enquiry_ref,
                    "customer_ref": arguments.customer_ref,
                    "missing_data_request_ref": arguments.missing_data_request_ref,
                    "draft_status": "drafted",
                    "captured_by": "in_memory_draft",
                },
            )

        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = arguments.to_email
        message["Subject"] = arguments.subject
        message["X-Chorus-Tenant-Id"] = context.tenant_id
        message["X-Chorus-Correlation-Id"] = context.correlation_id
        message["X-Chorus-Workflow-Id"] = context.workflow_id
        message["X-Chorus-Connector-Invocation-Id"] = str(connector_invocation_id)
        message["X-Chorus-Tool-Mode"] = mode
        message["X-Chorus-Enquiry-Ref"] = arguments.enquiry_ref
        message["X-Chorus-Missing-Data-Request-Ref"] = arguments.missing_data_request_ref
        message.set_content(arguments.body_text)

        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=10) as smtp:
                smtp.send_message(message)
        except OSError as exc:
            raise ConnectorError(
                f"Mailpit SMTP send failed at {self._smtp_host}:{self._smtp_port}: {exc}"
            ) from exc

        return ConnectorResult(
            connector_invocation_id=connector_invocation_id,
            output={
                "connector": "sandbox_outbound_comms.mailpit",
                "mode": mode,
                "enquiry_ref": arguments.enquiry_ref,
                "customer_ref": arguments.customer_ref,
                "missing_data_request_ref": arguments.missing_data_request_ref,
                "send_status": "sent",
                "captured_by": "mailpit",
            },
        )


_CANNED_CUSTOMER_PROFILES: dict[str, dict[str, Any]] = {
    "cust_demo_001": {
        "display_name_category": "individual_personal_lines",
        "vulnerability_markers": [],
        "consent_state_category": "marketing_opt_in",
    },
    "cust_demo_002": {
        "display_name_category": "individual_personal_lines",
        "vulnerability_markers": ["bereavement_declared"],
        "consent_state_category": "marketing_opt_out",
    },
}


class SandboxCustomerProfileAdapter:
    """`sandbox-customer-profile` adapter; read-only customer-of-record lookup.

    Settles the R1-deferred customer-profile store boundary: the
    customer-of-record lives inside the broker firm; the connector port
    only exposes a read surface (`customer_profile.lookup`). The write
    path is owned by the firm's customer-of-record service, reachable
    only via the firm's own write surfaces, not through this adapter.
    Vulnerability markers are returned alongside the profile per the
    Consumer Duty conduct-hook test in the audit content.
    """

    adapter_id = "sandbox_customer_profile"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="customer_profile.lookup",
                argument_contract=CustomerProfileLookupArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/customer_profile_lookup_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del mode, context
        if tool_name != "customer_profile.lookup":
            raise ConnectorError(
                f"SandboxCustomerProfileAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, CustomerProfileLookupArgs):
            raise TypeError(
                "SandboxCustomerProfileAdapter expected CustomerProfileLookupArgs for "
                f"{tool_name!r}"
            )

        canned = _CANNED_CUSTOMER_PROFILES.get(arguments.customer_ref)
        if canned is None:
            return ConnectorResult(
                connector_invocation_id=uuid4(),
                output={
                    "connector": "sandbox_customer_profile.local",
                    "customer_ref": arguments.customer_ref,
                    "lookup_status": "customer_not_found",
                },
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_customer_profile.local",
                "customer_ref": arguments.customer_ref,
                "lookup_status": "customer_found",
                "display_name_category": canned["display_name_category"],
                "vulnerability_markers": list(canned["vulnerability_markers"]),
                "consent_state_category": canned["consent_state_category"],
            },
        )


_CANNED_PRODUCT_TARGET_MARKETS: dict[str, dict[str, Any]] = {
    "motor_private_car": {
        "target_market_summary_category": "uk_resident_private_motor_standard",
        "min_age_category": "age_25_plus",
        "excluded_postcode_categories": ["high_theft_metropolitan"],
        "fair_value_assessment_ref": "fva_motor_private_2026_q1",
    },
    "home_buildings": {
        "target_market_summary_category": "uk_resident_homeowner_buildings",
        "construction_categories": ["standard_brick", "standard_stone"],
        "excluded_postcode_categories": ["flood_zone_3"],
        "fair_value_assessment_ref": "fva_home_buildings_2026_q1",
    },
}


class SandboxProductCatalogueAdapter:
    """`sandbox-product-catalogue` adapter; read-only target-market lookup."""

    adapter_id = "sandbox_product_catalogue"

    def tool_specs(self) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                tool_name="product_catalogue.lookup",
                argument_contract=ProductCatalogueLookupArgs,
                return_contract_ref=(
                    "contracts/connector/uc1/product_catalogue_lookup_args.schema.json"
                ),
            ),
        )

    def invoke(
        self,
        *,
        tool_name: str,
        mode: str,
        context: ConnectorContext,
        arguments: BaseModel,
    ) -> ConnectorResult:
        del mode, context
        if tool_name != "product_catalogue.lookup":
            raise ConnectorError(
                f"SandboxProductCatalogueAdapter received unsupported tool {tool_name!r}"
            )
        if not isinstance(arguments, ProductCatalogueLookupArgs):
            raise TypeError(
                "SandboxProductCatalogueAdapter expected ProductCatalogueLookupArgs for "
                f"{tool_name!r}"
            )

        canned = _CANNED_PRODUCT_TARGET_MARKETS.get(arguments.product_family_category.value)
        if canned is None:
            return ConnectorResult(
                connector_invocation_id=uuid4(),
                output={
                    "connector": "sandbox_product_catalogue.local",
                    "product_family_category": arguments.product_family_category.value,
                    "lookup_status": "product_family_not_in_catalogue",
                },
            )
        return ConnectorResult(
            connector_invocation_id=uuid4(),
            output={
                "connector": "sandbox_product_catalogue.local",
                "product_family_category": arguments.product_family_category.value,
                "lookup_status": "product_family_found",
                "target_market": dict(canned),
            },
        )


def _is_outbound_comms_failure_fixture(arguments: OutboundCommsMessageArgs) -> bool:
    marker = "connector-failure fixture"
    return marker in arguments.subject.lower() or marker in arguments.body_text.lower()


__all__ = [
    "SandboxCustomerProfileAdapter",
    "SandboxDeclineLedgerAdapter",
    "SandboxOutboundCommsAdapter",
    "SandboxProductCatalogueAdapter",
    "SandboxQuotingQueueAdapter",
    "SandboxReferralInboxAdapter",
]
