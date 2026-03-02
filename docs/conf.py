# Configuration file for the Sphinx documentation builder.

project = 'ionique'
copyright = '2025, Ali Fallahi, Dinara Boyko, Wanunu Lab'
author = 'Ali Fallahi, Dinara Boyko'
from importlib.metadata import version as _get_version

release = _get_version('ionique')
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx_copybutton',
    'myst_parser',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

autodoc_mock_imports = ["nbwidgets", "setup_log", "panel", "bokeh"]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'sphinx.ext.autodoc', "cparsers*"]
autosummary_generate = True

autodoc_default_options = {
    "special-members": "__init__"
}

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/', None),
}

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_sidebars = {
    '**': [
        'globaltoc.html',
        'sourcelink.html',
        'searchbox.html',
    ],
}
html_theme_options = {
    'collapse_navigation': False,
    'navigation_depth': 4,
    'sticky_navigation': True,
}
