Installation for beginners
===========================

Welcome to Ionique!
------------------

This tutorial is designed for non-coding users. If you have used Python and GitHub before, please proceed with the ``README.md`` instructions.

Before diving into data analysis, let's first install Python, GitHub, and Jupyter Notebook.

Step 1: Install Python
-----------------------

Download the package from `Python Downloads <https://www.python.org/downloads/>`_.

Choose the appropriate OS system for your machine. Then, scroll down to pick Python version **3.10** or later up to **3.12**.

After Python has been successfully installed, we can go over some basic terminal commands.

**Linux Users:**
  - In the search window, type **"shell"** or use the hotkey **Ctrl-Alt-T**.

**MacOS Users:**
  - In the search window, type **"Terminal"**.

**Windows Users:**
  - In the search window, type **"Terminal"**.

To check the installation, type:

.. code-block:: sh

   python -V

Some versions of Python may require the following command:

.. code-block:: sh

   python3 -V


Step 2: GitHub
--------------

First, you need to create an account by following the instructions on `GitHub <https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github>`_.

Now, open the repository link: `Ionique Repository <https://github.com/wanunulab/ionique>`_, click on the green **"Code"** button, and download the ZIP file. Unzip it.

Move the folder to the desired location on your computer.

Step 3: Moving Between Folders in the Terminal
----------------------------------------------

You can find a short list of basic commands here: `Linux vs Windows Commands <https://www.geeksforgeeks.org/linux-vs-windows-commands/>`_.

Check your current location using:

  - **pwd** (Unix, Linux, Mac)
  - **cd** (Windows)

To list items in the current directory:

  - **ls** (Unix, Linux, Mac)
  - **chdir** (Windows)

The most important command for this tutorial is **cd**, which stands for "change directory." To move around folders in the terminal, type:

.. code-block:: sh

   cd directory_name

Find the **ionique** folder and move inside it.

Step 4: Virtual Environment
---------------------------

A virtual environment is an encapsulated workspace on your computer that allows you to install software packages for a project. It helps to keep the versions of different packages within a project completely separate from other projects.

To learn more about virtual environments, visit `Python Virtual Environments <https://docs.python.org/3/tutorial/venv.html>`_.

Let's create your first virtual environment!

Run the following command:

.. code-block:: sh

   python -m venv ionique_env

Then, activate it:

.. code-block:: sh

   source ionique_env/bin/activate   # Linux/MacOS
   ionique_env\Scripts\activate.bat  # Windows

Now, install the Ionique requirements:

.. code-block:: sh

   pip install .

*If your OS and Python version require the ``python3`` command, use ``pip3`` instead.*

Next, install JupyterLab:

.. code-block:: sh

   pip install jupyterlab

Step 5: Run the Notebooks
-------------------------

Copy the notebook you want to run into the **data** folder. (You don’t need to use the terminal for this step.)

Now, return to the terminal window and navigate to the folder where the copied notebook is stored.

Then, run:

.. code-block:: sh

   jupyter lab

You are now ready to work on data analysis!

Step 6: Finish Workflow
-----------------------

Once you are done with the analysis, go back to the terminal and press **Ctrl + C**.

Then, type:

.. code-block:: sh

   deactivate

to deactivate the virtual environment.

**Note:** Starting from **Step 5**, the procedure will be identical each time you want to run **Ionique**.

Happy using Ionique!
