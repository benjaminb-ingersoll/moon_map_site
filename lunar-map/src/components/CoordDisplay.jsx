import { useEffect, useState } from "react";
import * as Cesium from "cesium";

export default function CoordDisplay({ viewer }) {
    const [coords, setCoords] = useState(null);

    useEffect(() => {
        if (!viewer) return;

        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((movement) => {
            const cartesian = viewer.camera.pickEllipsoid(
                movement.endPosition,
                viewer.scene.globe.ellipsoid
            );
            if (cartesian) {
                const carto = Cesium.Cartographic.fromCartesian(cartesian);
                setCoords({
                    lat: Cesium.Math.toDegrees(carto.latitude).toFixed(2),
                    lon: Cesium.Math.toDegrees(carto.longitude).toFixed(2),
                });
            } else {
                setCoords(null);
            }
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

        return () => handler.destroy();
    }, [viewer]);

    if (!coords) return null;

    return (
        <div className="coord-display">
            {coords.lat}°, {coords.lon}°
        </div>
    );
}
