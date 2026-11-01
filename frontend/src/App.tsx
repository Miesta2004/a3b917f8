import { useEffect, useState } from "react";
import { getMeta, type Meta } from "./api";
import ForecastView from "./components/ForecastView";
import "./App.css";

export default function App() {
    const [meta, setMeta] = useState<Meta | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        getMeta()
            .then(setMeta)
            .catch((e: Error) => setError(e.message));
    }, []);

    return (
        <main className="page">
            <h1>Wind forecasts for day-ahead purchases</h1>
            <p className="lead">
                UK wind generation, January 2026: the forecast the buyer could see when deciding, and how accurate it turned
                out to be.
            </p>
            {error && <p className="error">Could not reach the API: {error}</p>}
            {!meta && !error && <p>Loading…</p>}
            {meta && (
                <ForecastView
                    minDate={meta.delivery_window[0]}
                    maxDate={meta.delivery_window[1]}
                    defaultCutoff={meta.default_cutoff}
                />
            )}
        </main>
    );
}