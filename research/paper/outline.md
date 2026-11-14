# Paper outline

Working title: *LECTRIS: auditable, risk-controlled post-OCR correction with engine uncertainty.*
Each section names the experiments that feed it. No number is written here until its report
exists.

1. **Introduction.** Post-OCR correction trades fixes for damage, and the damage is not reported.
   Contributions:
   (i) a propose–evidence–decide architecture in which every edit carries its provenance;
   (ii) a Learn-then-Test acceptance threshold that bounds the expected harm rate on new pages;
   (iii) engine-aware evidence from the OCR engine's own uncertainty, through an open contract
   with a companion engine;
   (iv) an evaluation protocol that reports harm alongside error reduction, by page, with CIs;
   (v) a dependency-free implementation.
2. **Related work.** `research/related_work.md` (after verification).
3. **Method.** Architecture §3–§11: transforms, proposers, evidence, acceptance model, risk
   control, conflict resolution, flags.
4. **Experimental setup.** Data and splits (ADR-0005, DATASETS.md); engines (GLYPHARIS fixed model,
   Tesseract); baselines B0–B4; metrics and statistics (protocol §2–§5).
5. **Results.** RQ1, RQ3: LX-MAIN-*, LX-RISK-*. RQ2: LX-ABL-*. RQ4: LX-XFER-*. Test: LX-TEST-*.
6. **Error analysis.** RQ5: LX-ERR-*.
7. **Efficiency.** RQ6: LX-EFF-*.
8. **Limitations.** Scene-heavy dev data; guarantee only under exchangeability; one companion
   engine; English and Western European Latin script; automatic harm labels.
9. **Conclusion.**

Appendix: reproducibility (commands, hashes, seeds); the GLYPHARIS JSON contract; per-rule tables.
