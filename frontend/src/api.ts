// Talks to the Django API. The shapes below mirror the JSON returned by /api/meta/,
// /api/forecast/ and /api/accuracy/ (all values in MW).

// Empty in development (Vite forwards /api to Django). In production, set VITE_API_URL
// to the deployed backend address, e.g. https://wind-challenge.vercel.app
const BASE = import.meta.env.VITE_API_URL ?? "";

export type Meta = {
    decision_window: [string, string];
    delivery_window: [string, string];
    default_cutoff: string;
    cutoff_timezone: string;
    units: string;
    error_definition: string;
};

export type Point = {
    start_time: string;
    forecast_mw: number | null;
    publish_time: string | null;
    horizon_hours: number | null;
    actual_mw: number | null;
};

export type ForecastResponse = {
    delivery_date: string;
    decision_deadline: string;
    points: Point[];
    summary: {
        slots_without_forecast: number;
        mean_forecast_mw: number | null;
        min_forecast_mw: number | null;
        max_forecast_mw: number | null;
    };
};

export type Metrics = {
    n: number;
    mae_mw: number | null;
    rmse_mw: number | null;
    bias_mw: number | null;
    wmape_pct: number | null;
};

export type AccuracyResponse = {
    delivery_from: string;
    delivery_to: string;
    cutoff: string;
    overall: Metrics & { slots_missing_data: number; mean_horizon_hours: number | null };
    by_day: (Metrics & { delivery_date: string })[];
    by_hour_of_day: (Metrics & { hour: number })[];
    by_horizon: (Metrics & { horizon: string })[];
};

async function get<T>(endpoint: string, params: Record<string, string> = {}): Promise<T> {
    const query = new URLSearchParams(params).toString();
    const response = await fetch(`${BASE}/api/${endpoint}/${query ? `?${query}` : ""}`);
    if (!response.ok) {
        throw new Error(`The API answered ${response.status} for ${endpoint}`);
    }
    return response.json() as Promise<T>;
}

export const getMeta = () => get<Meta>("meta");

export const getForecast = (deliveryDate: string, cutoff?: string) =>
    get<ForecastResponse>("forecast", { delivery_date: deliveryDate, ...(cutoff ? { cutoff } : {}) });

export const getAccuracy = (cutoff?: string) =>
    get<AccuracyResponse>("accuracy", cutoff ? { cutoff } : {});