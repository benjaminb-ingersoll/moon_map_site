import { ERA_ORDER, ERA_LABEL_COLORS, LINE_COLORS } from "../data/config";

const uniqueLineTypes = [
    "Graben/Fossa",
    "Scarp/Rupes",
    "Ridge/Dorsum",
    "Rille/Rima",
    "Wrinkle Ridge",
];

export default function LayerControl({ layers, toggleLayer }) {
    return (
        <div className="panel layer-control">
            <h4>Geologic Eras</h4>
            {ERA_ORDER.map((era) => (
                <label key={era} className="layer-checkbox">
                    <input
                        type="checkbox"
                        checked={layers[era] !== false}
                        onChange={() => toggleLayer(era)}
                    />
                    <span
                        className="era-dot"
                        style={{ background: ERA_LABEL_COLORS[era] }}
                    />
                    {era}
                </label>
            ))}
            <hr />
            <h4>Features</h4>
            <label className="layer-checkbox">
                <input
                    type="checkbox"
                    checked={!!layers.linearFeatures}
                    onChange={() => toggleLayer("linearFeatures")}
                />
                Linear Features
            </label>
            {layers.linearFeatures && (
                <div className="line-legend">
                    {uniqueLineTypes.map((t) => (
                        <div key={t} className="line-legend-item">
                            <span
                                className="line-swatch"
                                style={{ background: LINE_COLORS[t] }}
                            />
                            <span>{t}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
