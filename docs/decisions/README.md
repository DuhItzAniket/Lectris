# Decisions

Architecture decision records. An accepted record is never edited in substance; a new record
supersedes it. Status values: `Proposed` (waiting for the owner), `Accepted`, `Superseded`.

| ADR | Decision | Status |
|---|---|---|
| [0001](ADR-0001-propose-score-decide.md) | Rules propose, evidence scores, one decision layer accepts | Accepted |
| [0002](ADR-0002-risk-controlled-acceptance.md) | Acceptance threshold by Learn-then-Test, guaranteeing a harm rate | Accepted |
| [0003](ADR-0003-engine-aware-input.md) | Engine uncertainty in the data model; the GLYPHARIS JSON contract | Accepted (the `chars` field is Proposed to GLYPHARIS) |
| [0004](ADR-0004-stdlib-runtime-model-packs.md) | Standard library at run time; learned models as data packs; neural baselines isolated | Accepted for run time; **Proposed** for the research environment |
| [0005](ADR-0005-data-roles.md) | Fixed roles and page-level splits for every dataset | Accepted |
| [0006](ADR-0006-v01-as-baseline-and-parity.md) | v0.1 is the rule baseline and must be reproduced byte for byte | Accepted |
| [0007](ADR-0007-integration-first.md) | An integration release (v0.2) before the research phases | Accepted |
