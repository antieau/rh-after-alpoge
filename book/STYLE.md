# Style of the RH book

This book follows the style of the Hironaka book,
[`lean/hironaka/book/STYLE.md`](../../hironaka/book/STYLE.md). Its rules for statements and for
introductory paragraphs, its 13 numbered rules and its Words section apply here unchanged, with the
examples given there. `tools/check_style.py` is the same checker, with this book's names for
rule 13.

## Differences

- **Rule 7.** Alpöge's Lean is the only source of the proof. Write "Alpöge" where a construction
  is theirs, and name the published source where a result is standard; never write "the source".
  Lean names appear only in `\leanref` lines and correspondence notes.
- **Standard results.** A result from the literature is stated in full and cited, with no proof.
  Its correspondence note says how the Lean statement relates to the published one.
- **Rule 13.** One name per object, and one object per name. Record each choice here, and add the
  rejected name to the checker's rule 13 pattern. The chosen names so far:
  - *frame*, only for the almost tight frames of Chapter 5. Chapter 3's group data
    $(A,h,a_0)$ with Galois group $G_\Phi$, on which a host field is built, is a *Galois datum*
    $\Phi$; Chapter 8's family $X=(X_v)$ of matrices at the infinite places is a *metric* on
    $K^d$. Labels such as `hf-frame` keep their names.
  - *top classes* $T_{\mathrm{top}}$ for the host's set of top classes, and *thick places* for
    the Behrend set $T_2$ (Chapter 3); not "thick set" for $T_{\mathrm{top}}$.
  - *exponent* $\varepsilon$ of a family, not "parameter".
  - *split subgroup* $\Psi$ (and $\Psi_A$, $\Psi_H$); $\Phi$ is not used for it.
  - $d_u$ is the rank of $N_u$; write $\dim M_u$ for the dimension of $M_u$.
  - *weighted Chebyshev sum* $G_\psi$ of a cyclic level, *corrected Chebyshev sum* $g_\chi$ of a
    character; *level*, *cyclic level*, *windows of exponent* $\lambda$.
  - *host field*, *host*, *rank datum*, *admissible pair*, *good pair*.
  - *tiled set of positions*, and an orbit *tiled for* $T$ (Chapter 3); not "good" for these.
  - *controlled window*, not "good window"; an *Eisenstein datum* $(\ell,k,\psi,K)$ (Chapter 10).
  - *group coherence*, not "group compatibility"; the *degree-zero condition*, not "degree-zero
    law" (Chapter 7). *Good* is reserved for Chapter 11's good representations.
  - *surplus* $S(p,t_0)$ of a served representative (Chapter 7); the *served gain* is only
    $\mathrm{gain}^{\mathrm s}_j(p)$.
  - *run system* (Chapter 7) for the Lean's frames of $T$, and *tower decomposition* (Chapter 6),
    not "frame". *Level* is Chapter 2's level of a family of
    characters; a theta datum's set of places is its *ramification set* (Chapters 6 and 13), not
    its "level".
  - *laws*, *good* and *compatible*, as Chapter 11 defines them for the local correspondence.
  - *separated characters* and *separated tuples* of labels (Chapter 9), not "good characters".
  - *lift-distinct types* of a family of definite forms (Chapter 8), not "separated types".
  - *pattern* for the Lean's `Lbl` in Chapter 11's depth-zero support; "label" is kept for its
    other meanings.
  - *Heisenberg lift* for the map of Chapter 8's coset theta functions, and *split representative*
    for the Lean's `IsLift`; "theta lift" and "lift" keep their other meanings.
  - *formal chart* for the Lean's `GermAt` (Chapter 9).
  - *Witt torus* for the Lean's `Frame` in the assembly's Theorem K ("frame" is reserved for
    Chapter 5).
  - *ample theta presentation* for the Lean's `AmpFrames` (Chapter 9).
  - *Tate-free* for the Lean's `GalN.V.Unlinked` (Chapter 10); "unlinked" keeps its meaning in
    `gal-plain`.
  - *torsor datum* for the Lean's `Frame` in Chapter 11's thickening cohomology.
  - *place datum* for the Lean's `Alg.Frame` and *form datum* for its `Alg.FormData`, in Chapter
    10's $V_D$ model.
  - the *filtration* of a torsor datum $\Phi$, its *graded constant*, and $\mathrm{Th}^{(s)}$, in
    Chapter 11's level-one finiteness.
  - *torus extension* for the Lean's abelian extension in Chapter 9's Hodge germs
    (`cv-germs-abelian-extension`).
  - *triangulation* for the Lean's `Box` in Chapter 10's near lemma; "box" is used in Chapter 3.
  - *box path* and *block module* in Chapter 8's short Hida inclusion; "path" alone is Chapter 12's,
    and the *Hida setting* is a different object.
  - *periodic cube datum* in Chapter 9's Appell–Humbert lemma (`cv-origin-hodge-norm-form-appell-datum`).
  - *section complex* for the Lean's `Perf` and *cubical Weil pairing* in Chapter 9's abelian
    schemes over a discrete valuation ring.
  - $r=k+m-1$ for the rank of a rank datum (Definition `th-ranks`), not $r_0$; $r_\ast$ is only the
    helper prime and $q_0$ only the auxiliary prime of Definition `th-grid-places`.
  - $p_{de}$ and $p'_{de}$ for the level primes of a host, not $p_{\mathrm{de}}$.
  - $\mathcal Q$ and $\mathcal Q_0$ for the properties of column choices in "at all large stages
    after" (Definition `asm-stage-construction`), not $q$ and $q_0$.
  - *$\ell$-distinct* (Definition `sha-eigensystem-distinctness`), not "condition (U)", in
    Chapter 10's descent of windows.
  - $\Gamma_u$ only for the rational stabilizer of the Bessel data of a word $u$ (the Lean's `Srat`),
    and $\Gamma^H_u$ for the rational points that fix $e_a$, $f_a$ and $z_u$ (the Lean's `Gam`), in
    the assembly's Poincaré series (Definition `asm-division-kernel-finite-series-function-bessel`(4));
    not $\Gamma_u$ for the latter.
  - *point functor*, *small presentation* and *Zariski atlas* for the Lean's `Fn`, `Small` and
    its atlases in Chapter 11's realization; "atlas" alone is Chapter 9's holomorphic atlas. The
    *divided power filtration* $\mathrm{Fil}^r$ of a thickening of a point functor (Chapter 11).
  - $\mathfrak A=\mathfrak c\,\mathcal O\,\mathfrak b^{-1}$, the ideal of the host (Chapters 6, 8, 9 and the
    assembly), and $\mathfrak A_0=\mathfrak b^{-1}$, the vacuum ideal of Definition
    `is-vacuum-theta-vectors` (the Lean's `AA0`).
