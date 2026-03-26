"""
Generate chapter header images for OpenChapters.

Each header is 2480x1240 pixels, 300 DPI, RGB, saved as PDF.
Style: mathematical expressions and symbols on a soft gradient background,
mimicking the existing NUMSYSheader.pdf style.
"""

import random
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
import numpy as np

# 2480x1240 px at 300 DPI = 8.267 x 4.133 inches
WIDTH_IN = 2480 / 300
HEIGHT_IN = 1240 / 300
DPI = 300

# Color palettes per chapter (bg gradient start, bg gradient end, accent colors)
CHAPTERS = {
    "3DROTS": {
        "title": "3D Rotation Representations",
        "bg": ("#f0e6f6", "#e0f0ff"),
        "accents": ["#7c3aed", "#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd"],
        "formulas": [
            r"$R(\phi_1,\Phi,\phi_2)$",
            r"$\mathbf{q} = q_0 + q_1\mathbf{i} + q_2\mathbf{j} + q_3\mathbf{k}$",
            r"$\mathrm{SO}(3)$",
            r"$|\mathbf{q}| = 1$",
            r"$R_{ij} = \delta_{ij}\cos\omega + n_in_j(1-\cos\omega) - \epsilon_{ijk}n_k\sin\omega$",
            r"$(\phi_1, \Phi, \phi_2)$",
            r"$\omega = 2\arccos(q_0)$",
            r"$\hat{n} = (n_1, n_2, n_3)$",
            r"$\mathbf{p} = \hat{n}\tan(\omega/2)$",
            r"$S^3$",
        ],
        "big_symbols": [r"$R$", r"$\phi$", r"$\Phi$", r"$\omega$", r"$\mathbf{q}$"],
    },
    "BASCRY": {
        "title": "Crystallographic Computations",
        "bg": ("#e8f5e9", "#e3f2fd"),
        "accents": ["#2e7d32", "#1565c0", "#00897b", "#558b2f", "#0277bd"],
        "formulas": [
            r"$\mathbf{a}_i \cdot \mathbf{a}_j^* = \delta_{ij}$",
            r"$g_{ij} = \mathbf{a}_i \cdot \mathbf{a}_j$",
            r"$d_{hkl} = 1/|\mathbf{g}_{hkl}|$",
            r"$V = \mathbf{a}_1 \cdot (\mathbf{a}_2 \times \mathbf{a}_3)$",
            r"$(hkl)$",
            r"$[uvw]$",
            r"$\mathbf{g}_{hkl} = h\mathbf{a}_1^* + k\mathbf{a}_2^* + l\mathbf{a}_3^*$",
            r"$hu + kv + lw = 0$",
        ],
        "big_symbols": [r"$(hkl)$", r"$[uvw]$", r"$g_{ij}$", r"$d$"],
    },
    "GRAINB": {
        "title": "Grain Boundaries",
        "bg": ("#fff3e0", "#fce4ec"),
        "accents": ["#e65100", "#c62828", "#bf360c", "#d84315", "#b71c1c"],
        "formulas": [
            r"$\Delta g = g_B \cdot g_A^{-1}$",
            r"$\Sigma$",
            r"$\theta = \omega_{min}$",
            r"$\mathrm{MFZ}$",
            r"$\mathrm{CSL}$",
            r"$\hat{n} \cdot [\mathbf{e}_1 \times \mathbf{e}_2]$",
            r"$\mathrm{FZ}$",
            r"$(\omega, \hat{n})$",
        ],
        "big_symbols": [r"$\Sigma$", r"$\Delta g$", r"$\theta$", r"$\omega$"],
    },
    "MICROD": {
        "title": "Microstructure Descriptors",
        "bg": ("#e8eaf6", "#f3e5f5"),
        "accents": ["#283593", "#6a1b9a", "#4527a0", "#1a237e", "#7b1fa2"],
        "formulas": [
            r"$\bar{L} = 1/P_L$",
            r"$S_V = 2P_L$",
            r"$V_V = A_A = L_L = P_P$",
            r"$N_A = N_V \cdot \bar{D}$",
            r"$B = \frac{1}{4\pi}\oint \kappa\, dS$",
            r"$F_h$",
            r"$A = \pi r^2$",
            r"$L/\pi$",
        ],
        "big_symbols": [r"$S_V$", r"$V_V$", r"$N_A$", r"$P_L$"],
    },
    "ORISYM": {
        "title": "Orientations and Symmetry",
        "bg": ("#e0f7fa", "#e8f5e9"),
        "accents": ["#00695c", "#2e7d32", "#00838f", "#1b5e20", "#006064"],
        "formulas": [
            r"$g \in \mathrm{SO}(3)/\mathcal{S}$",
            r"$\mathrm{FZ}$",
            r"$\rho = \hat{n}\tan(\omega/2)$",
            r"$\mathcal{S} = \{s_1, s_2, \ldots, s_n\}$",
            r"$g' = s_i \cdot g \cdot s_j^{-1}$",
            r"$\omega_{max}$",
            r"$O_h$",
            r"$D_6$",
        ],
        "big_symbols": [r"$\mathrm{FZ}$", r"$g$", r"$\mathcal{S}$", r"$O_h$"],
    },
    "PROJTS": {
        "title": "Useful Projections",
        "bg": ("#fce4ec", "#e8eaf6"),
        "accents": ["#880e4f", "#311b92", "#ad1457", "#4a148c", "#c2185b"],
        "formulas": [
            r"$(X,Y) = \frac{(x,y)}{1+z}$",
            r"$S^2 \to \mathbb{R}^2$",
            r"$(X,Y) = \sqrt{\frac{2}{1+z}}(x,y)$",
            r"$(X,Y) = \frac{(x,y)}{z}$",
            r"$S^{n-1}$",
            r"$B^{n-1}$",
            r"$|\mathbf{p}| \leq 1$",
            r"$\pi: S^2 \to D^2$",
        ],
        "big_symbols": [r"$S^2$", r"$\pi$", r"$D^2$", r"$X$"],
    },
    "PRPSYM": {
        "title": "Material Properties and Symmetry",
        "bg": ("#f1f8e9", "#fff9c4"),
        "accents": ["#33691e", "#f57f17", "#827717", "#9e9d24", "#689f38"],
        "formulas": [
            r"$T_{ij} = T_{ji}$",
            r"$C_{ijkl} = C_{klij}$",
            r"$\sigma_{ij} = C_{ijkl}\,\varepsilon_{kl}$",
            r"$\mathrm{Neumann}$",
            r"$\mathcal{S} \subseteq \mathcal{G}$",
            r"$T'_{ij} = a_{ik}a_{jl}T_{kl}$",
            r"$n_{ind}$",
        ],
        "big_symbols": [r"$C_{ijkl}$", r"$T_{ij}$", r"$\mathcal{S}$", r"$\sigma$"],
    },
    "TENSOR": {
        "title": "Introduction to Tensors",
        "bg": ("#e3f2fd", "#e0f2f1"),
        "accents": ["#0d47a1", "#004d40", "#01579b", "#006064", "#1565c0"],
        "formulas": [
            r"$T'_{ij} = a_{ip}a_{jq}T_{pq}$",
            r"$\mathbf{a} \times \mathbf{b} = \epsilon_{ijk}a_jb_k\,\hat{e}_i$",
            r"$\epsilon_{ijk}\epsilon_{ilm} = \delta_{jl}\delta_{km} - \delta_{jm}\delta_{kl}$",
            r"$\delta_{ij}$",
            r"$T_{ij\ldots} = a_{ip}a_{jq}\cdots T_{pq\ldots}$",
            r"$\mathrm{rank}\,n$",
            r"$a_{ij}a_{kj} = \delta_{ik}$",
        ],
        "big_symbols": [r"$T_{ij}$", r"$\epsilon_{ijk}$", r"$\delta_{ij}$", r"$a_{ip}$"],
    },
    "TEXCOM": {
        "title": "Texture Components",
        "bg": ("#fff8e1", "#fbe9e7"),
        "accents": ["#ff6f00", "#bf360c", "#e65100", "#d84315", "#f57c00"],
        "formulas": [
            r"$\{hkl\}\langle uvw\rangle$",
            r"$\mathrm{Cube}:\ \{001\}\langle100\rangle$",
            r"$\mathrm{Goss}:\ \{110\}\langle001\rangle$",
            r"$\mathrm{Brass}:\ \{110\}\langle1\bar{1}2\rangle$",
            r"$\mathrm{Copper}:\ \{112\}\langle11\bar{1}\rangle$",
            r"$\mathrm{S}:\ \{123\}\langle63\bar{4}\rangle$",
            r"$f(g)$",
            r"$\mathrm{ODF}$",
        ],
        "big_symbols": [r"$\{hkl\}$", r"$f(g)$", r"$\langle uvw\rangle$"],
    },
}


def generate_header(abbr: str, config: dict, output_path: Path):
    """Generate a single chapter header image."""
    random.seed(hash(abbr))
    np.random.seed(abs(hash(abbr)) % (2**31))

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), dpi=DPI)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("auto")
    ax.axis("off")

    # Gradient background
    bg1 = matplotlib.colors.to_rgb(config["bg"][0])
    bg2 = matplotlib.colors.to_rgb(config["bg"][1])
    gradient = np.linspace(0, 1, 256).reshape(1, -1)
    gradient = np.vstack([gradient] * 128)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("bg", [bg1, bg2])
    ax.imshow(gradient, extent=[0, 1, 0, 1], aspect="auto", cmap=cmap, alpha=0.9, zorder=0)

    # Large semi-transparent background symbols
    for sym in config.get("big_symbols", []):
        x = random.uniform(0.05, 0.95)
        y = random.uniform(0.1, 0.9)
        size = random.randint(40, 80)
        color = random.choice(config["accents"])
        alpha = random.uniform(0.08, 0.18)
        ax.text(x, y, sym, fontsize=size, ha="center", va="center",
                color=color, alpha=alpha, zorder=1,
                fontfamily="serif")

    # Scattered formulas
    formulas = config.get("formulas", [])
    positions = []
    for formula in formulas * 2:  # repeat to fill space
        for _ in range(20):  # try to find non-overlapping position
            x = random.uniform(0.02, 0.98)
            y = random.uniform(0.02, 0.98)
            # Check distance from existing positions
            too_close = any(abs(x - px) < 0.15 and abs(y - py) < 0.08
                          for px, py in positions)
            if not too_close:
                break
        positions.append((x, y))
        size = random.choice([9, 10, 11, 12, 14, 16])
        color = random.choice(config["accents"])
        alpha = random.uniform(0.35, 0.75)
        rotation = random.uniform(-8, 8)
        ax.text(x, y, formula, fontsize=size, ha="center", va="center",
                color=color, alpha=alpha, rotation=rotation, zorder=2,
                fontfamily="serif")

    # Decorative circles/shapes in background
    for _ in range(random.randint(5, 12)):
        x = random.uniform(0, 1)
        y = random.uniform(0, 1)
        r = random.uniform(0.02, 0.12)
        color = random.choice(config["accents"])
        circle = mpatches.Circle((x, y), r, fill=True, color=color,
                                  alpha=random.uniform(0.03, 0.08), zorder=0)
        ax.add_patch(circle)

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    # Save as PDF
    with PdfPages(str(output_path)) as pdf:
        pdf.savefig(fig, dpi=DPI, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    print(f"  Generated: {output_path.name}")


def main():
    monorepo = Path("/Volumes/Drive2/Files/Books/OC/OpenChapters/src")

    for abbr, config in CHAPTERS.items():
        # Find the chapter directory
        for cdir in monorepo.iterdir():
            if not cdir.is_dir():
                continue
            tex_files = list(cdir.glob("*.tex"))
            for tex in tex_files:
                text = tex.read_text(errors="replace")
                if f"\\chabbr}}{{{abbr}}}" in text:
                    pdf_dir = cdir / "pdf"
                    pdf_dir.mkdir(exist_ok=True)
                    output = pdf_dir / f"{abbr}header.pdf"
                    generate_header(abbr, config, output)
                    break


if __name__ == "__main__":
    main()
