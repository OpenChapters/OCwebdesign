"""
Generate chapter header images for OpenChapters.

Each header is 2480x1240 pixels, 300 DPI, RGB, saved as PDF.
Style: mathematical expressions and symbols on a soft gradient background,
with up to 4 actual chapter figures embedded (blurred, rotated, semi-transparent).
"""

import random
import subprocess
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches
import numpy as np

try:
    from PIL import Image, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# 2480x1240 px at 300 DPI = 8.267 x 4.133 inches
WIDTH_IN = 2480 / 300
HEIGHT_IN = 1240 / 300
DPI = 300

CHAPTERS = {
    "2DROTS": {
        "title": "2D Rotations",
        "bg": ("#f0e6f6", "#e0f0ff"),
        "accents": ["#7c3aed", "#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd"],
        "formulas": [
            r"$R(\theta)$",
            r"$[\cos\theta, -\sin\theta; \sin\theta, \cos\theta]$",
            r"$z = e^{i\theta}$",
            r"$R_1 R_2 = R(\theta_1+\theta_2)$",
            r"$\mathrm{SO}(2)$",
            r"$|z| = 1$",
            r"$R^{-1} = R^T$",
            r"$\det R = 1$",
        ],
        "big_symbols": [r"$R$", r"$\theta$", r"$e^{i\theta}$", r"$z$"],
    },
    "3DROTS": {
        "title": "3D Rotation Representations",
        "bg": ("#e8eaf6", "#e0f7fa"),
        "accents": ["#1a237e", "#006064", "#283593", "#00838f", "#304ffe"],
        "formulas": [
            r"$R(\phi_1,\Phi,\phi_2)$",
            r"$\mathbf{q} = q_0 + q_1\mathbf{i} + q_2\mathbf{j} + q_3\mathbf{k}$",
            r"$\mathrm{SO}(3)$",
            r"$|\mathbf{q}| = 1$",
            r"$\omega = 2\arccos(q_0)$",
            r"$\hat{n} = (n_1, n_2, n_3)$",
            r"$\mathbf{p} = \hat{n}\tan(\omega/2)$",
            r"$S^3$",
            r"$(\phi_1, \Phi, \phi_2)$",
        ],
        "big_symbols": [r"$R$", r"$\Phi$", r"$\omega$", r"$\mathbf{q}$"],
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
            r"$(\omega, \hat{n})$",
            r"$\mathrm{FZ}$",
        ],
        "big_symbols": [r"$\Sigma$", r"$\Delta g$", r"$\theta$", r"$\omega$"],
    },
    "LINALG": {
        "title": "Concepts of Linear Algebra",
        "bg": ("#e8eaf6", "#e3f2fd"),
        "accents": ["#1a237e", "#0d47a1", "#283593", "#1565c0", "#304ffe"],
        "formulas": [
            r"$A\mathbf{x} = \mathbf{b}$",
            r"$\det(A - \lambda I) = 0$",
            r"$A^{-1} = \frac{1}{\det A}\,\mathrm{adj}(A)$",
            r"$A\mathbf{v} = \lambda\mathbf{v}$",
            r"$P^{-1}AP = D$",
            r"$\mathrm{rank}(A) = r$",
            r"$\mathrm{tr}(A) = \sum \lambda_i$",
        ],
        "big_symbols": [r"$A$", r"$\lambda$", r"$\det$", r"$\mathbf{v}$"],
    },
    "MATPRP": {
        "title": "What is a Material Property?",
        "bg": ("#f1f8e9", "#e8eaf6"),
        "accents": ["#33691e", "#283593", "#558b2f", "#1a237e", "#689f38"],
        "formulas": [
            r"$T_{ij} = C_{ijkl}\varepsilon_{kl}$",
            r"$\mathbf{F} = m\mathbf{a}$",
            r"$\sigma_{ij}$",
            r"$\varepsilon_{kl}$",
            r"$\kappa_{ij}\nabla_j T$",
            r"$D_{ij}E_j$",
        ],
        "big_symbols": [r"$\sigma$", r"$\varepsilon$", r"$C_{ijkl}$"],
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
        ],
        "big_symbols": [r"$S_V$", r"$V_V$", r"$N_A$", r"$P_L$"],
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
            r"$|\mathbf{p}| \leq 1$",
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
            r"$\mathrm{Neumann}$",
            r"$\mathcal{S} \subseteq \mathcal{G}$",
            r"$n_{ind}$",
        ],
        "big_symbols": [r"$C_{ijkl}$", r"$T_{ij}$", r"$\mathcal{S}$"],
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
            r"$a_{ij}a_{kj} = \delta_{ik}$",
            r"$\mathrm{rank}\,n$",
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
            r"$f(g)$",
            r"$\mathrm{ODF}$",
        ],
        "big_symbols": [r"$\{hkl\}$", r"$f(g)$", r"$\langle uvw\rangle$"],
    },
    "SELPRP": {
        "title": "Selected Anisotropic Material Properties",
        "bg": ("#fce4ec", "#fff3e0"),
        "accents": ["#b71c1c", "#e65100", "#c62828", "#bf360c", "#d50000"],
        "formulas": [
            r"$\sigma_{ij} = C_{ijkl}\varepsilon_{kl}$",
            r"$D_i = \epsilon_{ij}E_j$",
            r"$B_i = \mu_{ij}H_j$",
            r"$d_{ijk}$",
            r"$S_{IJ}$",
            r"$\alpha_{ij}\Delta T$",
        ],
        "big_symbols": [r"$C_{ijkl}$", r"$\sigma$", r"$S_{IJ}$"],
    },
    "TRAPRP": {
        "title": "Selected Transport Properties",
        "bg": ("#e0f7fa", "#f3e5f5"),
        "accents": ["#006064", "#4a148c", "#00838f", "#6a1b9a", "#00acc1"],
        "formulas": [
            r"$J_i = L_{ij}X_j$",
            r"$L_{ij} = L_{ji}$",
            r"$\kappa_{ij}$",
            r"$\sigma_{ij}E_j = J_i$",
            r"$\mathrm{Onsager}$",
            r"$R_{H}$",
            r"$\nabla T$",
        ],
        "big_symbols": [r"$L_{ij}$", r"$J$", r"$\kappa$", r"$\nabla T$"],
    },
    "MISORI": {
        "title": "Misorientations and Disorientations",
        "bg": ("#f3e5f5", "#e1f5fe"),
        "accents": ["#6a1b9a", "#0277bd", "#7b1fa2", "#01579b", "#9c27b0"],
        "formulas": [
            r"$\Delta g = g_B g_A^{-1}$",
            r"$\omega_{dis} = \min(\omega_i)$",
            r"$g' = s_i g s_j^{-1}$",
            r"$\mathrm{MDF}$",
            r"$P(\omega)$",
        ],
        "big_symbols": [r"$\Delta g$", r"$\omega$", r"$\Sigma$"],
    },
}


def _load_figure_as_image(pdf_path: Path) -> "Image.Image | None":
    """Convert a PDF figure to a PIL Image using pdftoppm or sips."""
    if not HAS_PIL:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_path.read_bytes())
            tmp_path = tmp.name
        prefix = tmp_path.replace(".pdf", "")
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", "100", "-singlefile", tmp_path, prefix],
                capture_output=True, check=True, timeout=10,
            )
            png_path = prefix + ".png"
        except FileNotFoundError:
            png_path = tmp_path.replace(".pdf", ".png")
            subprocess.run(
                ["sips", "-s", "format", "png", tmp_path, "--out", png_path],
                capture_output=True, check=True, timeout=10,
            )
        img = Image.open(png_path).convert("RGBA")
        Path(tmp_path).unlink(missing_ok=True)
        Path(png_path).unlink(missing_ok=True)
        return img
    except Exception:
        return None


def generate_header(abbr: str, config: dict, output_path: Path, figure_dir: Path | None = None):
    """Generate a single chapter header image."""
    random.seed(hash(abbr) + 42)  # changed seed for new designs
    np.random.seed((abs(hash(abbr)) + 42) % (2**31))

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

    # Decorative circles in background
    for _ in range(random.randint(5, 12)):
        x, y = random.uniform(0, 1), random.uniform(0, 1)
        r = random.uniform(0.02, 0.12)
        color = random.choice(config["accents"])
        circle = mpatches.Circle((x, y), r, fill=True, color=color,
                                  alpha=random.uniform(0.03, 0.08), zorder=0)
        ax.add_patch(circle)

    # Embed actual figures (blurred, rotated, semi-transparent)
    if figure_dir and HAS_PIL:
        fig_pdfs = [f for f in sorted(figure_dir.glob("*.pdf")) if "header" not in f.name.lower()]
        if fig_pdfs:
            chosen = random.sample(fig_pdfs, min(4, len(fig_pdfs)))
            for fig_pdf in chosen:
                img = _load_figure_as_image(fig_pdf)
                if img is None:
                    continue
                # Resize so it occupies less than a quarter of the header
                max_w, max_h = 2480 // 4, 1240 // 4
                img.thumbnail((max_w, max_h), Image.LANCZOS)
                # Apply Gaussian blur
                img = img.filter(ImageFilter.GaussianBlur(radius=3))
                # Random rotation
                angle = random.uniform(-15, 15)
                img = img.rotate(angle, expand=True, fillcolor=(0, 0, 0, 0))
                # Make semi-transparent
                alpha = img.getchannel("A")
                alpha = alpha.point(lambda p: int(p * random.uniform(0.12, 0.22)))
                img.putalpha(alpha)
                # Random position
                px = random.uniform(0.05, 0.75)
                py = random.uniform(0.05, 0.75)
                extent = [px, px + img.width / 2480, py, py + img.height / 1240]
                ax.imshow(np.array(img), extent=extent, aspect="auto", zorder=1)

    # Large semi-transparent background symbols
    for sym in config.get("big_symbols", []):
        x = random.uniform(0.05, 0.95)
        y = random.uniform(0.1, 0.9)
        size = random.randint(40, 80)
        color = random.choice(config["accents"])
        alpha = random.uniform(0.08, 0.18)
        ax.text(x, y, sym, fontsize=size, ha="center", va="center",
                color=color, alpha=alpha, zorder=2, fontfamily="serif")

    # Scattered formulas
    formulas = config.get("formulas", [])
    positions = []
    for formula in formulas * 2:
        for _ in range(20):
            x = random.uniform(0.02, 0.98)
            y = random.uniform(0.02, 0.98)
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
                color=color, alpha=alpha, rotation=rotation, zorder=3,
                fontfamily="serif")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    with PdfPages(str(output_path)) as pdf:
        pdf.savefig(fig, dpi=DPI, bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    print(f"  Generated: {output_path.name}")


def main():
    import re
    monorepo = Path("/Volumes/Drive2/Files/Books/OC/OpenChapters/src")
    chabbr_re = re.compile(r'\\renewcommand\{\\chabbr\}\{([^}]+)\}')
    skip = {"ChapterTemplate"}

    for cdir in sorted(monorepo.iterdir()):
        if not cdir.is_dir() or cdir.name in skip:
            continue
        # Find chabbr
        abbr = None
        for tex in cdir.glob("*.tex"):
            m = chabbr_re.search(tex.read_text(errors="replace"))
            if m:
                abbr = m.group(1)
                break
        if not abbr or abbr not in CHAPTERS:
            continue

        pdf_dir = cdir / "pdf"
        pdf_dir.mkdir(exist_ok=True)
        output = pdf_dir / f"{abbr}header.pdf"
        fig_dir = pdf_dir if any(f for f in pdf_dir.glob("*.pdf") if "header" not in f.name.lower()) else None
        generate_header(abbr, CHAPTERS[abbr], output, figure_dir=fig_dir)


if __name__ == "__main__":
    main()
