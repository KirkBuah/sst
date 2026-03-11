"""
Plot: Number of servers vs number of inter-switch links
for Jellyfish vs 2D Mesh.

Jellyfish RRG(N_sw, k, r):
  - Servers = N_sw * (k - r)
  - Inter-switch links = N_sw * r / 2

2D Mesh (1 server port per switch):
  - N_sw switches in a p x p grid (p = sqrt(N_sw))
  - Servers = N_sw
  - Links = 2 * p * (p - 1)
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def mesh_links_and_servers(max_side=30):
    """Return (links, servers) arrays for square 2D meshes of increasing size."""
    links, servers = [], []
    for p in range(2, max_side + 1):
        n_sw = p * p
        n_links = 2 * p * (p - 1)  # horizontal + vertical edges
        links.append(n_links)
        servers.append(n_sw)  # 1 server per switch
    return np.array(links), np.array(servers)


def jellyfish_links_and_servers(k, r, max_sw=500):
    """Return (links, servers) arrays for Jellyfish with N_sw from 2 to max_sw."""
    N_sw = np.arange(2, max_sw + 1)
    links = N_sw * r / 2
    servers = N_sw * (k - r)
    return links, servers


def main():
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    mesh_l, mesh_s = mesh_links_and_servers()

    # --- Left: fixed k=12, vary r ---
    ax = axes[0]
    k = 12
    ax.plot(mesh_l, mesh_s, 'o-', color='#2ca02c', lw=2, ms=4,
            label='2D Mesh (1 server/switch)')
    for r in [3, 4, 6, 8]:
        jf_l, jf_s = jellyfish_links_and_servers(k, r)
        ax.plot(jf_l, jf_s, '--', lw=1.5,
                label='Jellyfish r=%d (%d srv/sw)' % (r, k - r))
    ax.set_xlabel("Number of inter-switch links")
    ax.set_ylabel("Number of servers")
    ax.set_title("Servers vs Links (k=%d-port switches)" % k)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # --- Right: vary k, fix r=k/2 ---
    ax = axes[1]
    ax.plot(mesh_l, mesh_s, 'o-', color='#2ca02c', lw=2, ms=4,
            label='2D Mesh (1 server/switch)')
    for k_val in [6, 12, 24, 48]:
        r = k_val // 2
        jf_l, jf_s = jellyfish_links_and_servers(k_val, r)
        ax.plot(jf_l, jf_s, '--', lw=1.5,
                label='Jellyfish k=%d, r=%d (%d srv/sw)' % (k_val, r, k_val - r))
    ax.set_xlabel("Number of inter-switch links")
    ax.set_ylabel("Number of servers")
    ax.set_title("Servers vs Links (Jellyfish r=k/2)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    out = SCRIPT_DIR / "plot_servers_vs_links.png"
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print("Saved %s" % out)


if __name__ == "__main__":
    main()
