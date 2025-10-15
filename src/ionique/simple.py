#!/usr/bin/env python
"""
Module ionique.simple
GUI and Jupyter convinience functions to streamline work for basic users
"""
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

def panel_load_opt_files(path="~",pattern="*.opt",title= "OPT Files and Parameters"):
    return _panel_load_files(on_run=_panel_load_opt_callback,path=path,pattern=pattern,title=title)

def panel_load_edh_files(path="~",pattern="*.edh",title= "EDH Files and Parameters"):
    print("not implemented yet")
    pass 

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
            status.object = "Done."
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
