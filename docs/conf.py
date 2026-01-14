# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = 'ionique'
copyright = '2025, Ali Fallahi, Dinara Boyko, Wanunu Lab'
author = 'Ali Fallahi, Dinara Boyko'
import ionique

release = ionique.__version__
version = release

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'myst_parser',
    'sphinx_multiversion',
]

smv_tag_whitelist = r'^v\d+\.\d+(\.\d+)?$'
smv_branch_whitelist = r'^(main|master|feature/dina)$'
smv_remote_whitelist = r'^origin$'


source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

autodoc_mock_imports = ["nbwidgets", "setup_log"]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'sphinx.ext.autodoc', "cparsers*"]
autosummary_generate = True

autodoc_default_options = {
    "special-members": "__init__"
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_sidebars = {
    '**': [

        'globaltoc.html',     # site/page navigation
        'sourcelink.html',    # "View page source"
        'searchbox.html',     # search
        'versions.html',
    ],
}
html_theme_options = {
    'collapse_navigation': False,  # keep sections expanded
    'navigation_depth': 4,         # how deep the TOC goes
    'sticky_navigation': True,     # keep nav visible while scrolling
}
