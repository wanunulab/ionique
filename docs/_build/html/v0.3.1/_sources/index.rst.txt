.. ionique documentation master file, created by
   sphinx-quickstart on Tue Feb 11 10:00:50 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Ionique: A Nanopore Signal Analysis Framework
==========================================

**Authors:**
Ali Fallahi, Dinara Boyko

**Date:**
Feb 11, 2025

**Version:**
0.1.0 (Development)

Overview
--------

Ionique is a Python module for processing and analyzing nanopore signal data. It provides tools for reading, filtering, segmenting, and analyzing nanopore experimental data. The framework supports structured workflows for signal processing and quality control, allowing researchers to extract relevant information from raw current and voltage traces.

Features
--------

- **File Handling**
  - Supports `.edh`, `.opt`, and `.xml` formats.
  - Extracts raw current and voltage traces.
  - Parses experimental metadata for structured analysis.

- **Signal Processing**
  - Segmentation and event detection.


- **Analysis Modules**
  - IV curve computation and voltage pattern detection.
  - Step response and dwell-time analysis.
  - Customizable parsers and filters for flexible workflows.

- **Usability**
  - Python library for scripting and automation.


Installation (Development)
--------------------------

To install the development version of Ionique, clone the repository and install it in editable mode:

.. code-block:: bash

    git clone https://github.com/wanunulab/ionique.git
    cd ionique
    pip install ionique

**Requirements:**
- Python > 3.10
- Dependencies listed in `requirements.txt`

Future Development
------------------

- **Additional analysis modules** for extended event detection and pattern recognition.
- **Integration with Jupyter Notebooks** for interactive visualization.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

   signal_process
   api_reference

.. toctree::
   :maxdepth: 2
   :caption: Guides

   install_beginner.rst
   ionique_starter.md
   python_vscode_start.md


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
