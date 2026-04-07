import { useState, useEffect } from "react";

export default function Legend() {
    const [colors, setColors] = useState({});
    const [descs, setDescs] = useState({});
    const [open, setOpen] = useState(false);

    useEffect(() => {
        fetch("/data/unit_colors.json")
            .then((r) => r.json())
            .then(setColors);
        fetch("/data/unit_descriptions.json")
            .then((r) => r.json())
            .then(setDescs);
    }, []);

    const units = Object.keys(colors);
    if (units.length === 0) return null;

    return (
        <div className="panel legend">
            <button className="legend-toggle" onClick={() => setOpen(!open)}>
                {open ? "▾" : "▸"} Legend ({units.length} units)
            </button>
            {open && (
                <div className="legend-body">
                    {units.map((unit) => (
                        <div key={unit} className="legend-item">
                            <span
                                className="legend-swatch"
                                style={{ background: colors[unit] }}
                            />
                            <span className="legend-label">
                                <strong>{unit}</strong>
                                {descs[unit] && ` — ${descs[unit].name}`}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
