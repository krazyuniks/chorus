# Agent Runtime

The Agent Runtime is the domain-side caller of the LLM provider port.

It resolves:

- tenant policy;
- approved agent version;
- prompt reference and prompt hash;
- model route;
- budget cap;
- invocation ID and correlation metadata.

It records decision-trail and transcript evidence for every invocation. It owns
no connector authority and no durable workflow state.

The execution pipeline is plain Python:

1. prepare context;
2. invoke the LLM provider port;
3. normalise result;
4. validate the output contract;
5. return the final response.

Provider SDKs stay behind `chorus/llm_provider/`.
