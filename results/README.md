# Generated results

- `cache/` contains exact generated Q-market and path-congruent hedge-price
  artefacts. Only `precompute_q_market_and_hedge_cache.py` may write them.
- `runs/` contains timestamped local workflow outputs and is not versioned.
- `runtime_cache/` contains non-market projection accelerators and is not
  versioned.
- `document_figures/` contains the small reviewed figures and provenance files
  that are intentionally versioned with the documentation.

Never move a plot from a non-completed run into `document_figures/`. A curated
figure must identify the completed run, sample roles, cache fingerprints,
deployed-policy status and numerical result from which it was generated.
