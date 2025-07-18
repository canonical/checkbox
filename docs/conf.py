import datetime
import os
import sys
import re

import checkbox_ng

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Checkbox"
author = "Canonical Group Ltd"
copyright = "%s, %s" % (datetime.date.today().year, author)
# Here we just keep the version number and not any .devhash because that would
#  make the CI/CD spellcheck fail mistaking any .devhash occurence for an
#  unknown word
release = (
    re.match(r"(\d+\.{0,1})+", checkbox_ng.__version__).group(0).rstrip(".")
)

# Open Graph configuration - defines what is displayed in the website preview
ogp_site_url = "https://checkbox.readthedocs-hosted.com/"
ogp_site_name = project
ogp_image = (
    "https://assets.ubuntu.com/v1/253da317-image-document-ubuntudocs.svg"
)

html_context = {
    # Change to the discourse instance you want to be able to link to
    # "discourse": "https://discourse.ubuntu.com",
    # Change to the GitHub info for your project
    "github_url": "https://github.com/canonical/checkbox",
    "github_version": "main",
    "github_folder": "docs",
    "github_filetype": "rst",
}

# Used for related links - no need to change
if "discourse" in html_context:
    html_context["discourse_prefix"] = html_context["discourse"] + "/t/"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "custom-rst-roles",
    "myst_parser",
    "related-links",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_reredirects",
    "sphinx_tabs.tabs",
    "sphinx-jsonschema",
    "sphinxcontrib.mermaid",
    "sphinxext.opengraph",
    "terminal-output",
    "youtube-links",
]

myst_enable_extensions = ["substitution", "deflist"]

myst_enable_extensions = ["substitution", "deflist"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", ".sphinx"]

rst_epilog = """
.. include:: /reuse/links.txt
"""

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# Links to ignore when checking links
linkcheck_ignore = [
    "http://127.0.0.1:8000",
    "https://github.com/canonical/hwcert-jenkins-jobs",
    "https://www.gnu.org/licenses",
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Find the current builder
builder = "dirhtml"
if "-b" in sys.argv:
    builder = sys.argv[sys.argv.index("-b") + 1]

# Setting templates_path for epub makes the build fail
if builder == "dirhtml" or builder == "html":
    templates_path = [".sphinx/_templates"]

html_theme = "furo"
html_last_updated_fmt = ""
html_permalinks_icon = "¶"
html_theme_options = {
    "light_css_variables": {
        "color-sidebar-background-border": "none",
        "font-stack": "Ubuntu, -apple-system, Segoe UI, Roboto, Oxygen, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif",
        "font-stack--monospace": "Ubuntu Mono, Consolas, Monaco, Courier, monospace",
        "color-foreground-primary": "#111",
        "color-foreground-secondary": "var(--color-foreground-primary)",
        "color-foreground-muted": "#333",
        "color-background-secondary": "#FFF",
        "color-background-hover": "#f2f2f2",
        "color-brand-primary": "#111",
        "color-brand-content": "#06C",
        "color-api-background": "#cdcdcd",
        "color-inline-code-background": "rgba(0,0,0,.03)",
        "color-sidebar-link-text": "#111",
        "color-sidebar-item-background--current": "#ebebeb",
        "color-sidebar-item-background--hover": "#f2f2f2",
        "toc-font-size": "var(--font-size--small)",
        "color-admonition-title-background--note": "var(--color-background-primary)",
        "color-admonition-title-background--tip": "var(--color-background-primary)",
        "color-admonition-title-background--important": "var(--color-background-primary)",
        "color-admonition-title-background--caution": "var(--color-background-primary)",
        "color-admonition-title--note": "#24598F",
        "color-admonition-title--tip": "#24598F",
        "color-admonition-title--important": "#C7162B",
        "color-admonition-title--caution": "#F99B11",
        "color-highlighted-background": "#EbEbEb",
        "color-link-underline": "var(--color-background-primary)",
        "color-link-underline--hover": "var(--color-background-primary)",
        "color-version-popup": "#772953",
    },
    "dark_css_variables": {
        "color-foreground-secondary": "var(--color-foreground-primary)",
        "color-foreground-muted": "#CDCDCD",
        "color-background-secondary": "var(--color-background-primary)",
        "color-background-hover": "#666",
        "color-brand-primary": "#fff",
        "color-brand-content": "#06C",
        "color-sidebar-link-text": "#f7f7f7",
        "color-sidebar-item-background--current": "#666",
        "color-sidebar-item-background--hover": "#333",
        "color-admonition-background": "transparent",
        "color-admonition-title-background--note": "var(--color-background-primary)",
        "color-admonition-title-background--tip": "var(--color-background-primary)",
        "color-admonition-title-background--important": "var(--color-background-primary)",
        "color-admonition-title-background--caution": "var(--color-background-primary)",
        "color-admonition-title--note": "#24598F",
        "color-admonition-title--tip": "#24598F",
        "color-admonition-title--important": "#C7162B",
        "color-admonition-title--caution": "#F99B11",
        "color-highlighted-background": "#666",
        "color-link-underline": "var(--color-background-primary)",
        "color-link-underline--hover": "var(--color-background-primary)",
        "color-version-popup": "#F29879",
    },
}

html_static_path = [".sphinx/_static"]
html_css_files = [
    "checkbox-doc.css",
    "custom.css",
    "github_issue_links.css",
]
html_js_files = [
    "github_issue_links.js",
]


# Set up redirects (https://documatt.gitlab.io/sphinx-reredirects/usage.html)
# For example: "explanation/old-name.html": "../how-to/prettify.html",
redirects = {}
