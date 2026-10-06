# Model registry monitoring

The scheduled `Model Registry Monitor` workflow protects the Advisor from
quiet model-catalog drift.

## What it watches

Only official sources listed in `registry.json` are scanned by default.

The scanner extracts model/mode-like signals, stores their fingerprints, and
compares them with the last successful baseline.

## Alert policy

The workflow does **not** fail simply because a provider webpage changed.

It requires manual review only when an already-baselined official source
contains a newly observed model-like signal that the registry does not know.

This keeps the monitor useful without turning normal documentation edits into
noise.

## Baseline behavior

The first successful run initializes history and does not claim every existing
unregistered-looking string is new.

If one provider page temporarily fails, the previous baseline for that source
is retained instead of being erased.

## Update policy

A monitor alert is a review trigger, not permission to edit the registry
automatically. Confirm the model/status/specifications from official provider
documentation before changing routing candidates.
