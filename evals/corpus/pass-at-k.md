# pass@k and pass^k

pass@k is the probability that at least one of k sampled trials succeeds. The unbiased estimator is 1 - C(n-c, k) / C(n, k), where n is the number of trials and c the number that passed. It measures peak capability when retries or best-of-N sampling are allowed.

pass^k (pass-hat-k) is the probability that all k trials succeed, estimated as (c/n)^k. It measures consistency and matters when an agent must be reliable every single time, for example for financial or medical actions.

A task with 0 passes out of k attempts is a systematic failure (a prompt or tool bug). A task with some passes is flaky (non-determinism).
