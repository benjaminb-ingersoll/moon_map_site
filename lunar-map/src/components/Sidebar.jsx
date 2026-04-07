import { useState, useEffect, useRef } from "react";
import * as Cesium from "cesium";
import { ERA_ORDER, ERA_LABEL_COLORS } from "../data/config";

export default function Sidebar({ layers, toggleLayer, viewer }) {
    const [collapsed, setCollapsed] = useState(true);
    const sidebarRef = useRef(null);

    // Close sidebar when clicking outside it
    useEffect(() => {
        if (collapsed) return;
        function handleClick(e) {
            if (sidebarRef.current && !sidebarRef.current.contains(e.target)) {
                setCollapsed(true);
            }
        }
        document.addEventListener("pointerdown", handleClick, true);
        return () => document.removeEventListener("pointerdown", handleClick, true);
    }, [collapsed]);

    function flyToNearside() {
        if (!viewer) return;
        const ellipsoid = viewer.scene.globe.ellipsoid;
        const r = ellipsoid.maximumRadius;
        const fov = viewer.camera.frustum.fov || Cesium.Math.toRadians(60);
        const aspect = viewer.camera.frustum.aspectRatio || 1;
        let trueVFov, trueHFov;
        if (aspect > 1) {
            trueHFov = fov;
            trueVFov = 2 * Math.atan(Math.tan(fov / 2) / aspect);
        } else {
            trueVFov = fov;
            trueHFov = 2 * Math.atan(Math.tan(fov / 2) * aspect);
        }
        const distV = r / Math.sin(trueVFov / 2);
        const distH = r / Math.sin(trueHFov / 2);
        const dist = Math.max(distV, distH) * 1.15;
        viewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(0, 0, dist - r),
            orientation: {
                heading: 0,
                pitch: Cesium.Math.toRadians(-90),
                roll: 0,
            },
            duration: 1.5,
        });
    }
    const [legendOpen, setLegendOpen] = useState(false);
    const [colors, setColors] = useState({});
    const [descs, setDescs] = useState({});

    useEffect(() => {
        fetch("/data/unit_colors.json")
            .then((r) => r.json())
            .then(setColors);
        fetch("/data/unit_descriptions.json")
            .then((r) => r.json())
            .then(setDescs);
    }, []);

    const units = Object.keys(colors);

    if (collapsed) {
        return (
            <div className="sidebar-collapsed-btns">
                <button
                    className="sidebar-toggle-btn"
                    onClick={() => setCollapsed(false)}
                    title="Open sidebar"
                >
                    ☰
                </button>
                <button
                    className="sidebar-toggle-btn"
                    onClick={flyToNearside}
                    title="Earth-facing view"
                >
                    🌕
                </button>
            </div>
        );
    }

    return (
        <div className="sidebar" ref={sidebarRef}>
            {/* Header */}
            <div className="sidebar-header">
                <div className="sidebar-title">
                    <h2>Geologic Map of the Moon</h2>
                    <span className="sidebar-subtitle">
                        USGS 1:5M — Fortezzo, Spudis &amp; Harrel (2020)
                    </span>
                </div>
                <button
                    className="sidebar-close"
                    onClick={() => setCollapsed(true)}
                    title="Collapse sidebar"
                >
                    ✕
                </button>
            </div>

            <div className="sidebar-section">
                <button className="nearside-btn" onClick={flyToNearside}>
                    🌕 Earth-facing view
                </button>
            </div>

            <div className="sidebar-divider" />

            {/* Layers section */}
            <div className="sidebar-section">
                <h3 className="sidebar-section-title">Geologic Eras</h3>
                <div className="era-list">
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
                </div>
            </div>

            <div className="sidebar-divider" />

            {/* Legend section */}
            <div className="sidebar-section sidebar-section-legend">
                <button
                    className="legend-toggle"
                    onClick={() => setLegendOpen(!legendOpen)}
                >
                    <span className="legend-arrow">{legendOpen ? "▾" : "▸"}</span>
                    <h3 className="sidebar-section-title" style={{ margin: 0 }}>
                        Unit Legend
                    </h3>
                    <span className="legend-count">{units.length}</span>
                </button>
                {legendOpen && units.length > 0 && (
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
        </div>
    );
}
