"""Render the ASR heatmap (light + dark) from the archived result files into media/.

    uv run --with matplotlib --with numpy python -m evals.plot_results

Reproduces media/results_heatmap_{light,dark}.png used in the README.
"""
# ruff: noqa: E701, E702, E401
import collections
import json

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


def load(f):
    with open(f) as fh:
        return [json.loads(ln) for ln in fh]
rows = load("evals/baselines/attacks_all.jsonl")
agg = collections.defaultdict(lambda:[0,0])
for r in rows:
    if r.get("error"): continue
    agg[(r["task_id"], r["model"].split("/")[-1], r["defense"])][0] += 1 if r.get("attack_success") else 0
    agg[(r["task_id"], r["model"].split("/")[-1], r["defense"])][1] += 1

profs = ["baseline","d1","d1d2","d1d2d3","d1d2d3d4","full"]
prof_lbl = ["none","+d1","+d2","+d3","+d4","full"]
models = [("gpt-oss-120b","gpt-oss 120b"),("gemini-2.5-flash-lite","gemini 2.5 flash-lite"),("deepseek-v4-flash","deepseek v4 flash")]
order = [("a_indirect","Indirect injection"),("a_indirect_grep","Indirect (via grep)"),
("a_rag","RAG poisoning"),("a_stored","Stored injection"),("a_kb_overwrite","Self-poison KB write"),
("a_cross_agent","Cross-agent escalation"),
("a_secrets_in_kb","Secret leak (no attacker)"),("a_secrets_injection","Secret leak (forced)"),
("a_resource","Resource exhaustion"),("a_direct_jailbreak","Direct jailbreak")]

def val(t,m,d):
    s,n = agg.get((t,m,d),[0,0]); return 100*s/n if n else np.nan

def render(mode):
    if mode=="dark":
        bg="#0d1117"; ink="#e6edf3"; muted="#8b949e"; grid="#30363d"
        cmap=LinearSegmentedColormap.from_list("asr",["#15202b","#8a3b2e","#f0553a","#ff8c66"])
        plt.rcParams["savefig.facecolor"]=bg
    else:
        bg="#ffffff"; ink="#1f2328"; muted="#656d76"; grid="#d0d7de"
        cmap=LinearSegmentedColormap.from_list("asr",["#f6fbf7","#fde0d0","#f0553a","#b11226"])
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.6), facecolor=bg)
    for ax, (mid, mname) in zip(axes, models, strict=False):
        M = np.array([[val(t,mid,d) for d in profs] for t,_ in order])
        ax.set_facecolor(bg)
        im = ax.imshow(M, cmap=cmap, vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(profs))); ax.set_xticklabels(prof_lbl, fontsize=9, color=muted)
        if ax is axes[0]:
            ax.set_yticks(range(len(order))); ax.set_yticklabels([n for _,n in order], fontsize=9, color=ink)
        else:
            ax.set_yticks([])
        ax.set_title(mname, fontsize=11, color=ink, pad=8, fontweight="bold")
        for i in range(len(order)):
            for j in range(len(profs)):
                v=M[i,j]
                if np.isnan(v): continue
                tc = "#ffffff" if v>=55 else ("#3a2f2f" if mode=="light" else "#d7c9c0")
                ax.text(j,i,f"{v:.0f}", ha="center", va="center", fontsize=8.5, color=tc, fontweight="bold")
        for s in ax.spines.values(): s.set_color(grid)
        ax.set_xticks(np.arange(-.5,len(profs),1), minor=True)
        ax.set_yticks(np.arange(-.5,len(order),1), minor=True)
        ax.grid(which="minor", color=bg, linewidth=2); ax.tick_params(which="minor", length=0)
        ax.tick_params(which="major", length=0)
    fig.suptitle("Attack success rate (%) — defenses off → full  ·  lower is better",
                 fontsize=13, color=ink, fontweight="bold", y=0.99)
    cbar=fig.colorbar(im, ax=axes, fraction=0.022, pad=0.015)
    cbar.set_label("ASR %", color=muted, fontsize=9); cbar.ax.yaxis.set_tick_params(color=muted)
    plt.setp(plt.getp(cbar.ax,"yticklabels"), color=muted, fontsize=8)
    cbar.outline.set_edgecolor(grid)
    fig.text(0.013, 0.015, "N=20 (baseline) / 10 (per defense)  ·  profiles cumulative: +d1 spotlight+policy, +d2 detection, +d3 least-privilege, full +d5 output redaction",
             fontsize=7.5, color=muted)
    out=f"media/results_heatmap_{mode}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=bg)
    print("wrote", out)

render("light"); render("dark")
