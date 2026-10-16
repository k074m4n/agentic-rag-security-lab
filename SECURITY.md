# Security policy and responsible use

## Purpose

This repository is a **deliberately vulnerable research and teaching lab** for defensive
work on LLM agents. It studies how prompt injection, RAG poisoning and excessive agency
arise in a multi-agent assistant, and measures whether defenses hold. The attacks exist to
evaluate the defenses.

## What the lab does and does not contain

- Attack payloads target **only the bundled assistant**, through text placed in the
  bundled sample codebase (`data/sample_codebase/`). They are not exploits for third-party
  software or services.
- All credentials in the repository are **fake** placeholders created for the lab.
- "Exfiltration" scenarios are simulated locally (writing a local file or printing to the
  console). The lab has no real external endpoint and collects no data.
- The repository contains no malware, credential stealers, scanners or tooling for
  attacking other systems.

## Intended use

- Run it locally, against the bundled sample codebase, on a machine you control.
- Do not point the assistant or the payloads at systems, codebases or accounts you do not
  own or are not explicitly authorized to test.
- Keep `GRADIO_SHARE=false` and `ENABLE_CODE_AGENT=false` unless you understand the risk;
  see the README's *Known attack surface* section.

## Reporting a vulnerability

The documented findings (F1–F8 in the README) are intentional. If you find an
**unintended** issue, for example a way for the lab to affect anything outside its
workspace, report it privately via GitHub's
[private vulnerability reporting](../../security/advisories/new) for this repository rather
than in a public issue.

Report issues in upstream dependencies (smolagents, Gradio, LiteLLM, ...) to those projects.
