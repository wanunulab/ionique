#!/usr/bin/env python
"""
Module ionique.simple
GUI and Jupyter convinience functions to streamline work for basic users
"""

import panel as pn

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

############################
# Panel functions
############################


def panel_select_file(directory:str="~", file_pattern:str="opt", title:str="Select file(s)"):
    """
    Panel for building a file selector window
    """

    pn.extension("tabulator")

    selector = pn.widgets.FileSelector(directory=directory, file_pattern=file_pattern, name="Files")
    run_button = pn.widgets.Button(name="OK", button_type="primary")
    header = pn.pane.Markdown(f"### {title}")

    layout = pn.Column(header, selector, run_button)

    def get_values():
        # FileSelector returns list of paths; normalize to tuple
        sel = selector.value or []
        return sel

    return layout, get_values, run_button


def panel_optreader_minimal(title: str = "OPTReader Parameters", voltage_compress: bool = True, downsample: int = 5):
    """
    Minimal form: Voltage compress + Downsample + OK button

    """
    import panel as pn
    pn.extension('tabulator')

    header = pn.pane.Markdown(f"### {title}")
    voltage_compress_checkbox = pn.widgets.Checkbox(name="Voltage Compress", value=voltage_compress)
    downsample_input = pn.widgets.IntInput(name="Downsample", value=downsample, step=1, start=1)
    run_button = pn.widgets.Button(name="OK", button_type="primary")

    layout = pn.Column(header, voltage_compress_checkbox, downsample_input, run_button)

    def get_values():
        return {
            "voltage_compress": bool(voltage_compress_checkbox.value),
            "downsample": int(downsample_input.value),
        }

    return layout, get_values, run_button


def panel_optreader_full(
    title: str = "OPTReader Parameters for Preprocessing Data",
    *,
    voltage_compress: bool = True,
    downsample: int = 5,
    cutoff_frequency: int = 25000,
    sampling_frequency: int = 250000,
    filter_type_options=("lowpass", "highpass", "bandpass", "bandstop"),
    filter_method_options=("bessel", "butter"),
    filter_type_default: str = "lowpass",
    filter_method_default: str = "butter",
    order: int = 2,
    bidirectional: bool = True,
    samples_remove: int = 100,
):
    """
    Full preprocessing form, second plot.

    """
    pn.extension('tabulator')

    header = pn.pane.Markdown(f"### {title}")

    voltage_compress_w = pn.widgets.Checkbox(name="Voltage Compress", value=voltage_compress)
    downsample_w = pn.widgets.IntInput(name="Downsample", value=downsample, step=1, start=1)

    cutoff_w = pn.widgets.IntInput(name="Cutoff Frequency", value=cutoff_frequency, step=1, start=1)
    fs_w = pn.widgets.IntInput(name="Sampling Frequency", value=sampling_frequency, step=1, start=1)

    filter_type_w = pn.widgets.Select(
        name="Filter type",
        options=list(filter_type_options),
        value=(filter_type_default if filter_type_default in filter_type_options else filter_type_options[0]),
    )
    filter_method_w = pn.widgets.Select(
        name="Filter method",
        options=list(filter_method_options),
        value=(filter_method_default if filter_method_default in filter_method_options else filter_method_options[0]),
    )

    order_w = pn.widgets.IntInput(name="Order", value=order, step=1, start=1)
    bidir_w = pn.widgets.Checkbox(name="Bidirectional", value=bidirectional)
    samples_remove_w = pn.widgets.IntInput(name="Samples to Remove", value=samples_remove, step=1, start=0)

    run_button = pn.widgets.Button(name="OK", button_type="primary")

    # Lay it out
    form = pn.Column(
        header,
        pn.Row(voltage_compress_w, downsample_w),
        pn.Row(cutoff_w, fs_w),
        pn.Row(filter_type_w, filter_method_w),
        pn.Row(order_w, bidir_w, samples_remove_w),
        run_button,
    )

    def get_values():
        return {
            "voltage_compress": bool(voltage_compress_w.value),
            "downsample": int(downsample_w.value),
            "cutoff_frequency": int(cutoff_w.value),
            "sampling_frequency": int(fs_w.value),
            "filter_type": str(filter_type_w.value),
            "filter_method": str(filter_method_w.value),
            "order": int(order_w.value),
            "bidirectional": bool(bidir_w.value),
            "samples_remove": int(samples_remove_w.value),
        }

    return form, get_values, run_button


def panel_filter_from_dataclass(
    title: str = "Filter Parameters",
    *,
    show_voltage_compress: bool = True,
    voltage_compress_default: bool = True,
    show_downsample: bool = True,
    downsample_default: int = 5,
):
    """
    Panel form for Filter dataclass metadata.

    """
    from dataclasses import fields, MISSING
    from typing import Literal, get_origin, get_args, Union
    from ionique.utils import Filter

    pn.extension('tabulator')

    header = pn.pane.Markdown(f"### {title}")

    extra_rows = []
    voltage_compress_w = None
    downsample_w = None
    if show_voltage_compress:
        voltage_compress_w = pn.widgets.Checkbox(name="Voltage Compress", value=voltage_compress_default)
        extra_rows.append(voltage_compress_w)
    if show_downsample:
        downsample_w = pn.widgets.IntInput(name="Downsample", value=downsample_default, step=1, start=1)
        extra_rows.append(downsample_w)

    widgets = {}
    rows = []
    for f in fields(Filter):
        ann = f.type
        label = f.name.replace("_", " ").title()

        if get_origin(ann) is Literal:
            choices = list(get_args(ann))
            default = (f.default if f.default is not MISSING else (choices[0] if choices else None))
            w = pn.widgets.Select(name=label, options=choices, value=default)
        elif ann is bool:
            default = (bool(f.default) if f.default is not MISSING else False)
            w = pn.widgets.Checkbox(name=label, value=default)
        elif ann is int:
            default = (int(f.default) if f.default is not MISSING else 0)
            start = f.metadata.get("min", None) if f.metadata else None
            end = f.metadata.get("max", None) if f.metadata else None
            kwargs = {"name": label, "value": default}
            if start is not None:
                kwargs["start"] = int(start)
            w = pn.widgets.IntInput(**kwargs)

        elif ann is float or (get_origin(ann) is Union and float in get_args(ann)):
            default = (None if f.default is MISSING else f.default)
            w = pn.widgets.TextInput(name=label, value=("" if default is None else str(default)))
        else:
            default = ("" if f.default is MISSING else str(f.default))
            w = pn.widgets.TextInput(name=label, value=default)

        widgets[f.name] = w
        rows.append(w)

    run_button = pn.widgets.Button(name="OK", button_type="primary")
    layout = pn.Column(header, *extra_rows, *rows, run_button)

    def get_values():
        kwargs = {}
        for f in fields(Filter):
            w = widgets[f.name]
            val = w.value
            ann = f.type
            if get_origin(ann) is Literal:
                kwargs[f.name] = val
            elif ann is bool:
                kwargs[f.name] = bool(val)
            elif ann is int:
                kwargs[f.name] = int(val)
            elif ann is float or (get_origin(ann) is Union and float in get_args(ann)):
                txt = str(val).strip()
                kwargs[f.name] = (None if txt == "" or txt.lower() == "none" else float(txt))
            else:
                kwargs[f.name] = val

        out = {
            "filter": Filter(**kwargs),
        }
        if voltage_compress_w is not None:
            out["voltage_compress"] = bool(voltage_compress_w.value)
        if downsample_w is not None:
            out["downsample"] = int(downsample_w.value)
        return out

    return layout, get_values, run_button






















