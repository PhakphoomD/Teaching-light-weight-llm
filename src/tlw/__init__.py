# tlw = "Teaching Lightweight LLMs" — this project's core library, and also the
# name of the conda environment it runs in (`envs/tlw`, Constitution §0.5).
#
# It is the config-driven core (ADR-017): one run is one YAML resolved through
# six registries (student / teacher / preset / memory / params+arm / eval), so
# behaviour changes by editing configuration, never by editing this package.
# Blocks: config/ registries.py memory/ prompts/ evaluation/ loop/ analysis/
# providers.py runner.py. See .claude/rules/structure.md.
