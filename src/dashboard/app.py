"""Streamlit dashboard for viewing property hunt results."""

from __future__ import annotations

import json
import re
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_results() -> str:
    """Load the latest results markdown file."""
    results_file = DATA_DIR / "results.md"
    if results_file.exists():
        return results_file.read_text(encoding="utf-8")
    return ""


def main():
    st.set_page_config(
        page_title="London Property Hunter",
        page_icon="🏠",
        layout="wide",
    )

    st.title("London Property Hunter")
    st.caption("AI-powered property search using Claude Agent SDK + MCP")

    # Sidebar: search config
    with st.sidebar:
        st.header("Search Parameters")
        areas = st.text_input("Areas (comma-separated)", "SE15, SE22, SE5, E8, E5")
        budget = st.number_input("Max Budget (£)", value=600_000, step=25_000)
        min_beds = st.slider("Min Bedrooms", 1, 6, 2)
        commute_to = st.text_input("Commute To", "Kings Cross")
        max_commute = st.slider("Max Commute (mins)", 10, 90, 45)

        if st.button("Run Search", type="primary"):
            import subprocess
            import sys

            area_list = [a.strip() for a in areas.split(",")]
            cmd = [
                sys.executable, "-m", "src.agent.main",
                "--areas", *area_list,
                "--budget", str(budget),
                "--min-beds", str(min_beds),
                "--commute-to", commute_to,
                "--max-commute", str(max_commute),
                "--verbose",
            ]

            with st.spinner("Agent is searching... this may take a few minutes"):
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(DATA_DIR.parent),
                    timeout=600,
                )
                if proc.returncode == 0:
                    st.success("Search complete!")
                else:
                    st.error(f"Agent error:\n{proc.stderr[:500]}")

    # Main area: results
    results = load_results()

    if results:
        st.markdown("---")
        st.markdown(results)

        # Offer downloads
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "Download Results (Markdown)",
                results,
                file_name="property_results.md",
                mime="text/markdown",
            )
        with col2:
            # Check for JSON results too
            json_file = DATA_DIR / "results.json"
            if json_file.exists():
                json_data = json_file.read_text(encoding="utf-8")
                st.download_button(
                    "Download Results (JSON)",
                    json_data,
                    file_name="property_results.json",
                    mime="application/json",
                )
    else:
        st.info(
            "No results yet. Configure your search in the sidebar and click **Run Search**, "
            "or run the agent from the CLI:\n\n"
            "```bash\n"
            "python -m src.agent.main --areas SE15 SE22 --budget 600000 --min-beds 2\n"
            "```"
        )


if __name__ == "__main__":
    main()
