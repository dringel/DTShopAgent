# .devcontainer/Dockerfile — the pinned base image, plus a workaround for
# one upstream defect in it.
#
# WHY THIS FILE EXISTS
# The pinned Microsoft devcontainer image ships an APT source for Yarn
# (dl.yarnpkg.com) whose signing key is no longer valid, so any apt-get
# update inside the image fails with:
#     NO_PUBKEY 62D54FD4003F6525
# Dev Container Features run apt-get update while installing. The
# desktop-lite Feature (our noVNC lab desktop) therefore fails, the whole
# Dev Container build fails, and Codespaces silently falls back to an
# Alpine RECOVERY container. That recovery container has no apt-get at
# all, so .devcontainer/setup.sh then dies at its package step with a
# misleading "sudo: apt-get: command not found" — three layers away from
# the actual cause. Diagnosing that from the symptom costs hours.
# Upstream: devcontainers/images#1752, #1797; devcontainers/features#1605.
#
# THE FIX
# Drop the stale Yarn source before any Feature runs; nothing in this kit
# uses Yarn. We then run apt-get update HERE so that if this workaround
# ever stops matching — the source moves to deb822 .sources, or the base
# image is re-pinned to a digest where it is already fixed — this build
# fails loudly with the real error instead of silently degrading to the
# Alpine recovery container again.
#
# REPINNING: change the digest deliberately, never implicitly, and re-run
# the T-21 clean-build check afterwards. Resolved from tag
# mcr.microsoft.com/devcontainers/python:1-3.12-bookworm on 2026-07-26.
FROM mcr.microsoft.com/devcontainers/python@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

USER root

RUN rm -f /etc/apt/sources.list.d/yarn*.list \
          /etc/apt/sources.list.d/yarn*.sources \
 && if [ -f /etc/apt/sources.list ]; then \
        sed -i '/dl\.yarnpkg\.com/d' /etc/apt/sources.list; \
    fi \
 && apt-get update \
 && rm -rf /var/lib/apt/lists/*
