import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { progressPath, subscribeProgress, type ProgressEvent } from "./sse";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly url: string;
  readonly init?: EventSourceInit;
  readonly listeners = new Map<string, EventListenerOrEventListenerObject[]>();
  close = vi.fn();

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.init = init;
    FakeEventSource.instances.push(this);
  }

  addEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject,
  ) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      const event = { data: JSON.stringify(data) } as MessageEvent;
      if (typeof listener === "function") {
        listener(event);
      } else {
        listener.handleEvent(event);
      }
    }
  }
}

describe("progress SSE", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds workflow-scoped progress paths", () => {
    expect(progressPath({ workflow_id: "uc2-legal-1" })).toBe(
      "/progress?workflow_id=uc2-legal-1",
    );
    expect(
      progressPath({
        workflow_id: "uc2-legal-1",
        correlation_id: "cor_uc2_legal_1",
      }),
    ).toBe(
      "/progress?workflow_id=uc2-legal-1&correlation_id=cor_uc2_legal_1",
    );
  });

  it("handles the BFF named progress event and the default message event", () => {
    const onEvent = vi.fn<(event: ProgressEvent) => void>();
    const stream = subscribeProgress("/progress", onEvent);
    const source = FakeEventSource.instances[0];

    const event = {
      id: "evt-uc2-010",
      workflow_id: "uc2-2026-05-24-0001",
      event_type: "workflow.step.completed",
      sequence: 12,
      step: "engagement_letter_send",
      payload: { gateway_verdict: "approval_required" },
      occurred_at: "2026-05-24T09:05:20Z",
      correlation_id: "cor_uc2_legal_demo_001",
    };

    source.emit("progress", event);
    source.emit("message", { ...event, id: "evt-uc2-011" });
    stream.close();

    expect(source.url).toBe("/api/progress");
    expect(source.init).toEqual({ withCredentials: false });
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, event);
    expect(source.close).toHaveBeenCalledTimes(1);
  });
});
