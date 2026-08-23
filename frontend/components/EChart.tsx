"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

/** Thin ECharts wrapper — owns the chart instance's lifecycle (init/resize/
 * dispose) so callers just pass an option object. */
export default function EChart({ option, height = 280 }: { option: EChartsOption; height?: number }) {
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
    chartRef.current?.setOption(option, true);
  }, [option, height]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
