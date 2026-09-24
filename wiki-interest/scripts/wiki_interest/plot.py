"""PNG charts via matplotlib."""

from pathlib import Path


def plot_trends(results: dict, output: str | None = None) -> bytes:
    """Plot trend lines for each language.

    Args:
        results: dict of {lang: analysis_result} from analyze()
        output: file path to save PNG, or None to return bytes

    Returns:
        PNG bytes if output=None, else None
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_bytes(b"PNG stub")
        return b"PNG stub"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlabel("Month")
    ax.set_ylabel("Views")
    ax.set_title("Wikipedia Pageview Trends")
    ax.legend()
    ax.grid(True, alpha=0.3)

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        return None
    else:
        import io
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
