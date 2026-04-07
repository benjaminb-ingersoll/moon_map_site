import { useEffect, useRef } from "react";
import * as Cesium from "cesium";

// Sphere with WGS84 equatorial radius — keeps Cesium internals happy
// while being spherical so Moon tiles drape without oblate-distortion seams.
const SPHERE = new Cesium.Ellipsoid(6378137, 6378137, 6378137);

const TILE_URL =
    "/tiles/LRO_WAC_Mosaic_Global_303ppd_v02/{z}/{y}/{x}.jpg";

// Terrain tile encoding parameters (from generate_terrain.py)
const TERRAIN_HEIGHT_OFFSET = -33560.7;
const TERRAIN_HEIGHT_SCALE = 2.232468;
const TERRAIN_TILE_SIZE = 65;
const TERRAIN_MAX_ZOOM = 5;

async function loadTerrainTile(x, y, level) {
    if (level > TERRAIN_MAX_ZOOM) level = TERRAIN_MAX_ZOOM;
    const url = `/terrain/${level}/${x}/${y}.terrain`;
    try {
        const response = await fetch(url);
        if (!response.ok) return new Int16Array(TERRAIN_TILE_SIZE * TERRAIN_TILE_SIZE);
        const buf = await response.arrayBuffer();
        const raw = new Uint16Array(buf);
        const heights = new Float32Array(raw.length);
        for (let i = 0; i < raw.length; i++) {
            heights[i] = raw[i] * TERRAIN_HEIGHT_SCALE + TERRAIN_HEIGHT_OFFSET;
        }
        return heights;
    } catch {
        return new Float32Array(TERRAIN_TILE_SIZE * TERRAIN_TILE_SIZE);
    }
}

export default function Globe({ onViewerReady }) {
    const containerRef = useRef(null);
    const viewerRef = useRef(null);

    useEffect(() => {
        if (viewerRef.current) return;

        const viewer = new Cesium.Viewer(containerRef.current, {
            baseLayer: false,
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            timeline: false,
            animation: false,
            navigationHelpButton: false,
            sceneModePicker: true,
            infoBox: true,
            selectionIndicator: false,
            globe: new Cesium.Globe(SPHERE),
            mapProjection: new Cesium.GeographicProjection(SPHERE),
            mapMode2D: Cesium.MapMode2D.ROTATE,
            requestRenderMode: true,
            maximumRenderTimeChange: Infinity,
            skyBox: false,
            skyAtmosphere: false,
            contextOptions: {
                webgl: { alpha: true },
            },
        });

        // Remove Cesium credits / logo
        viewer.cesiumWidget.creditContainer.style.display = "none";

        // Start at Earth-facing view (nearside centered)
        const r = SPHERE.maximumRadius;
        const fov = viewer.camera.frustum.fov || Cesium.Math.toRadians(60);
        const aspect = viewer.camera.frustum.aspectRatio || 1;
        // Cesium: fov is horizontal when aspect>1 (landscape), vertical when aspect<=1 (portrait)
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
        const startDist = Math.max(distV, distH) * 1.15;
        viewer.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(0, 0, startDist - r),
            orientation: {
                heading: 0,
                pitch: Cesium.Math.toRadians(-90),
                roll: 0,
            },
        });

        // Use logarithmic depth buffer to avoid frustum-split RangeError
        // with large terrain height ranges under vertical exaggeration
        viewer.scene.logarithmicDepthBuffer = true;

        // Dark space background
        viewer.scene.backgroundColor = Cesium.Color.BLACK;
        viewer.scene.globe.baseColor = Cesium.Color.BLACK;

        // Moon WAC imagery from local tiles
        const imageryProvider = new Cesium.UrlTemplateImageryProvider({
            url: TILE_URL,
            maximumLevel: 6,
            tilingScheme: new Cesium.GeographicTilingScheme({ ellipsoid: SPHERE }),
            credit: "NASA/GSFC/ASU",
        });
        viewer.imageryLayers.addImageryProvider(imageryProvider);

        // Globe rendering tweaks
        viewer.scene.globe.enableLighting = false;
        viewer.scene.globe.showGroundAtmosphere = false;

        // Allow free camera orbit — remove pole-locking constraints
        const controller = viewer.scene.screenSpaceCameraController;
        controller.constrainedAxis = undefined;
        viewer.camera.constrainedAxis = undefined;

        // Terrain from LOLA DEM tiles
        viewer.scene.globe.terrainProvider =
            new Cesium.CustomHeightmapTerrainProvider({
                width: TERRAIN_TILE_SIZE,
                height: TERRAIN_TILE_SIZE,
                tilingScheme: new Cesium.GeographicTilingScheme({ ellipsoid: SPHERE }),
                geometryTilingScheme: new Cesium.GeographicTilingScheme({ ellipsoid: SPHERE }),
                callback: loadTerrainTile,
            });
        viewer.scene.globe.terrainExaggeration = 1.0;
        viewer.scene.verticalExaggeration = 5.0;

        // Polar axis lines — two segments from surface to above each pole
        const poleStart = r * 1.0;
        const poleEnd = r * 1.3;
        const axisColor = Cesium.ColorGeometryInstanceAttribute.fromColor(
            Cesium.Color.WHITE.withAlpha(0.5)
        );
        viewer.scene.primitives.add(
            new Cesium.Primitive({
                geometryInstances: [
                    new Cesium.GeometryInstance({
                        geometry: new Cesium.PolylineGeometry({
                            positions: [
                                new Cesium.Cartesian3(0, 0, poleStart),
                                new Cesium.Cartesian3(0, 0, poleEnd),
                            ],
                            width: 1.5,
                            arcType: Cesium.ArcType.NONE,
                        }),
                        attributes: { color: axisColor },
                    }),
                    new Cesium.GeometryInstance({
                        geometry: new Cesium.PolylineGeometry({
                            positions: [
                                new Cesium.Cartesian3(0, 0, -poleStart),
                                new Cesium.Cartesian3(0, 0, -poleEnd),
                            ],
                            width: 1.5,
                            arcType: Cesium.ArcType.NONE,
                        }),
                        attributes: { color: axisColor },
                    }),
                ],
                appearance: new Cesium.PolylineColorAppearance(),
            })
        );

        // Pole labels
        viewer.entities.add({
            position: new Cesium.Cartesian3(0, 0, poleEnd),
            label: {
                text: "N",
                font: "bold 14px sans-serif",
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
        });
        viewer.entities.add({
            position: new Cesium.Cartesian3(0, 0, -poleEnd),
            label: {
                text: "S",
                font: "bold 14px sans-serif",
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
        });

        viewerRef.current = viewer;
        if (onViewerReady) onViewerReady(viewer);

        return () => {
            if (!viewer.isDestroyed()) viewer.destroy();
            viewerRef.current = null;
        };
    }, []);

    return (
        <div
            ref={containerRef}
            style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0 }}
        />
    );
}
