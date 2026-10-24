# Validating the validators

EvalGen (Shankar et al.) introduced two measures for aligning automated graders with human judgement. Coverage is the share of outputs humans marked bad that the grader also fails (a true negative rate). The false failure rate (FFR) is the share of outputs humans marked good that the grader wrongly fails.

Alignment is the harmonic mean of coverage and (1 - FFR). Cohen kappa measures chance-corrected agreement between the grader and a human.

Criteria drift: people need criteria to grade outputs, but grading outputs changes the criteria. Evaluation criteria therefore cannot be fixed before looking at real outputs, so graders must be easy to revise and re-run on stored transcripts.
