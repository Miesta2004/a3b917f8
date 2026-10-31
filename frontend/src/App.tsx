import { useEffect, useState } from "react";
import { getForecast, getMeta, type ForecastResponse, type Meta } from "./api";

// Temporary page: checks that the front end can talk to the API.
export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getMeta(), getForecast("2026-01-15")])
        .then(([m, f]) => {
          setMeta(m);
          setForecast(f);
        })
        .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p>Erreur : {error}</p>;
  if (!meta || !forecast) return <p>Chargement…</p>;

  return (
      <main style={{ padding: 24, fontFamily: "system-ui" }}>
        <h1>Connexion à l’API</h1>
        <p>
          Livraisons couvertes : {meta.delivery_window[0]} → {meta.delivery_window[1]}
        </p>
        <p>Échéance d’achat du 15 janvier : {forecast.decision_deadline}</p>
        <p>
          Créneaux : {forecast.points.length}, sans prévision : {forecast.summary.slots_without_forecast}
        </p>
        <p>Prévision moyenne : {forecast.summary.mean_forecast_mw} MW</p>
      </main>
  );
}