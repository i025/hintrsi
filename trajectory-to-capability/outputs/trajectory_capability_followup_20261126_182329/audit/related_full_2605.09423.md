[SimWorld Studio](https://arxiv.org/html/2605.09423) optimizes reusable scene-building skills and navigation decision rules, not model weights (§2.1–2.2, lines 00164–00179).

Failure action–observation trajectories yield prioritized rules; prior rules provide non-contradiction context, not an explicit success–failure contrast. LLM rule synthesis resembles teacher guidance; trajectory summaries and cross-episode principles overlap with distillation and fixed-model adaptation (§3.3, lines 00525–00526; §F.4, 02454–02472; §G.1, 02545–02562).

Scene-graph checks and a VLM judge verify physical validity and prompt alignment; corrections stop at PASS or three rounds. Recurring failures motivate skill creation, but independent skill-candidate selection is not specified (§C.2, 01210–01215). This overlaps with skill verification and state-aware feedback, not demonstrated alignment of corresponding program states across trajectories.

The authors report transfer to independently authored, unseen UE5 scenes; we did not replicate it (§F.2, 02430–02433). Spatial reasoning remains limiting (§A, 01137–01141). Their navigation curriculum does not test our functional-state-aligned versus chronological extraction comparison under fixed evidence and budgets.
