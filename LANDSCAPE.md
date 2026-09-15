# Landscape and adopted components

The distinction below matters: “reviewed documentation” does not mean “implemented and benchmarked.”
No private challenge prompts, outcomes or artifacts were uploaded to an evaluation SaaS product.

| Component or approach | What was evaluated | Decision and evidence |
|---|---|---|
| Published Harbour backend and scorers | Inspected source; ran seeded-backend tests and the original 87-test suite | Adopted unchanged. These define task truth and official checked policy rules; release hashes are verified. |
| Published starter eval | Inspected its completion/summary criterion and reproduced an unsafe committed action | Rejected as the migration gate. A summary and commit do not establish the correct database state. |
| GPT-4.1 mini and GPT-5 mini exact pins | Official model documentation, challenge price pins and real API runs | Kept the prescribed dated models. The measured primary comparison is lateral budget-class migration. No flagship verifier or hidden fallback was used. |
| Python unittest, SQLite and standard-library HTTP/process tooling | Implemented and executed the candidate suite and isolated workers | Adopted. No runtime package installation is needed, and the small loop can be audited directly. |
| LLM-as-judge for equivalence | Considered against the deterministic decision contract; not benchmarked | Not used for headline scores. Another model can add cost and judge variability while failing to verify actual writes. Semantic review remains useful for summaries and policy gaps. |
| Promptfoo | Documentation reviewed, not integrated or benchmarked | Its configurable test cases and assertions could organise a larger prompt regression suite. Here the custom evaluator must reopen Harbour databases and honour the exact official contract, so another runtime was unnecessary. |
| LangSmith | Documentation reviewed, not integrated or benchmarked | Dataset experiments and trace comparison could support a larger team. Local JSONL, hashes and SQLite were sufficient for this private take-home; hosted data handling and another dependency were not needed. |

Official sources consulted: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini),
[reasoning-token guidance](https://developers.openai.com/api/docs/guides/reasoning),
[Promptfoo configuration](https://www.promptfoo.dev/docs/configuration/guide/), and
[LangSmith evaluation](https://docs.langchain.com/langsmith/evaluation).
Model docs were checked on 2026-09-08; evaluation-framework docs on 2026-09-09.

Official OpenAI documentation informed the decision to preserve the exact model snapshots and was used
to verify endpoint support and completion-token semantics. It did not justify selecting a newer model or
changing the challenge's frozen pricing. The latest challenge calibration used the Responses API; our fresh
comparison uses the same Chat Completions transport for both models and discloses that difference.

Before the next migration I would fund a maintained private regression dataset with repeated runs,
human-reviewed semantic checks, an independent metering gateway, and durable write idempotency.
Those improve evidence and operational guarantees more directly than adding an unmeasured agent framework.
