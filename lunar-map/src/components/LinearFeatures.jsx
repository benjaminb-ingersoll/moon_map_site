import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import { LINE_COLORS, LINE_DASH } from "../data/config";

export default function LinearFeatures({ viewer, visible }) {
    const dsRef = useRef(null);
    const loadingRef = useRef(false);

    useEffect(() => {
        if (!viewer || !visible || dsRef.current || loadingRef.current) return;
        loadingRef.current = true;

        fetch("/data/linear_features.json")
            .then((r) => r.json())
            .then((geojson) => {
                return Cesium.GeoJsonDataSource.load(geojson, {
                    stroke: Cesium.Color.YELLOW,
                    strokeWidth: 2,
                    clampToGround: false,
                });
            })
            .then((ds) => {
                if (!viewer || viewer.isDestroyed()) { ds.destroy(); return; }

                ds.name = "Linear Features";
                viewer.dataSources.add(ds);
                dsRef.current = ds;

                for (const entity of ds.entities.values) {
                    const type = entity.properties?.TYPE?.getValue() || "";
                    const hex = LINE_COLORS[type] || "#ffd43b";
                    const color = Cesium.Color.fromCssColorString(hex).withAlpha(0.85);
                    const isDashed = !!LINE_DASH[type];
                    const comment = entity.properties?.COMMENT?.getValue() || "";
                    const preservation = entity.properties?.Preservati?.getValue() || "";

                    if (entity.polyline) {
                        entity.polyline.material = isDashed
                            ? new Cesium.PolylineDashMaterialProperty({ color, dashLength: 12 })
                            : color;
                        entity.polyline.width = 2;
                    }

                    entity.name = type;
                    entity.description = `
                        <div style="font-family:sans-serif;color:#ddd;background:#1a1a2e;padding:8px;border-radius:4px;">
                          <strong>${type}</strong><br/>
                          ${comment ? `<b>Comment:</b> ${comment}<br/>` : ""}
                          ${preservation ? `<b>Preservation:</b> ${preservation}` : ""}
                        </div>`;
                }

                ds.show = true;
                loadingRef.current = false;
            });
    }, [viewer, visible]);

    useEffect(() => {
        if (dsRef.current) dsRef.current.show = !!visible;
        if (viewer && !viewer.isDestroyed()) viewer.scene.requestRender();
    }, [visible]);

    return null;
}
