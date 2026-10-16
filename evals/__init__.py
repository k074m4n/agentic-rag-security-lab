"""Evaluation harness for the security lab.

Measures, per model and defense profile, how often an attack succeeds (attack
success rate) and how often the assistant still answers benign questions
correctly (utility). Each run executes in an isolated copy of the sample
codebase so runs never contaminate each other or the tracked repo.
"""
