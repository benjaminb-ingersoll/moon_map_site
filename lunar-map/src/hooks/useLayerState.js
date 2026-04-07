import { useState, useEffect, useCallback } from "react";

const STORAGE_KEY = "lunarMapState";

const defaultState = {
    Copernican: true,
    Eratosthenian: true,
    "Eratosthenian-Imbrian": true,
    Imbrian: true,
    "Imbrian-Nectarian": true,
    Nectarian: true,
    "Pre-Nectarian": true,
    linearFeatures: false,
};

function loadState() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) return { ...defaultState, ...JSON.parse(raw) };
    } catch { }
    return { ...defaultState };
}

export function useLayerState() {
    const [layers, setLayers] = useState(loadState);

    useEffect(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(layers));
    }, [layers]);

    const toggleLayer = useCallback((key) => {
        setLayers((prev) => ({ ...prev, [key]: !prev[key] }));
    }, []);

    return { layers, toggleLayer };
}
