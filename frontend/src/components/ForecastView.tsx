import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAccuracy, getForecast, type AccuracyResponse, type ForecastResponse } from "../api";

type Props = { minDate: string; maxDate: string; defaultCutoff: string };
type Result = { key: string; forecast?: ForecastResponse; accuracy?: AccuracyResponse; error?: string };

const mw = (v: number | null) => (v === null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);
const signed = (v: number | null) => (v === null ? "–" : `${v > 0 ? "+" : ""}${Math.round(v).toLocaleString("en-GB")} MW`);

export default function ForecastView({ minDate, maxDate, defaultCutoff }: Props) {
    const [date, setDate] = useState("2026-01-15");
    const [cutoff, setCutoff] = useState(defaultCutoff);
    const [result, setResult] = useState<Result | null>(null);

    // One request key per (date, deadline). A result is only shown if it matches the current key,
    // so an old answer never appears under new inputs.
    const key = `${date}|${cutoff}`;

    useEffect(() => {
        if (!date || !cutoff) return;
        let cancelled = false; // ignore answers that arrive after the inputs changed
        Promise.all([getForecast(date, cutoff), getAccuracy({ cutoff, from: date, to: date })])
            .then(([forecast, accuracy]) => {
                if (!cancelled) setResult({ key, forecast, accuracy });
            })
            .catch((e: Error) => {
                if (!cancelled) setResult({ key, error: e.message });
            });
        return () => {
            cancelled = true;
        };
    }, [date, cutoff, key]);

    const current = result?.key === key ? result : null;
    const day = current?.accuracy?.overall;
    const chartData = current?.forecast?.points.map((p) => ({
        time: p.start_time.slice(11, 16), // UTC = UK time in January
        forecast: p.forecast_mw,
        actual: p.actual_mw,
    }));

    return (
        <section>
            <h2>Forecast available at the purchase deadline</h2>

            <div className="controls">
                <label>
                    Delivery day
                    <input type="date" value={date} min={minDate} max={maxDate} onChange={(e) => setDate(e.target.value)} />
                </label>
                <label>
                    Purchase deadline (UK time, day before)
                    <input type="time" value={cutoff} onChange={(e) => setCutoff(e.target.value)} />
                </label>
            </div>

            {(!date || !cutoff) && <p>Pick a delivery day and a deadline.</p>}
            {date && cutoff && !current && <p>Loading…</p>}
            {current?.error && <p className="error">Could not load the data: {current.error}</p>}

            {current?.forecast && chartData && day && (
                <>
                    <p className="deadline">
                        For delivery on <b>{current.forecast.delivery_date}</b>, the buyer decides by{" "}
                        <b>
                            {new Date(current.forecast.decision_deadline).toLocaleString("en-GB", {
                                timeZone: "Europe/London",
                                dateStyle: "medium",
                                timeStyle: "short",
                            })}
                        </b>
                        . Each half-hour uses the latest forecast published before that moment.
                    </p>

                    <div className="chart">
                        <ResponsiveContainer width="100%" height={340}>
                            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                                <CartesianGrid strokeOpacity={0.15} />
                                <XAxis dataKey="time" interval={5} />
                                <YAxis unit=" MW" width={80} />
                                <Tooltip />
                                <Legend />
                                <Line type="monotone" dataKey="forecast" name="Forecast at deadline" stroke="#4FB3D4" dot={false} strokeWidth={2} />
                                <Line type="monotone" dataKey="actual" name="Actual generation" stroke="#E0A100" dot={false} strokeWidth={2} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="cards">
                        <div className="card">
                            <span>Mean forecast</span>
                            <b>{mw(current.forecast.summary.mean_forecast_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Bias (forecast − actual)</span>
                            <b>{signed(day.bias_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Typical error (MAE)</span>
                            <b>{mw(day.mae_mw)}</b>
                        </div>
                        <div className="card">
                            <span>Error vs output</span>
                            <b>{day.wmape_pct === null ? "–" : `${day.wmape_pct} %`}</b>
                        </div>
                    </div>

                    {day.bias_mw !== null && (
                        <p className="reading">
                            {day.bias_mw > 0
                                ? "On this day the forecast was too high: the buyer would have counted on more wind than arrived and bought too little."
                                : "On this day the forecast was too low: the buyer would have bought more than needed."}
                        </p>
                    )}
                </>
            )}
        </section>
    );
}