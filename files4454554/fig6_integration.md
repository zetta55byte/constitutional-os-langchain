# Fig6 integration materials

---

## README.md block (paste after the Figures table)

```markdown
### Ecosystem map

![Mythos Research Ecosystem — Layered Stack](figures/fig6_ecosystem_stack.svg)

**Figure 6.** The Mythos ecosystem integrates four layers:
- **UAG** — theoretical foundation ([10.5281/zenodo.19448508](https://doi.org/10.5281/zenodo.19448508))
- **Constitutional OS** — governance substrate ([github.com/zetta55byte/constitutional-os](https://github.com/zetta55byte/constitutional-os))
- **CARE** — runtime enforcement ([github.com/zetta55byte/care](https://github.com/zetta55byte/care))
- **Mythos-Class Containment Architecture** — full system ([github.com/zetta55byte/mythos-containment](https://github.com/zetta55byte/mythos-containment))

All artifacts are cross-linked and archived under DOI [10.5281/zenodo.19464889](https://doi.org/10.5281/zenodo.19464889).
```

---

## LaTeX snippet (already inserted into main.tex — paste here for reference)

```latex
\begin{figure}[h]
\centering
\includegraphics[width=0.95\linewidth]{fig6_ecosystem_stack}
\caption{Mythos research ecosystem --- layered stack. The four-layer integration
from UAG (attractor geometry, Layer~0) through Constitutional OS (governance
substrate, Layer~1) through CARE (runtime enforcement, Layer~2) to the full
Mythos-Class Containment Architecture (Layer~3). All six public artifacts are
shown with their DOIs and repository links.}
\label{fig:ecosystem}
\end{figure}
```

---

## Files generated

| File | Size | Use |
|---|---|---|
| `fig6_ecosystem_stack.svg` | 7KB | GitHub README, GitHub Pages, web |
| `fig6_ecosystem_stack.pdf` | 32KB | LaTeX inclusion |
| `mythos_arxiv_v1.1.zip` | 155KB | Updated arXiv bundle (8 files: 6 figs + tex + bib) |
| `main.pdf` | 15 pages | Compiled paper with fig6 included |

---

## Deploy checklist

- [ ] Copy `fig6_ecosystem_stack.svg` and `fig6_ecosystem_stack.pdf` into repo `figures/`
- [ ] Paste README block above into `README.md` after the Figures table
- [ ] Replace `mythos_arxiv_v1.zip` with `mythos_arxiv_v1.1.zip` in `paper/`
- [ ] Commit: `git add . && git commit -m "Add fig6 ecosystem stack" && git push`
