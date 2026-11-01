import { useEffect, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAccuracy, type AccuracyResponse, type Metrics } from "../api";

type Props = {
    cutoff: string; // purchase deadline shared with the forecast view
    onPickDay: (date: string) => void; // clicking a day opens it in the forecast view
};

// Deadlines compared in the "does deciding later help?" chart (UK time, day before delivery).
const COMPARED_CUTOFFS = ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"];

const mw = (v: number | null) => (v === null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);
const signed = (v: number | null) => (v === null ? "–" : `${v > 0 ? "+" : ""}${Math.round(v).toLocaleString("en-GB")} MW`);
const tooltipMw = (v: unknown) => mw(typeof v === "number" ? v : null);

const shortDate = (iso: string) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

type MonthResult = { cutoff: string; data?: AccuracyResponse; error?: string };
type CompareResult = { rows?: { cutoff: string; metrics: Metrics }[]; error?: string };

export default function AccuracyView({ cutoff, onPickDay }: Props) {
    const [month, setMonth] = useState<MonthResult | null>(null);
    const [compare, setCompare] = useState<CompareResult | null>(null);

    // Whole month at the chosen deadline. As in ForecastView, a result is only shown if it
    // matches the current deadline, so an old answer never appears under new inputs.
    useEffect(() => {
        if (!cutoff) return;
        let cancelled = false;
        getAccuracy({ cutoff })
            .then((data) => {
                if (!cancelled) setMonth({ cutoff, data });
            })
            .catch((e: Error) => {
                if (!cancelled) setMonth({ cutoff, error: e.message });
            });
        return () => {
            cancelled = true;
        };
    }, [cutoff]);

    // The same month for several deadlines, loaded once.
    useEffect(() => {
        let cancelled = false;
        Promise.all(COMPARED_CUTOFFS.map((c) => getAccuracy({ cutoff: c })))
            .then((results) => {
                if (!cancelled) setCompare({ rows: results.map((r, i) => ({ cutoff: COMPARED_CUTOFFS[i], metrics: r.overall })) });
            })
            .catch((e: Error) => {
                if (!cancelled) setCompare({ error: e.message });
            });
        return () => {
            cancelled = true;
        };
    }, []);

    const current = month?.cutoff === cutoff ? month : null;
    const overall = current?.data?.overall;
    const dayData = current?.data?.by_day.map((d) => ({
        date: d.delivery_date,
        label: shortDate(d.delivery_date),
        mae: d.mae_mw,
        bias: d.bias_mw,
    }));
    const compareData = compare?.rows?.map((r) => ({ cutoff: r.cutoff, mae: r.metrics.mae_mw, wmape: r.metrics.wmape_pct }));
    const best = compareData?.reduce((a, b) => ((b.mae ?? Infinity) < (a.mae ?? Infinity) ? b : a));
    const worst = compareData?.reduce((a, b) => ((b.mae ?? -Infinity) > (a.mae ?? -Infinity) ? b : a));
    const gain = best?.mae != null && worst?.mae ? (worst.mae - best.mae) / worst.mae : 0; // share of the error saved by the best deadline

    return (
        <section>
            <h2>How accurate were the forecasts over January?</h2>

            {!current && <p>Loading…</p>}
            {current?.error && <p className="error">Could not load the data: {current.error}</p>}

            {overall && dayData && (
                <>
                    <p className="deadline">
                        All delivery days of the month, judged on the forecast available at <b>{cutoff}</b> (UK time) the day before.
                    </p>

                    <div className="cards">
                        <div className="card">
                            <span>Bias (forecast − actual)</span>
                            <b>{signed(overall.bias_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Typical error (MAE)</span>
                            <b>{mw(overall.mae_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Large misses (RMSE)</span>
                            <b>{mw(overall.rmse_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Error vs output</span>
                            <b>{overall.wmape_pct === null ? "–" : `${overall.wmape_pct} %`}</b>
                        </div>
                    </div>

                    {overall.bias_mw !== null && (
                        <p className="reading">
                            {overall.bias_mw > 0
                                ? `Over the month the forecast was too high by ${mw(overall.bias_mw)} on average: a buyer trusting it as it is would have bought too little.`
                                : `Over the month the forecast was too low by ${mw(Math.abs(overall.bias_mw))} on average: a buyer trusting it as it is would have bought more than needed.`}{" "}
                            Subtracting this bias from the forecast is the simplest correction, but individual days still move a lot (see below).
                        </p>
                    )}

                    <h3>Error by delivery day</h3>
                    <p className="hint">Click a day to open it in the forecast view above.</p>
                    <div className="chart">
                        <ResponsiveContainer width="100%" height={320}>
                            <ComposedChart data={dayData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                                <CartesianGrid strokeOpacity={0.15} />
                                <XAxis dataKey="label" interval={2} />
                                <YAxis unit=" MW" width={80} />
                                <Tooltip formatter={tooltipMw} />
                                <Legend />
                                <ReferenceLine y={0} stroke="currentColor" strokeOpacity={0.4} />
                                <Bar
                                    dataKey="mae"
                                    name="Typical error (MAE)"
                                    fill="#1d8fb3"
                                    fillOpacity={0.55}
                                    cursor="pointer"
                                    onClick={(bar) => {
                                        // Recharts passes the bar's geometry plus the original data row (in `payload`).
                                        const item = bar as unknown as { date?: string; payload?: { date?: string } };
                                        const day = item.payload?.date ?? item.date;
                                        if (day) onPickDay(day);
                                    }}
                                />
                                <Line type="monotone" dataKey="bias" name="Bias (forecast − actual)" stroke="#d98a00" dot={false} strokeWidth={2} />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </>
            )}

            <h3>Does deciding later help?</h3>
            {!compare && <p>Loading…</p>}
            {compare?.error && <p className="error">Could not load the comparison: {compare.error}</p>}
            {compareData && best && worst && (
                <>
                    <p className="hint">Typical error over the whole month for each possible deadline on the day before delivery.</p>
                    <div className="chart">
                        <ResponsiveContainer width="100%" height={260}>
                            <LineChart data={compareData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                                <CartesianGrid strokeOpacity={0.15} />
                                <XAxis dataKey="cutoff" />
                                <YAxis unit=" MW" width={80} domain={["dataMin - 100", "dataMax + 100"]} tickFormatter={(v: number) => String(Math.round(v))} />
                                <Tooltip formatter={tooltipMw} />
                                <Line type="monotone" dataKey="mae" name="Typical error (MAE)" stroke="#1d8fb3" strokeWidth={2} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                    <p className="reading">
                        The error is lowest with a {best.cutoff} deadline ({mw(best.mae)}) and highest with {worst.cutoff} ({mw(worst.mae)}).{" "}
                        {gain < 0.2
                            ? "Waiting for fresher forecasts helps only a little: most of the error is not about timing."
                            : "Waiting for fresher forecasts clearly reduces the error."}
                    </p>
                </>
            )}
        </section>
    );
}