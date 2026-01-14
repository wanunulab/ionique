#!/usr/bin/env python
"""
Module ionique.plotting
Includes convenience functions for generating routine plots.
"""
from typing import List, Optional,Literal
from ionique.core import AnySegment
from ionique.datatypes import SessionFileManager
import matplotlib.pyplot as plt


def qp_trace(seg:AnySegment|None = None, ranks=["vstepgap","event"],downsamples={"vstepgap":50,"event":1},fig_size=(6,5),ranks_kwargs={},fig_kwargs={},plot_voltage:Literal["same","split",None]=None):
    """
    quickly plot a trace, or segment.
    """

    if seg is None or type(seg) is SessionFileManager:
        session=SessionFileManager()
        if len(session.children)==0:
            raise Exception("No files have been loaded into this session.")
        else:
            seg=session
          
    if seg.rank is None: # root session
        independent_segs=seg.children
    else:
        independent_segs=[seg]
    for seg in independent_segs:
        title=seg.get_feature("metadata")["HeaderFile"][-60:]
        if plot_voltage is None:
            fig,axc = plt.subplots(1,1,figsize=fig_size,**fig_kwargs)
            axc.set_xlabel("Time (s)")
        elif plot_voltage == "same":
            fig,axc = plt.subplots(1,1,figsize=fig_size,**fig_kwargs)
            axv=axc.twinx()
            axv.tick_params(axis='y', colors='red')        # ticks + tick labels
            axv.spines['right'].set_color('red')
            axv.set_ylabel("Voltage (mV)",color='red')
            axc.set_xlabel("Time (s)")
        elif plot_voltage == "split":
            fig,(axc,axv) = plt.subplots(2,1,sharex=True,height_ratios=(2,1),figsize=fig_size,**fig_kwargs)
            axv.set_ylabel("Voltage (mV)")
            axv.set_xlabel("Time (s)")
        axc.set_ylabel("Current (nA)")
        axc.set_title(title)
        for rank in ranks:
            rank_kwargs:dict=getattr(ranks_kwargs,rank,{})
            for item in seg.traverse_to_rank(rank):
                ds=downsamples[rank]
                color=rank_kwargs.pop("color",None)
                if not color:
                    if rank != "event" and rank!="subevent":
                        color="k"
                    elif rank=="event" and "subevent" in ranks:
                        color='k'
                axc.plot(item.time[::ds],item.current[::ds],lw=0.6,c=color,**rank_kwargs)
                if plot_voltage:
                    if rank==ranks[0] and rank!="file":
                        axv.plot([item.time[0],item.time[-1]],[item.get_feature("voltage")]*2,c='r',lw=0.6)
                    elif rank=="file":
                        ts=[[vstep.time[0],vstep.time[-1]] for vstep in item.traverse_to_rank("vstep")]
                        vs=[[vstep.get_feature("voltage")]*2 for vstep in item.traverse_to_rank("vstep")]
                        for t,v in zip(ts,vs):
                            axv.plot(t,v,c='r',lw=0.6)

    pass

import numpy as np
import pandas as pd

import panel as pn
from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    TapTool,
    Legend,
    LegendItem,
    Range1d,
)
from bokeh.palettes import Category10, Category20

pn.extension()

# -----------------------------
# Utilities
# -----------------------------

def _is_arraylike(x) -> bool:
    return isinstance(x, (np.ndarray, list, tuple))


def _non_array_columns(df: pd.DataFrame) -> List[str]:
    """Return columns whose values are not arrays in any row (ignoring NaNs)."""
    cols = []
    for c in df.columns:
        s = df[c]
        vals = s.dropna()
        if not len(vals):
            # Empty/NaN column counts as non-array for our purposes
            cols.append(c)
            continue
        if not vals.map(_is_arraylike).any():
            cols.append(c)
    return cols


def _categorical_candidates(df: pd.DataFrame) -> List[str]:
    """Non-array columns that can be used for color grouping (object/category or small unique count)."""
    candidates = []
    for c in _non_array_columns(df):
        s = df[c]
        if pd.api.types.is_categorical_dtype(s) or pd.api.types.is_object_dtype(s):
            candidates.append(c)
        else:
            # allow numerics with small cardinality
            if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) <= min(12, max(3, len(s)//10)):
                candidates.append(c)
    return candidates


def _numeric_non_array_columns(df: pd.DataFrame) -> List[str]:
    cols = []
    for c in _non_array_columns(df):
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def _detect_array_columns(df: pd.DataFrame) -> List[str]:
    cols = []
    for c in df.columns:
        s = df[c]
        if s.dropna().map(_is_arraylike).any():
            cols.append(c)
    return cols


def find_offset_samples(wrap: np.ndarray, current: np.ndarray, atol: float = 1e-8) -> Optional[int]:
    """
    Find the start index k in `wrap` where `current` best aligns by exact subsequence match (within atol).
    Returns k if found (0-based), else None. This is a direct sliding-window allclose check.
    """
    if wrap is None or current is None:
        return None
    wrap = np.asarray(wrap)
    current = np.asarray(current)
    n = len(current)
    m = len(wrap)
    if n == 0 or m == 0 or n > m:
        return None
    # Fast path: try simple search using vectorized comparison thresholds
    for k in range(m - n + 1):
        if np.allclose(wrap[k:k+n], current, atol=atol, rtol=0.0):
            return k
    return None


def compute_sampling_frequency(row: pd.Series) -> Optional[float]:
    """Per spec: sampling_frequency = row['start'] / row['start_time'].
    Returns None if invalid or missing."""
    try:
        start = row["start"]
        start_time = row["start_time"]
        if pd.isna(start) or pd.isna(start_time):
            return None
        if float(start_time) == 0:
            return None
        return float(start) / float(start_time)
    except Exception:
        return None


# -----------------------------
# Main builder
# -----------------------------


from bokeh.palettes import Category10, Category20
from bokeh.plotting import figure
from bokeh.models import (
    HoverTool, TapTool, Range1d, ColumnDataSource,
    CDSView, BooleanFilter
)


def dashboard_event_inspection(df: pd.DataFrame):
    """
    Panel + Bokeh dashboard for exploring ionic current events.

    Adds:
      • Voltage filter (single-select) to show only events at a chosen voltage.
      • Group-by dropdown still controls coloring (can select 'voltage' there too).
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pn.pane.Markdown("❌ DataFrame is empty or invalid.")

    # ---------- helpers ----------
    def _pick_palette(n: int):
        if n <= 10:
            return Category10[10][:n]
        elif n <= 20:
            return Category20[20][:n]
        else:
            base = Category10[10]
            reps = (n // 10) + 1
            return (base * reps)[:n]

    # Column classifications
    numeric_cols = _numeric_non_array_columns(df)
    group_cols = ["(None)"] + _categorical_candidates(df)
    if "Voltage" in df.columns and "Voltage" not in group_cols:
        group_cols.append("Voltage")

    # ---------- widgets ----------
    x_select = pn.widgets.Select(name="X axis", options=numeric_cols,
                                 value=numeric_cols[0] if numeric_cols else None)
    y_select = pn.widgets.Select(name="Y axis", options=numeric_cols,
                                 value=(numeric_cols[1] if len(numeric_cols) > 1 else
                                        (numeric_cols[0] if numeric_cols else None)))
    group_select = pn.widgets.Select(name="Color by (group)", options=group_cols, value="(None)")

    # Voltage filter (single-select; choose "(All)" to show all)
    if "Voltage" in df.columns:
        _voltages = [str(v) for v in sorted(df["Voltage"].dropna().unique().tolist(), key=float)]
    else:
        _voltages = []
    voltage_filter = pn.widgets.Select(name="Show voltage", options=["(All)"] + _voltages, value="(All)")

    x_log = pn.widgets.Checkbox(name="Log X", value=False)
    y_log = pn.widgets.Checkbox(name="Log Y", value=False)

    select_idx = pn.widgets.IntInput(name="Row selector", value=-1, start=-1, end=max(len(df)-1, 0), step=1)
    clear_btn = pn.widgets.Button(name="Clear selection", button_type="warning")

    y_autoscale = pn.widgets.Checkbox(name="Auto-scale Y (event view)", value=True)
    show_segments = pn.widgets.Checkbox(name="Show sub-segments", value=False)
    status = pn.pane.Markdown("")

    scatter_source = ColumnDataSource(data=dict(
        index=np.arange(len(df)),
        x=np.zeros(len(df)),
        y=np.zeros(len(df)),
        color=["#1f77b4"]*len(df),
        size=[4]*len(df),
        alpha=[0.2]*len(df),
        legend=[""]*len(df),
        group_val=[""]*len(df),
        voltage_str=(df["Voltage"].astype(str).fillna("NA").values
                     if "Voltage" in df.columns else ["NA"]*len(df)),
    ))

    def _build_scatter_source():
        if x_select.value is None or y_select.value is None:
            return
        x = df[x_select.value].values
        y = df[y_select.value].values

        legend = [""] * len(df)
        colors = ["#1f77b4"] * len(df)

        if group_select.value and group_select.value != "(None)":
            groups_raw = df[group_select.value]
            groups = groups_raw.astype(str).fillna("NA").values
            uniq = list(pd.unique(groups))
            palette = _pick_palette(len(uniq))
            color_map = {g: palette[i % len(palette)] for i, g in enumerate(uniq)}
            colors = [color_map[g] for g in groups]
            legend = groups

        scatter_source.data.update(
            index=np.arange(len(df)),
            x=x, y=y, color=colors,
            size=[4]*len(df), alpha=[0.4]*len(df),
            legend=legend, group_val=legend,
            voltage_str=(df["Voltage"].astype(str).fillna("NA").values
                         if "Voltage" in df.columns else scatter_source.data["voltage_str"])
        )

    # Build once before first render
    _build_scatter_source()

    bool_filter = BooleanFilter(booleans=[True]*len(df))
    view = CDSView(filter=bool_filter)

    def _update_voltage_view():
        if not _voltages or voltage_filter.value == "(All)":
            mask = [True]*len(df)
        else:
            allowed = {voltage_filter.value}
            vstr = scatter_source.data.get("voltage_str", ["NA"]*len(df))
            mask = [vs in allowed for vs in vstr]
        bool_filter.booleans = mask

    _update_voltage_view()

    scatter_pane = pn.pane.Bokeh(sizing_mode="stretch_both")

    def _make_scatter_figure():
        x_axis_type = "log" if x_log.value else "linear"
        y_axis_type = "log" if y_log.value else "linear"
        p = figure(height=350, sizing_mode="stretch_width",
                   tools="pan,wheel_zoom,box_zoom,reset,tap,hover,save",
                   x_axis_type=x_axis_type, y_axis_type=y_axis_type)
        # p.circle(source=scatter_source, x="x", y="y",
        #          size="size", color="color", alpha="alpha", line_color=None,
        #          legend_field="legend", view=view)
        p.scatter(source=scatter_source, x="x", y="y",
                 size="size", color="color", alpha="alpha", line_color=None,
                 legend_field="legend", view=view)

        p.add_tools(TapTool())
        hover = p.select_one(HoverTool)
        hover.tooltips = [
            ("row", "@index"),
            (x_select.name, "@x"),
            (y_select.name, "@y"),
            ("group", "@group_val"),
            ("voltage", "@voltage_str"),
        ]
        p.title.text = "Event Scatter"
        p.legend.visible = (group_select.value and group_select.value != "(None)")
        p.legend.location = "top_right"
        p.legend.click_policy = "hide"

        scatter_pane.object = p
        return p

    p_scatter = _make_scatter_figure()

    # ---------- event view ----------
    # event_fig = figure(height=300, sizing_mode="stretch_width",
    #                    tools="pan,wheel_zoom,box_zoom,reset,save", output_backend='webgl')
    # event_fig.title.text = "Blockade Event View"
    # wrap_renderer = event_fig.line([], [], line_color="#000000", line_width=1, alpha=0.9)
    # current_renderer = event_fig.line([], [], line_color="#1f77b4", line_width=1, alpha=0.9)
    # segments_source = ColumnDataSource(data=dict(xs=[], ys=[], color=[]))
    # event_fig.multi_line(xs='xs', ys='ys', line_color='color', line_width=3, alpha=0.95, source=segments_source)

    event_fig = figure(height=500, width=500, sizing_mode="stretch_width",
                       tools="pan,wheel_zoom,box_zoom,reset,save", output_backend='webgl')
    event_fig.title.text = "Blockade Event View"
    wrap_renderer = event_fig.line([], [], line_color="#000000", line_width=1, line_alpha=0.9)
    current_renderer = event_fig.line([], [], line_color="#1f77b4", line_width=1, line_alpha=0.9)
    segments_source = ColumnDataSource(data=dict(xs=[], ys=[], color=[]))
    event_fig.multi_line(xs='xs', ys='ys', line_color='color', line_width=3, line_alpha=0.9, source=segments_source)

    selected_index = {"idx": -1}

    def _highlight_selection():
        idx = selected_index["idx"]
        sizes = [9 if i == idx else 5 for i in range(len(df))]
        alphas = [1.0 if i == idx else 0.85 for i in range(len(df))]
        scatter_source.data.update(size=sizes, alpha=alphas)

    def _update_event_view(idx: int):
        segments_source.data = dict(xs=[], ys=[], color=[])
        if idx is None or idx < 0 or idx >= len(df):
            wrap_renderer.data_source.data = {"x": [], "y": []}
            current_renderer.data_source.data = {"x": [], "y": []}
            status.object = "(no selection)"
            return

        row = df.iloc[idx]
        wrap = row.get("wrap", None)
        current = row.get("current", None)
        if wrap is None or current is None or not _is_arraylike(wrap) or not _is_arraylike(current):
            status.object = f"❌ Row {idx}: missing 'wrap' or 'current' arrays."
            return

        wrap = np.asarray(wrap)
        current = np.asarray(current)
        fs = compute_sampling_frequency(row)
        if fs is None or fs <= 0:
            status.object = f"⚠️ Row {idx}: could not compute sampling frequency from start/start_time."

        k = find_offset_samples(wrap, current, atol=1e-8)
        if k is None:
            k = 0
            status.object = f"⚠️ Row {idx}: could not match 'current' inside 'wrap' (plotting fallback)."
        else:
            status.object = f"Selected row {idx}."

        start = row.get("start", 0)
        if fs and fs > 0:
            wrap_start_time = (float(start) - float(k)) / fs
            t_wrap = wrap_start_time + np.arange(len(wrap)) / fs
            t_current = t_wrap[k : k + len(current)]
        else:
            t_wrap = np.arange(len(wrap))
            t_current = np.arange(k, k + len(current))

        wrap_renderer.data_source.data = {"x": t_wrap, "y": wrap}
        current_renderer.data_source.data = {"x": t_current, "y": current}
        event_fig.x_range = Range1d(float(np.min(t_wrap)), float(np.max(t_wrap)))

        if y_autoscale.value:
            ymin = float(np.min(wrap))
            ymax = float(np.max(wrap))
            pad = 0.05 * (ymax - ymin if ymax > ymin else 1.0)
            event_fig.y_range = Range1d(ymin - pad, ymax + pad)

        if show_segments.value:
            seg_starts = row.get("subevent_starts", None)
            seg_ends = row.get("subevent_ends", None)
            if _is_arraylike(seg_starts) and _is_arraylike(seg_ends):
                seg_starts = np.asarray(seg_starts)
                seg_ends = np.asarray(seg_ends)
                nsegs = int(min(len(seg_starts), len(seg_ends)))
                if nsegs > 0:
                    palette = (Category10[10] * ((nsegs // 10) + 1)) if nsegs > 10 else Category10[max(3, nsegs)]
                    xs, ys, cols = [], [], []
                    for i in range(nsegs):
                        s = int(seg_starts[i]); e = int(seg_ends[i])
                        if s < 0 or e <= s or e > len(current):
                            continue
                        xs.append(t_current[s:e].tolist())
                        ys.append(current[s:e].tolist())
                        cols.append(palette[i % len(palette)])
                    segments_source.data = dict(xs=xs, ys=ys, color=cols)
            wrap_renderer.glyph.line_alpha = 0.6
            current_renderer.glyph.line_alpha = 0.6
        else:
            wrap_renderer.glyph.line_alpha = 0.9
            current_renderer.glyph.line_alpha = 0.9

    # ---------- wiring ----------
    def _on_scatter_tap(attr, old, new):
        inds = new
        if inds:
            idx = int(inds[0])
            selected_index["idx"] = idx
            select_idx.value = idx
            _highlight_selection()
            _update_event_view(idx)
        else:
            selected_index["idx"] = -1
            select_idx.value = -1
            _highlight_selection()
            _update_event_view(-1)

    scatter_source.selected.on_change("indices", lambda attr, old, new: _on_scatter_tap(attr, old, new))

    def _on_spinner_change(event):
        idx = int(event.new)
        scatter_source.selected.indices = ([] if idx < 0 or idx >= len(df) else [idx])

    select_idx.param.watch(_on_spinner_change, "value")
    clear_btn.on_click(lambda _ : setattr(scatter_source.selected, "indices", []))

    def _on_axis_change(event=None):
        _build_scatter_source()
        _make_scatter_figure()
        _update_voltage_view()
        _highlight_selection()

    for w in (x_select, y_select, group_select, x_log, y_log):
        w.param.watch(_on_axis_change, "value")

    voltage_filter.param.watch(lambda e: (_update_voltage_view(), _highlight_selection()), "value")

    def _on_flags_change(event=None):
        _update_event_view(selected_index["idx"])

    y_autoscale.param.watch(_on_flags_change, "value")
    show_segments.param.watch(_on_flags_change, "value")

    _highlight_selection()
    _update_event_view(-1)

    controls = pn.Row(
        pn.Column(x_select, y_select, group_select, voltage_filter, sizing_mode="fixed", width=280),
        pn.Spacer(width=20),
        pn.Column(x_log, y_log, select_idx, clear_btn, y_autoscale, show_segments, status, width=280),
    )

    layout = pn.Column(
        pn.pane.Markdown("### Ionic Events Explorer"),
        controls,
        pn.Row(scatter_pane, event_fig),
        sizing_mode="stretch_width",
    )
    return layout


def qp_scatter(**args):
  """
  quickly generate a scatterplot from specified parameters. wrapper for seaborn scatterplot
  """
  pass

def qp_histogram(**args):
  """
  quickly plot a 1-D histogram from specified parameter. wrapper for seaborn histplot
  """
  pass

def _get_feature_df_from_segments(**args):
  """
  if a qp (non-trace) function receives a segment, extract required features and return a pandas dataframe.
  """
  pass
