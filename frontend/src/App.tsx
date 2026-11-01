import { useEffect, useState } from "react";
import { getMeta, type Meta } from "./api";
import AccuracyView from "./components/AccuracyView";
import ForecastView from "./components/ForecastView";
import "./App.css";

const DEFAULT_DATE = "2026-01-15";

// The delivery day and the purchase deadline are shared by both views, so they live here.
function Dashboard({ meta }: { meta: Meta }) {
    const [date, setDate] = useState(DEFAULT_DATE);
    const [cutoff, setCutoff] = useState(meta.default_cutoff);

    const openDay = (day: string) => {
        setDate(day);
        document.getElementById("forecast")?.scrollIntoView({ behavior: "smooth" });
    };

    return (
        <>
            <ForecastView
                minDate={meta.delivery_window[0]}
                maxDate={meta.delivery_window[1]}
                date={date}
                cutoff={cutoff}
                onDateChange={setDate}
                onCutoffChange={setCutoff}
            />
            {cutoff && <AccuracyView cutoff={cutoff} onPickDay={openDay} />}
        </>
    );
}

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
            {meta && <Dashboard meta={meta} />}
        </main>
    );
}