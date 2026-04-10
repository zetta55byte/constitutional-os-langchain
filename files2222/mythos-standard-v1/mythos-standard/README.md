# Mythos Standard v1.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19464889.svg)](https://doi.org/10.5281/zenodo.19464889)

**A Unified Framework for Governed AI Systems**

The Mythos Standard defines the interfaces, invariants, schemas, and evaluation procedures
required to implement a Mythos-Class governed runtime. It spans seven layers from exact
curvature math engines to federated governance infrastructure.

---

## The Mythos Stack

```
L1  hypercomplex / hcderiv  —  exact one-pass Hessians · XLA backend
L2  curvopt                 —  curvature-aware optimizer · trust-region
L3  Constitutional OS       —  formal governance substrate · typed reversible deltas
L4  CARE                    —  runtime curvature monitoring · drift detection
L5  mythos-threat-registry  —  machine-readable threat model · sim scenarios · harness specs
L6  mythos-containment      —  8-layer containment architecture · 5-membrane consensus
L7  constitutional-os-langchain  —  governed multi-agent execution
```

**Dependency order:**
`hcderiv → curvopt → COS → CARE → threat registry → containment → langchain`

**Evaluation loop:**
`sim scenarios → harness probes → registry updates → Section 7`

**Theory chain:**
`UAG → COS → CARE → M5 membrane → containment enforcement`

---

## Structure

```
mythos-standard/
│
├── standard/
│   ├── mythos_standard_v1.tex    # LaTeX source (camera-ready)
│   ├── mythos_standard_v1.pdf    # Compiled PDF
│   └── mythos_standard_v1.docx  # Word version
│
├── diagrams/
│   └── mythos_stack.md           # Mermaid stack diagram
│
├── examples/
│   └── README.md                 # Starter kit walkthrough
│
├── compliance/
│   └── checklist.json            # Self-assessment checklist (4 tiers)
│
├── README.md
└── LICENSE
```

---

## Compliance Tiers

| Tier | Requirements |
|---|---|
| Registry-only | L5 only — consumable threat registry |
| 3-layer starter | L3 + L4 + CMV — minimum viable containment |
| Full v0.1 | All 7 layers + v0.1 harness passing |
| Full v1.1 | All layers + expanded harness + public trace corpus |

---

## Governance Invariants

All Mythos-compliant systems must enforce:

- **Continuity** — no state transition severs the audit chain
- **Non-contradiction** — no two admitted deltas produce contradictory states
- **Human primacy** (*i*_HP) — all high-risk paths escalate to human operator
- **Escalation correctness** — all detected deviations routed to the correct layer

---

## Key Metrics

| Metric | Hard gate |
|---|---|
| SER (Silent Expansion Rate) | ≤ 0.05 |
| ADR (Adversarial Detection Rate) | ≥ 0.60 (v0.1), ≥ 0.80 (v1.1) |
| EC (Escalation Correctness) | ≥ 0.90 |
| Liveness | = 1.0 |

---

## Companion works

| Work | Role | DOI |
|---|---|---|
| MCCA paper | Architecture specification | [10.5281/zenodo.19464889](https://doi.org/10.5281/zenodo.19464889) |
| UAG | Mathematical foundation | [10.5281/zenodo.19448508](https://doi.org/10.5281/zenodo.19448508) |
| Constitutional OS | Governance substrate | [10.5281/zenodo.19258310](https://doi.org/10.5281/zenodo.19258310) |
| hcderiv | Runtime math engine | [10.5281/zenodo.19476000](https://doi.org/10.5281/zenodo.19476000) |
| Threat registry | Layer 0 | [github.com/zetta55byte/mythos-threat-registry](https://github.com/zetta55byte/mythos-threat-registry) |

---

## Citation

```bibtex
@misc{byte2026standard,
  author = {Byte, Zetta},
  title  = {Mythos Standard v1.0: A Unified Framework for Governed AI Systems},
  year   = {2026},
  note   = {Attractor Dynamics Research Lab}
}
```

## License

MIT
