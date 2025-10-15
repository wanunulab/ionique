#!/usr/bin/env python
"""
Module ionique.simple
GUI and Jupyter convinience functions to streamline work for basic users
"""
import os
from pathlib import Path
pn_init=False
pn=None
def _init_panel():
    global pn
    global pn_init
    if pn is None or not pn_init:
        import panel 
        pn=panel 
        pn.extension("plotly")
        pn_init=True
    return

def panel_load_opt_files(path="~",pattern="*[0-9].opt",title= "OPT Files and Parameters"):
    return _panel_load_files(on_run=_panel_load_opt_callback,path=path,pattern=pattern,title=title)

def panel_load_edh_files(path="~",pattern="*.edh",title= "EDH Files and Parameters"):
    print("not implemented yet")
    pass 
def panel_parser_AutoSquare():
    """
    Build a Panel UI to configure and run AutoSquareParser on `session`.
    Hard-coded:
      - rules=[lambda event: event.duration > 4]
      - newrank="event", at_child_rank="vstepgap"
    """
    
    from ionique.datatypes import SessionFileManager
    
    from ionique.parsers import AutoSquareParser
    session=SessionFileManager()
    _init_panel()
    # Widgets for numeric params
    threshold_baseline = pn.widgets.FloatInput(name="Threshold Baseline (fractional)", value=0.7, step=0.01)
    expected_conductance = pn.widgets.FloatInput(name="Expected Conductance (nS)", value=2.0, step=0.1)
    conductance_tolerance = pn.widgets.FloatInput(name="Conductance Tolerance (factor)", value=1.15, step=0.01)
    wrap_padding = pn.widgets.IntInput(name="Samples to pad", value=50, step=1)

    # Preview + status
    parser_preview = pn.pane.Str("", sizing_mode="stretch_width")
    status = pn.pane.Markdown("", sizing_mode="stretch_width")

    def _build_parser():
        return AutoSquareParser(
            threshold_baseline=threshold_baseline.value,
            expected_conductance=expected_conductance.value,
            conductance_tolerance=conductance_tolerance.value,
            wrap_padding=wrap_padding.value,
            rules=[lambda event: event.duration > 4],  # hard-coded “funky” param
        )

    def _update_preview(event=None):
        try:
            parser_preview.object = repr(_build_parser())
        except Exception as e:
            parser_preview.object = f"Error building parser: {e}"

    for w in (threshold_baseline, expected_conductance, conductance_tolerance, wrap_padding):
        w.param.watch(_update_preview, "value")

    _update_preview()

    run_btn = pn.widgets.Button(name="Run parse (newrank='event' at 'vstepgap')", button_type="primary")
    def _run(event):
        try:
            status.object = "Running..."
            parser = _build_parser()
            session.parse(parser, newrank="event", at_child_rank="vstepgap")
            status.object = "✅ Parse complete: newrank **event** at **vstepgap**"
        except Exception as e:
            status.object = f"❌ Parse failed: `{e}`"

    run_btn.on_click(_run)

    return pn.Card(
        pn.Row(threshold_baseline, expected_conductance, conductance_tolerance, wrap_padding),
        pn.Column("**Parser preview**", parser_preview),
        run_btn,
        status,
        title="AutoSquareParser",
        collapsible=True,
        sizing_mode="stretch_width",
    )


def panel_parser_SpeedyStatSplit():
    """
    Build a Panel UI to configure and run SpeedyStatSplit on `session`.
    Hard-coded:
      - sampling_freq = session.children[0].metadata["eff_sampling_freq"]
      - newrank="subevent", at_child_rank="event"
    """
    from ionique.datatypes import SessionFileManager
    from ionique.parsers import SpeedyStatSplit
    session=SessionFileManager()
    
    # Numeric widgets
    cutoff_frequency = pn.widgets.FloatInput(name="Cutoff Frequency (must match loading filter)", value=25000, step=1.0)
    window_width = pn.widgets.IntInput(name="Window Width (samples)", value=500, step=5)
    min_width = pn.widgets.IntInput(name="Minimum Width (samples)", value=5, step=1)
    false_positive_rate = pn.widgets.IntInput(name="False Positive Rate (segments per second)", value=5000, step=100)
    # prior_segments_per_second = pn.widgets.IntInput(name="Prior (segments per second)", value=8000, step=500)

    # Hard-coded sampling frequency (not editable), but shown to user
    try:
        sampling_freq_val = session.children[0].metadata["eff_sampling_freq"]
    except Exception:
        sampling_freq_val = None  # will surface in preview and run if missing

    sampling_info = pn.pane.Markdown(
        f"**sampling_freq** (derived from files): `{sampling_freq_val}`",
        sizing_mode="stretch_width"
    )

    parser_preview = pn.pane.Str("", sizing_mode="stretch_width")
    status = pn.pane.Markdown("", sizing_mode="stretch_width")

    def _build_parser():
        if sampling_freq_val is None:
            raise RuntimeError("Could not resolve session.children[0].metadata['eff_sampling_freq']")
        return SpeedyStatSplit(
            cutoff_freq=cutoff_frequency.value,
            window_width=window_width.value,
            min_width=min_width.value,
            sampling_freq=sampling_freq_val,  # hard-coded “funky” param
            false_positive_rate=false_positive_rate.value,
            # prior_segments_per_second=prior_segments_per_second.value,
        )

    def _update_preview(event=None):
        try:
            parser_preview.object = repr(_build_parser())
        except Exception as e:
            parser_preview.object = f"Error building parser: {e}"

    for w in (cutoff_frequency, window_width, min_width, false_positive_rate):#, prior_segments_per_second):
        w.param.watch(_update_preview, "value")

    _update_preview()

    run_btn = pn.widgets.Button(name="Run parse (newrank='subevent' at 'event')", button_type="primary")
    def _run(event):
        try:
            status.object = "Running..."
            parser = _build_parser()
            session.parse(parser=parser, newrank="subevent", at_child_rank="event")
            status.object = "✅ Parse complete: newrank **subevent** at **event**"
        except Exception as e:
            status.object = f"❌ Parse failed: `{e}`"

    run_btn.on_click(_run)

    return pn.Card(
        pn.Row(cutoff_frequency, window_width),
        pn.Row(min_width,false_positive_rate),#, prior_segments_per_second),
        sampling_info,
        pn.Column("**Parser preview**", parser_preview),
        run_btn,
        status,
        title="SpeedyStatSplit",
        collapsible=True,
        sizing_mode="stretch_width",
    )
    
def get_standard_features():
    """
    Extract standard features from the current session's open files. Also stores the dataframe in session.latest_dataframe.

    :return: df
    :rtype: pandas.DataFrame
    """
    from ionique.datatypes import SessionFileManager
    from ionique.utils import extract_features
    import numpy as np
    session=SessionFileManager()
    if "subevent" in session.summary().keys():
        df=extract_features(session, bottom_rank="event",
            extractions=['mean', 'std','frac', 'duration', 'current', 'wrap', 'start'],
            # add_ons={#"sample_type": trace_file.unique_features['sample_type'],
            #     ,
            #     # "concentration": trace_file.unique_features["concentration"]},
            # },
            lambdas={ "filename": lambda event: event.get_feature('metadata')["HeaderFile"],
                     "baseline": lambda event: np.abs(event.unique_features["baseline"])*(-1 if event.get_feature("voltage")<0.00001 else 1),
                "Voltage": lambda event: int(1000 * round(float(event.get_feature("voltage")), 3)),
                "baseline_conductance":lambda event:np.abs(event.unique_features["baseline"]/event.get_feature("voltage")),
                "start_time": lambda event: event.time[0],
                "parent_start_time":lambda event: event.parent.time[0],
                "subevent_starts": lambda event: np.array([subevent.start-event.start for subevent in event.children]),
                "subevent_ends": lambda event: np.array([subevent.end-event.start for subevent in event.children]),
                "subevent_mean": lambda event: np.array([subevent.mean for subevent in event.children]),
                "subevent_std": lambda event: np.array([subevent.std for subevent in event.children]),
                "subevent_duration": lambda event: np.array([subevent.duration for subevent in event.children]),
                "subevent_count":lambda event:len(event.children)
            })
    else:
        df=extract_features(session, bottom_rank="event",
            extractions=['mean', 'std','frac', 'duration', 'current', 'wrap', 'start'],
            # add_ons={#"sample_type": trace_file.unique_features['sample_type'],
            #     "filename": trace_file.metadata["HeaderFile"],
            #     # "concentration": trace_file.unique_features["concentration"]},
            # },
            lambdas={ "filename": lambda event: event.get_feature('metadata')["HeaderFile"],
                     "baseline": lambda event: np.abs(event.unique_features["baseline"])*(-1 if event.get_feature("voltage")<0.00001 else 1),
                "Voltage": lambda event: int(1000 * round(float(event.get_feature("voltage")), 3)),
                "baseline_conductance":lambda event:np.abs(event.unique_features["baseline"]/event.get_feature("voltage")),
                "start_time": lambda event: event.time[0],
                "parent_start_time":lambda event: event.parent.time[0],
            })
    session.latest_dataframe=df
    return df

import pandas as pd
def detect_array_columns(df: pd.DataFrame):
    """Return list of columns that contain at least one numpy.ndarray value."""
    import numpy as np
    cols = []
    for col in df.columns:
        s = df[col]
        if s.dropna().map(lambda x: isinstance(x, np.ndarray)).any():
            cols.append(col)
    return cols



def panel_save_dataframe(
    df: pd.DataFrame=None,
    start_dir: str = ".",
    default_name: str = f"dataset.pkl" # e.g. "2025-10-15_09-42"
,
):
    """
    A Panel UI that:
      • Lets you browse the filesystem with FileSelector
      • Uses the currently viewed path (or a selected folder) as the save directory
      • Saves .pkl / .csv / .xlsx accordingly
      • Drops array columns for CSV
      • Accepts the common typo .xslx -> .xlsx
    """
    
    name,ext = os.path.splitext(default_name)
    from datetime import datetime
    default_name=f'{name}_{datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M")}{ext}'

    from ionique.datatypes import SessionFileManager
    session=SessionFileManager()
    # --- Directory explorer ---
    if df is None:
        if hasattr(session,"latest_dataframe"):
            df=session.latest_dataframe
        else:
            raise ValueError("No dataframe containing features was provided or found.")
    _init_panel()
    explorer = pn.widgets.FileSelector(
        directory=str(Path(start_dir).expanduser()),
        only_files=False,          # allow selecting folders too
        file_pattern="*",
        size=12,
        name="Browse to a folder (you can also select one)"
    )

    # --- Inputs ---
    name_input = pn.widgets.TextInput(name="Filename", value=default_name)
    overwrite = pn.widgets.Checkbox(name="Overwrite if file exists", value=False)
    save_btn = pn.widgets.Button(name="Save", button_type="primary")
    status = pn.pane.Markdown("")
    chosen_dir_md = pn.pane.Markdown("", sizing_mode="stretch_width")

    # Track the "chosen directory"
    #  - If user selects a folder, use it.
    #  - If user selects files, use their parent.
    #  - If nothing selected, use the explorer's current path.
    def _compute_directory():
        sels = explorer.value or []  # list of selected paths (strings)
        if len(sels) == 1 and Path(sels[0]).is_dir():
            return Path(sels[0]).expanduser().resolve()
        elif len(sels) >= 1:
            # if files/folders mixed or multiple files => use parent of first
            return Path(sels[0]).expanduser().resolve().parent
        else:
            # nothing selected: use the currently viewed path
            return Path(explorer.directory).expanduser().resolve()

    def _update_chosen_dir_md(event=None):
        d = _compute_directory()
        chosen_dir_md.object = f"**Save directory:** `{d}`"

    # Update label whenever selection or path changes
    explorer.param.watch(lambda *_: _update_chosen_dir_md(), "value")
    explorer.param.watch(lambda *_: _update_chosen_dir_md(), "directory")
    _update_chosen_dir_md()

    def _save(_):
        status.object = "Saving..."
        try:
            directory = _compute_directory()
            filename = name_input.value.strip()

            if not filename:
                status.object = "❌ Please provide a filename (e.g., `data.xlsx`)."
                return

            # Normalize extension (fix common typo)
            suffix = Path(filename).suffix.lower()
            if suffix == ".xslx":
                filename = Path(filename).with_suffix(".xlsx").name
                suffix = ".xlsx"

            if suffix not in {".pkl", ".csv", ".xlsx"}:
                status.object = "❌ Filename must end with .pkl, .csv, or .xlsx."
                return

            directory.mkdir(parents=True, exist_ok=True)
            path = directory / filename

            if path.exists() and not overwrite.value:
                status.object = f"⚠️ File exists: `{path}`. Enable 'Overwrite' to replace it."
                return

            # Perform the save
            if suffix == ".pkl":
                df.to_pickle(path)
                status.object = f"✅ Saved pickle to `{path}`."
            elif suffix == ".csv":
                array_cols = detect_array_columns(df)
                out = df.drop(columns=array_cols) if array_cols else df
                out.to_csv(path, index=False)
                dropped = f" Dropped array columns: {array_cols}." if array_cols else " No array columns detected."
                status.object = f"✅ Saved CSV to `{path}`.{dropped}"
            else:  # .xlsx
                df.to_excel(path, index=False)  # requires openpyxl
                status.object = f"✅ Saved Excel to `{path}`."

        except Exception as e:
            status.object = f"❌ Error: `{type(e).__name__}: {e}`"

    save_btn.on_click(_save)

    # Optional: quick preview of which columns would be dropped for CSV
    def _array_cols_preview():
        cols = detect_array_columns(df)
        return "Array columns (will be dropped for CSV): " + (", ".join(map(str, cols)) if cols else "(none)")
    array_cols_md = pn.pane.Markdown(_array_cols_preview())

    return pn.Card(
        pn.Column(
            explorer,
            chosen_dir_md,
            pn.Row(name_input, overwrite, save_btn),
            array_cols_md,
            status,
        ),
        title="Save DataFrame",
        collapsible=False,
    )

def _panel_load_files(
    on_run,
    path="~",
    pattern="",
    title="File & Parameters",
):
    """
    Build a single Panel unit (FileSelector + parameter form) and wire a run callback.

    Parameters
    ----------
    on_run : callable
        Function called when the run button is clicked.
        Signature:
            on_run(
                file: str | None,
                voltage_compress: bool,
                filter_at_all:bool,
                downsample: int,
                cutoff_frequency: int,
                sampling_frequency: int,
                filter_type: str,
                filter_method: str,
                order: int,
                bidirectional: bool,
                samples_remove: int,
            ) -> Optional[panel.Viewable | str | dict]
        The return value (if any) is rendered in the output area.
    """
    _init_panel()
    import ionique.io as iqio
    from types import SimpleNamespace
    if pattern == "":
        raise ValueError("File pattern is undefined.")
    else:
        extension=pattern.split(".")[-1]
        if not extension:
            raise ValueError(f"File extension not specified in pattern: {pattern}")
        if "."+extension.lower().strip() not in iqio.supported_extensions:
            raise ValueError(f"Unsupported file extension. ionique currently supports {iqio.supported_extensions}")
        
    if not callable(on_run):
        raise TypeError("on_run must be a callable")

    # --- Widgets ---
    file_browser = pn.widgets.FileSelector(directory=path, file_pattern=pattern)

    voltage_compress_checkbox = pn.widgets.Checkbox(name="Voltage Compress", value=True)
    filter_at_all_checkbox=pn.widgets.Checkbox(name="Filter the signal?", value=True)
    cutoff_frequency = pn.widgets.FloatInput(name="Cutoff Frequency (Hz)", value=25_000,step=1000)
    sampling_frequency = pn.widgets.IntInput(name="Sampling Frequency (Hz)", value=250_000)
    filter_type = pn.widgets.Select(name="Filter type", options=["lowpass", "highpass", "bandpass", "bandstop"])
    filter_method = pn.widgets.Select(name="Filter method", options=["bessel", "butter"])
    order = pn.widgets.IntInput(name="Order", value=2, step=1, start=1,end=16)
    direction = pn.widgets.Checkbox(name="Bidirectional", value=True)
    
    downsample_input = pn.widgets.IntInput(name="Downsample (post-filter)", value=5, step=1, start=1)
    samples_remove = pn.widgets.IntInput(name="Samples to Remove (post-downsample)", value=2000)
    run_button = pn.widgets.Button(name="Run", button_type="primary")
    # Output/status area
    status = pn.pane.Alert("Ready.", alert_type="light", sizing_mode="stretch_width")
    output_area = pn.Column()

    form_2 = pn.Column(
        pn.pane.Markdown("### Parameters for Preprocessing Data"),
        voltage_compress_checkbox,
        filter_at_all_checkbox,
        cutoff_frequency,
        sampling_frequency,
        filter_type,
        filter_method,
        order,
        direction,
        downsample_input,
        samples_remove,
    
        run_button,
        status,
        sizing_mode="stretch_width",
    )

    unit = pn.Card(
        pn.Row(
            pn.Column(pn.pane.Markdown("### Select files"), file_browser, sizing_mode="stretch_both"),
            pn.Spacer(width=20),
            pn.Column(form_2, output_area, sizing_mode="stretch_both"),
        ),
        title=title,
        collapsible=False,
        sizing_mode="stretch_width",
    )

    # --- Click callback wiring ---
    def _on_click(event):
        # Grab current values
        selected_files = list(file_browser.value or [])
        # file = str(Path(selected_files[0]).expanduser()) if selected_files else None

        params = dict(
            files=selected_files,
            voltage_compress=bool(voltage_compress_checkbox.value),
            filter_at_all=bool(filter_at_all_checkbox.value),
            downsample=int(downsample_input.value),
            cutoff_frequency=float(cutoff_frequency.value),
            sampling_frequency=int(sampling_frequency.value),
            filter_type=str(filter_type.value),
            filter_method=str(filter_method.value),
            order=int(order.value),
            bidirectional=bool(direction.value),
            samples_remove=int(samples_remove.value),
        )

        # Basic validation example
        if selected_files is []:
            status.object = "Please select a valid data file."
            status.alert_type = "warning"
            return

        # Run user callback
        run_button.disabled = True
        status.object = "Running..."
        status.alert_type = "info"
        try:
            result = on_run(**params)
        except Exception as e:
            status.object = f"""Error: {e}""" 
            status.alert_type = "danger"
            output_area.objects = []
        else:
            status.object = f"""Done. Loaded {len(params['files'])} file(s).\n {' \n'.join(params["files"])}"""
            status.alert_type = "success"
            # Render result if provided
            if result is None:
                output_area.objects = []
            elif isinstance(result, pn.viewable.Viewable):
                output_area.objects = [result]
            else:
                # Fallback: show text/JSON-ish results
                output_area.objects = [pn.pane.Str(result, sizing_mode="stretch_width")]
        finally:
            run_button.disabled = False

    run_button.on_click(_on_click)

    widgets = SimpleNamespace(
        file_browser=file_browser,
        voltage_compress_checkbox=voltage_compress_checkbox,
        downsample_input=downsample_input,
        cutoff_frequency=cutoff_frequency,
        sampling_frequency=sampling_frequency,
        filter_type=filter_type,
        filter_method=filter_method,
        order=order,
        direction=direction,
        samples_remove=samples_remove,
        run_button=run_button,
        status=status,
        output_area=output_area,
        form=form_2,
        unit=unit,
    )
    return unit

def _panel_load_opt_callback(**params):
    from ionique.utils import Filter,Trimmer
    if not params["files"]:
        raise ValueError ("No files selected")
    if params["filter_at_all"]:
        filt=Filter(
            cutoff_frequency=params["cutoff_frequency"],
            filter_type=params["filter_type"],
            filter_method=params["filter_method"],
            order=params["order"],
            bidirectional=params["bidirectional"],
            sampling_frequency=params["sampling_frequency"])
    else:
        filt=None
    from ionique.io import OPTReader
    from ionique.datatypes import SessionFileManager,TraceFile
    sfm=SessionFileManager()
    trimmer=Trimmer(samples_to_remove=params["samples_remove"],rank="vstep",newrank="vstepgap")
    for fname in params["files"]:
        metadata,current,voltage=OPTReader(
            fname,
            voltage_compress=params["voltage_compress"],
            downsample=params["downsample"],
            )
        trace_file = TraceFile(
            current=current,
            voltage=voltage,
            parent=sfm,
            metadata=metadata,
            unique_features={
                "sampling_freq": metadata["eff_sampling_freq"],
                "eff_sampling_freq": metadata["eff_sampling_freq"]})
        trimmer(trace_file)

def select_files_GUI():
    """
    Open a file dialog allowing multiple selection, but only for ONE file type at a time.
    Users can switch the dialog's file-type dropdown, but the final selection must be
    homogeneous (all the same extension) and in the allowed list.
    
    
    Returns
    -------
    tuple[str, ...]
        Absolute paths of the selected files (empty tuple if the user cancels).
    """

    from tkinter import Tk, filedialog, messagebox
    import os
    from ionique.io import supported_extensions
    # Normalize & dedupe extensions (lowercase, ensure leading dot)
    norm = []
    seen = set()
    for ext in supported_extensions:
        e = ext.strip().lower()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        if e not in seen:
            norm.append(e)
            seen.add(e)

    filetypes = [(f"{e.upper()} (*{e})", f"*{e}") for e in norm]

    root = Tk()
    root.withdraw()

    try:
        paths = filedialog.askopenfilenames(
            title="Select Data File(s)",
            filetypes=filetypes,
            multiple=True
        )
        if not paths:
            root.destroy()
            return tuple()  # canceled

        root.destroy()
        return tuple(paths)


    finally:
        root.destroy()


def load_files_GUI():
    """
    Create a form with:
      - 'Compress voltage (only uncheck if voltage is not stepwise, e.g., triangle wave)' : checkbox
      - 'Apply Filter?' : checkbox
      - If 'Apply Filter?' checked: dynamic form from the Filter dataclass (types, options, limits).
    Returns (frame, get_values) where get_values() -> dict with:
      {'compress_voltage': bool, 'apply_filter': bool, 'filter': Filter|None}
    """
    import tkinter as tk
    from tkinter import ttk, messagebox
    from ionique.utils import Filter
    from dataclasses import dataclass, field, fields, MISSING
    from typing import Literal, Optional, get_origin, get_args, Union
    """
    Open a modal Tk dialog with:
      - 'Compress voltage (only uncheck if voltage is not stepwise, e.g., triangle wave)' checkbox
      - 'Apply Filter?' checkbox
      - If checked, a dynamic 'Filter' section derived from the Filter dataclass
    Returns a dict:
      {
        "compress_voltage": bool,
        "apply_filter": bool,
        "filter": Filter | None
      }
    or None if canceled.
    The window closes after Run or Cancel.
    """
    # Create an isolated Tk root for use outside Tk apps (e.g., Jupyter)
    root = tk.Tk()
    # root.withdraw()
    root.geometry("560x460")
    dlg = tk.Toplevel(root)
    
    dlg.title("Choose loading parameters and run")
    dlg.geometry("560x460")
    dlg.transient(root)
    dlg.grab_set()  # modal

    style = ttk.Style(dlg)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    container = ttk.Frame(dlg, padding=10)
    container.pack(fill="both", expand=True)
    container.grid_columnconfigure(1, weight=1)

    # Top checkboxes
    compress_var = tk.BooleanVar(value=True)
    apply_filter_var = tk.BooleanVar(value=False)

    ttk.Checkbutton(
        container,
        text="Compress voltage (only uncheck if voltage is not stepwise, e.g., triangle wave)",
        variable=compress_var
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

    ttk.Checkbutton(
        container, text="Apply Filter?", variable=apply_filter_var
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

    # Filter section
    
    filter_section = ttk.LabelFrame(container, text="Filter", padding=10)
    filter_section.grid(row=2, column=0, columnspan=3, sticky="ew")
    filter_section.grid_columnconfigure(1, weight=1)
    def validate_pos_int(text):
        if text.strip() == "":
            return True  # allow empty while typing
        return text.isdigit() and int(text) > 0


    vcmd_posint = (container.register(validate_pos_int), "%P")
    downsample_var = tk.StringVar(value="1")
    ttk.Label(container, text="Downsample rate:").grid(row=3, column=0, sticky="w", padx=(0, 8))
    ttk.Entry(container, textvariable=downsample_var, validate="key", validatecommand=vcmd_posint)\
        .grid(row=3, column=1, sticky="ew", pady=(0, 8))
    def is_literal(t): return get_origin(t) is Literal
    def is_optional_float(t): return get_origin(t) is Union and float in get_args(t) and type(None) in get_args(t)

    # Validators
    def validate_float(text):
        if text.strip() == "" or text.strip().lower() == "none": return True
        try: float(text); return True
        except ValueError: return False

    def validate_int(text):
        if text.strip() == "": return True
        try: int(text); return True
        except ValueError: return False
    

    vcmd_float = (container.register(validate_float), "%P")
    vcmd_int = (container.register(validate_int), "%P")
    
    widgets = {}
    row = 0
    for f in fields(Filter):
        ttk.Label(filter_section, text=f"{f.name.replace('_',' ').title()}:")\
            .grid(row=row, column=0, sticky="w", padx=(0,8), pady=4)

        ann = f.type
        if is_literal(ann):
            choices = list(get_args(ann))
            default = (f.default if f.default is not MISSING else choices[0])
            var = tk.StringVar(value=default)
            w = ttk.Combobox(filter_section, textvariable=var, values=choices, state="readonly")
            w.grid(row=row, column=1, sticky="ew", pady=4)
            widgets[f.name] = (var, w)

        elif ann is bool:
            default = (f.default if f.default is not MISSING else False)
            var = tk.BooleanVar(value=bool(default))
            w = ttk.Checkbutton(filter_section, variable=var)
            w.grid(row=row, column=1, sticky="w", pady=4)
            widgets[f.name] = (var, w)

        elif ann is int:
            default = (f.default if f.default is not MISSING else 0)
            var = tk.StringVar(value=str(default))
            w = ttk.Entry(filter_section, textvariable=var, validate="key", validatecommand=vcmd_int)
            w.grid(row=row, column=1, sticky="ew", pady=4)
            widgets[f.name] = (var, w)
            mn = f.metadata.get("min") if f.metadata else None
            mx = f.metadata.get("max") if f.metadata else None
            if mn is not None or mx is not None:
                ttk.Label(filter_section, text=f"({mn if mn is not None else ''}–{mx if mx is not None else ''})")\
                    .grid(row=row, column=2, sticky="w")

        elif ann is float or is_optional_float(ann):
            default = (None if f.default is MISSING else f.default)
            var = tk.StringVar(value="" if default is None else str(default))
            w = ttk.Entry(filter_section, textvariable=var, validate="key", validatecommand=vcmd_float)
            w.grid(row=row, column=1, sticky="ew", pady=4)
            widgets[f.name] = (var, w)

        else:
            default = ("" if f.default is MISSING else f.default)
            var = tk.StringVar(value=str(default) if default is not None else "")
            w = ttk.Entry(filter_section, textvariable=var)
            w.grid(row=row, column=1, sticky="ew", pady=4)
            widgets[f.name] = (var, w)

        row += 1

    def set_filter_state(*_):
        state = "normal" if apply_filter_var.get() else "disabled"
        for child in filter_section.winfo_children():
            try: child.configure(state=state)
            except tk.TclError: pass
    apply_filter_var.trace_add("write", set_filter_state)
    set_filter_state()

    # Buttons
    btns = ttk.Frame(container); btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12,0))
    result = {"value": None}

    def collect_values():
        apply_filter = apply_filter_var.get()
        compress = compress_var.get()
        filt_obj = None
        if apply_filter:
            kwargs, errors = {}, []
            for f in fields(Filter):
                var, _ = widgets[f.name]; val = var.get(); ann = f.type
                if is_literal(ann):
                    kwargs[f.name] = val
                elif ann is bool:
                    kwargs[f.name] = bool(var.get())
                elif ann is int:
                    try: iv = int(val)
                    except ValueError: errors.append(f"'{f.name}' must be an integer."); continue
                    mn = f.metadata.get("min") if f.metadata else None
                    mx = f.metadata.get("max") if f.metadata else None
                    if mn is not None and iv < mn: errors.append(f"'{f.name}' must be ≥ {mn}.")
                    if mx is not None and iv > mx: errors.append(f"'{f.name}' must be ≤ {mx}.")
                    kwargs[f.name] = iv
                elif ann is float or is_optional_float(ann):
                    txt = str(val).strip()
                    if txt == "" or txt.lower() == "none":
                        kwargs[f.name] = None
                    else:
                        try: kwargs[f.name] = float(txt)
                        except ValueError: errors.append(f"'{f.name}' must be a number.")
                else:
                    kwargs[f.name] = val
            if errors:
                messagebox.showerror("Invalid input", "\n".join(errors), parent=dlg)
                return None
            try:
                filt_obj = Filter(**kwargs)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create Filter: {e}", parent=dlg)
                return None
        return {"voltage_compress": compress, "apply_filter": apply_filter, "filter": filt_obj}

    def on_run():
        vals = collect_values()
        if vals is None: return
        result["value"] = vals
        dlg.destroy()
        root.destroy()

    def on_cancel():
        result["value"] = None
        dlg.destroy()
        root.destroy()

    ttk.Button(btns, text="Cancel", command=on_cancel).pack(side="right", padx=(0,8))
    ttk.Button(btns, text="Run", command=on_run).pack(side="right")

    dlg.bind("<Return>", lambda e: on_run())
    dlg.bind("<Escape>", lambda e: on_cancel())

    # Center dialog
    dlg.update_idletasks()
    req_w = max(dlg.winfo_reqwidth(), 560)   # floor width
    req_h = max(dlg.winfo_reqheight(), 460)  # floor height
    dlg.geometry(f"{req_w}x{req_h}")

    # Give it a reasonable minimum so it doesn't collapse to 0x0
    dlg.minsize(480, 360)
    
    try:
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        x = (sw - req_w) // 2
        y = (sh - req_h) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

    # Make sure it’s visible and on top (even on macOS/Windows)
    dlg.deiconify()
    dlg.state("normal")
    dlg.lift()
    # dlg.focus_force()
    # dlg.attributes("-topmost", True)
    # dlg.after(250, lambda: dlg.attributes("-topmost", False)) 
    # dlg.update_idletasks()
    # Block this call until the dialog is closed, without calling mainloop()
    root.wait_window()
    return result["value"]
