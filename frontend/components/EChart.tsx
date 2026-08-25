"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function injectAxisNameColor(option: EChartsOption): EChartsOption {
  const color = cssVar("--text-dim") || "#8b8b93";
  const patch = (axis: unknown) => {
    if (!axis || typeof axis !== "object") return;
    const a = axis as Record<string, unknown>;
    if (!("name" in a)) return; // only touch axes that have a name set
    const style = (a.nameTextStyle ?? {}) as Record<string, unknown>;
    if (!("color" in style)) style.color = color;
    a.nameTextStyle = style;
  };
  const applyToAxes = (axes: unknown) => {
    if (Array.isArray(axes)) axes.forEach(patch);
    else patch(axes);
  };
  applyToAxes(option.xAxis);
  applyToAxes(option.yAxis);
  return option;
}

export type EChartHandle = {
  /** Exports the current chart as a PNG and triggers a browser download.
   * Bakes in the page's --bg color explicitly — the chart's own canvas is
   * transparent (the prompt tells the LLM not to set backgroundColor,
   * since the page already provides it), so an export without this would
   * come out with a transparent background instead of matching what's
   * actually shown on screen. */
  downloadPng: (filename: string) => void;
};

/** Thin ECharts wrapper — owns the chart instance's lifecycle (init/resize/
 * dispose) so callers just pass an option object. */
const EChart = forwardRef<EChartHandle, { option: EChartsOption; height?: number }>(function EChart(
  { option, height = 280 },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const onResize = () => chart.resize();
    const observer = new ResizeObserver(onResize);
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    // Re-setting (not just resizing) whenever height changes forces ECharts
    // to fully recompute layout from scratch — a plain .resize() on a chart
    // with rotated/crowded axis labels can garble them on a big incremental
    // shrink (e.g. switching from the 360px single view to a 220px
    // dashboard card) instead of laying them out cleanly for the new size.
    chartRef.current?.setOption(injectAxisNameColor(option), true);
  }, [option, height]);

  useImperativeHandle(ref, () => ({
    downloadPng: (filename: string) => {
      const chart = chartRef.current;
      if (!chart) return;
      const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#0a0a0b";
      const url = chart.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: bg });
      const a = document.createElement("a");
      a.href = url;
      a.download = filename.endsWith(".png") ? filename : `${filename}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },
  }));

  return <div ref={containerRef} style={{ width: "100%", height }} />;
});

export default EChart;
