# Mythos starter kit — minimal compliance example

This directory contains the minimum viable Mythos-compliant system
for the 3-layer starter tier (L3 + L4 + CMV).

## Structure

```
examples/starter/
├── registry/
│   ├── threats.json        # 3 example threats (TM-002, TM-005, TM-012)
│   └── schema.json         # JSON Schema validator
├── sims/
│   └── SIM-031.json        # Governance drift scenario
├── harness/
│   └── HAR-SPEC-002.md     # Governance drift probe spec
├── cos_ruleset/
│   └── baseline.json       # Minimal COS governance profile
└── README.md
```

## Quick start

```bash
# Validate registry
python ../../tools/validate.py --registry registry/threats.json --coverage

# Run simulator scenario
python runner.py --scenario sims/SIM-031.json --model claude-sonnet-4-6

# Run harness probe
python probe_runner.py --probe 002 --dry-run
```

## Compliance tier

This example satisfies: **starter_3layer**
- COS governance profile loaded
- CARE monitor stub included
- HAR-SPEC-002 wired to SIM-031
- Registry validates with 0 errors
