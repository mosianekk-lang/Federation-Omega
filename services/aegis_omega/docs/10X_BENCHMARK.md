# 10× Benchmark Contract

AEGIS must not claim “10×” from architecture or synthetic tests alone.

## Higher-is-better objectives
- cross-source correlation throughput >= 10× baseline
- analyst cases handled per hour >= 10× baseline
- detector evaluation throughput >= 10× baseline
- historical corpus replay throughput >= 10× baseline

## Lower-is-better objectives
- threat-intel-to-detection latency <= 0.10× baseline
- investigation triage time <= 0.10× baseline
- evidence reconstruction time <= 0.10× baseline
- containment decision latency <= 0.10× baseline

## Mandatory quality floors
- unseen-family recall >= 0.90
- false-positive rate <= 0.02
- privacy leakage <= 0.001
- poisoning/drift/adversarial resilience >= 0.90
- calibration error <= 0.05
- provenance, shadow, canary and rollback tests must pass

## Experimental design
Training corpus, validation corpus and blind certification corpus must be separated. Market claims require comparable workloads, independently captured baselines, repeated runs, confidence intervals and no hidden hardware/data advantage.
