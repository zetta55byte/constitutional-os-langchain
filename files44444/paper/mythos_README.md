# Mythos-Class Containment Architecture

**Unified Governance, Geometry, and Runtime Enforcement for Frontier-Model Security**

This repository contains the reference implementation, figures, and companion materials for the Mythos-Class Containment Architecture — the first security framework that unifies:

- **UAG** (Unified Attractor Grammar) — mathematical foundation ([Zenodo](https://doi.org/10.5281/zenodo.19448508))
- **Constitutional OS** — formal governance substrate ([Zenodo](https://doi.org/10.5281/zenodo.19258310))
- **CARE** — runtime curvature and drift enforcement ([GitHub](https://github.com/zetta55byte/care))

Together, these form a **theory → governance → runtime** pipeline for securing frontier-class, exploit-capable AI systems.

---

## Why this exists

Frontier models (Mythos-class systems) can:

- chain multi-step reasoning into exploit sequences
- discover or synthesize zero-days
- attempt covert channels
- escalate privileges
- hide traces

Traditional AI safety proposals don't address this threat model.  
Traditional security architectures don't address agentic reasoning drift.  
Mythos-Class Containment is the first architecture designed for the actual failure modes of modern frontier models.

---

## The three-layer integration

### 1. UAG — Unified Attractor Grammar

UAG provides the mathematical foundation for understanding model behavior as trajectories in a high-dimensional dynamical system. It contributes:

- **κ** (curvature) — sensitivity to perturbation
- **δ** (drift) — movement toward unstable attractors
- basin transitions — early indicators of agentic escalation
- theoretical guarantees (UAG Theorems 3 and 4, including the Kramers escape rate)

These signals become first-class security primitives.

> DOI: [10.5281/zenodo.19448508](https://doi.org/10.5281/zenodo.19448508)

### 2. Constitutional OS — formal governance substrate

Constitutional OS turns UAG's mathematical signals into governance rules. It provides:

- **typed deltas** — formal, reversible state transitions with mandatory reason fields
- **membranes** — enforceable constraints with Lyapunov-style stability proofs
- **reversible lineage** — complete auditability
- **multi-membrane consensus** — 3-of-5 governance vote

This is where "security policy" becomes machine-checkable law.

> DOI: [10.5281/zenodo.19258310](https://doi.org/10.5281/zenodo.19258310)

### 3. CARE — curvature-aware runtime enforcement

CARE operationalizes theory and governance at runtime. It provides:

- live curvature monitoring via exact Hessians (hcderiv v0.4.0)
- canary drift detection (CARE watches CARE)
- membrane M5 integration (curvature signal → governance vote)
- freeze / rollback / sentinel escalation
- deterministic replay and forensic snapshots
- rate limiting + anomaly detection (chain probe, all-endpoint burst)
- immutable append-only audit log (file / Redis / S3 backends)

CARE is the runtime nervous system of the architecture.

> GitHub: [zetta55byte/care](https://github.com/zetta55byte/care) · v0.2.0

---

## The eight-layer containment stack

| Layer | Name | Mechanism | Threat addressed |
|---|---|---|---|
| 1 | I/O membrane | Schema validation, depth limits | Malformed input, injection |
| 2 | Outbound channel strangulation | Default-deny egress, HMAC calls | Exfiltration, C2 |
| 3 | Behavioral deviation fingerprinting | Token-curvature, plan topology | Agentic escalation |
| 4 | Multi-membrane consensus (3-of-5) | M1–M5 independent vote | Single-point bypass |
| 5 | Out-of-band sentinel | Separate machine, freeze/rollback | Environment compromise |
| 6 | Deterministic replay and forensics | Immutable audit log, replay | Evidence destruction |
| 7 | Cold-storage execution zone | Air-gapped GPU jail | Persistence, lateral movement |
| 8 | Cross-model verification | Weaker verifier, epistemic check | Intent masking, deception |

Each layer addresses a distinct threat class. No single bypass is sufficient.  
Every failed escape attempt increases the system's evidence base and tightens its defenses.

---

## Figures

All figures are provided in [`figures/`](figures/) as SVG and PDF:

| File | Description |
|---|---|
| `fig1_architecture` | Full 8-layer containment stack |
| `fig2_membrane_consensus` | 3-of-5 membrane governance vote |
| `fig3_verifier_asymmetry` | Two-pilot cockpit |
| `fig4_uag_cos_care_pipeline` | Theory → Governance → Runtime |
| `fig5_escape_vs_containment` | Escape path vs containment path |

These map directly to the figures referenced in the paper.

---

## Paper

The full paper is included as:

- [`paper/main.tex`](paper/main.tex) — LaTeX source
- [`paper/main.pdf`](paper/main.pdf) — compiled PDF (14 pages)
- [`paper/references.bib`](paper/references.bib) — bibliography

**Contents:**
- formal threat model with adversary capability table
- mathematical grounding (UAG Theorems 3 and 4, Kramers escape rate)
- eight-layer architecture with per-layer threat mapping
- five-membrane consensus protocol
- runtime enforcement protocol (CARE integration)
- cross-model verification theory (verifier asymmetry proof)
- evaluation methodology
- references (UAG, Constitutional OS, CARE, Freidlin-Wentzell, Kramers 1940, Carlini et al. 2026)

> **Note:** Empirical results in Section 7 are preliminary. Full red-team evaluation results will be added in v1.1.

---

## Companion works

This repository is part of a three-paper ecosystem:

| Work | Role | DOI / Link |
|---|---|---|
| UAG | Theoretical foundation | [10.5281/zenodo.19448508](https://doi.org/10.5281/zenodo.19448508) |
| Constitutional OS | Governance substrate | [10.5281/zenodo.19258310](https://doi.org/10.5281/zenodo.19258310) |
| CARE v0.2.0 | Runtime enforcement | [github.com/zetta55byte/care](https://github.com/zetta55byte/care) |
| hcderiv v0.4.0 | Exact Hessian computation | [10.5281/zenodo.19433812](https://doi.org/10.5281/zenodo.19433812) |

Each work stands alone. Together they form the Mythos-Class Security Stack.

---

## Repository structure

```
.
├── paper/
│   ├── main.tex              # LaTeX source
│   ├── main.pdf              # Compiled paper (14 pages)
│   └── references.bib        # Bibliography (8 entries)
├── figures/
│   ├── fig1_architecture.svg
│   ├── fig2_membrane_consensus.svg
│   ├── fig3_verifier_asymmetry.svg
│   ├── fig4_uag_cos_care_pipeline.svg
│   ├── fig5_escape_vs_containment.svg
│   └── *.pdf                 # PDF versions for LaTeX inclusion
└── README.md
```

---

## Status

| Item | Status |
|---|---|
| Architecture (8 layers) | Complete |
| Formal threat model | Complete |
| Five-membrane consensus | Complete |
| Cross-model verification theory | Complete |
| Figures (5) | Complete |
| LaTeX source | Complete |
| Empirical red-team results | Preliminary — v1.1 |

---

## Citation

```bibtex
@misc{byte2026mythos,
  author    = {Byte, Zetta},
  title     = {Mythos-Class Containment Architecture:
               A Unified Framework for Frontier-Model Security,
               Governance, and Runtime Drift Control},
  year      = {2026},
  note      = {Preprint}
}
```

---

## License

MIT