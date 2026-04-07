import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import { ERA_ORDER, ERA_LABEL_COLORS } from "../data/config";

const OUTLINE_COLOR = Cesium.Color.WHITE.withAlpha(0.5);
const HIGHLIGHT_COLOR = Cesium.Color.WHITE;
const OUTLINE_ATTR = Cesium.ColorGeometryInstanceAttribute.fromColor(OUTLINE_COLOR);
const HIGHLIGHT_ATTR = Cesium.ColorGeometryInstanceAttribute.fromColor(HIGHLIGHT_COLOR);

function getRings(geometry) {
    const rings = [];
    if (geometry.type === "Polygon") {
        for (const ring of geometry.coordinates) rings.push(ring);
    } else if (geometry.type === "MultiPolygon") {
        for (const poly of geometry.coordinates)
            for (const ring of poly) rings.push(ring);
    }
    return rings;
}

function ringToPositions(ring) {
    const flat = [];
    for (const [lon, lat] of ring) {
        flat.push(lon, lat);
    }
    return Cesium.Cartesian3.fromDegreesArray(flat);
}

// Shoelace formula for ring area (absolute value)
function ringArea(ring) {
    let area = 0;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        area += (ring[j][0] - ring[i][0]) * (ring[j][1] + ring[i][1]);
    }
    return Math.abs(area) / 2;
}

// Compute total polygon area (outer rings minus holes)
function polygonArea(geometry) {
    let total = 0;
    if (geometry.type === "Polygon") {
        total = ringArea(geometry.coordinates[0]);
    } else if (geometry.type === "MultiPolygon") {
        for (const poly of geometry.coordinates) {
            total += ringArea(poly[0]);
        }
    }
    return total;
}

// Ray-casting point-in-polygon test
function pointInRing(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const xi = ring[i][0], yi = ring[i][1];
        const xj = ring[j][0], yj = ring[j][1];
        if ((yi > lat) !== (yj > lat) &&
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) {
            inside = !inside;
        }
    }
    return inside;
}

function pointInGeometry(lon, lat, geometry) {
    if (geometry.type === "Polygon") {
        // Must be inside outer ring and outside all holes
        if (!pointInRing(lon, lat, geometry.coordinates[0])) return false;
        for (let i = 1; i < geometry.coordinates.length; i++) {
            if (pointInRing(lon, lat, geometry.coordinates[i])) return false;
        }
        return true;
    } else if (geometry.type === "MultiPolygon") {
        for (const poly of geometry.coordinates) {
            if (!pointInRing(lon, lat, poly[0])) continue;
            let inHole = false;
            for (let i = 1; i < poly.length; i++) {
                if (pointInRing(lon, lat, poly[i])) { inHole = true; break; }
            }
            if (!inHole) return true;
        }
    }
    return false;
}

function buildInfoHtml(props) {
    const unit = props.FIRST_Unit || "";
    const name = props.Name || "";
    const era = props.FIRST_Un_1 || "";
    const type = props.FIRST_Un_2 || "";
    const desc = props.Desc || "";
    const area = props.Area_km2 || "";
    const color = props.Color || "#888";
    return `<div style="font-family:sans-serif;color:#ddd;background:#1a1a2e;padding:8px;border-radius:4px;">
      <div style="display:inline-block;width:14px;height:14px;background:${color};border:1px solid #555;vertical-align:middle;margin-right:6px;border-radius:2px;"></div>
      <strong>${unit}</strong> — ${name}<br/>
      <b>Era:</b> ${era}<br/><b>Type:</b> ${type}<br/><b>Area:</b> ${area} km²
      <p style="margin:6px 0 0;color:#aaa;">${desc}</p>
    </div>`;
}

export default function GeoLayers({ viewer, layers }) {
    const primitivesRef = useRef({}); // era -> Primitive (outlines only)
    const featureMapRef = useRef(new Map()); // id -> properties
    const featuresRef = useRef([]); // [{id, geometry, bbox, era}] for hit testing
    const idToInstancesRef = useRef(new Map()); // featureId -> [{primitive, instanceId}]
    const hoveredIdRef = useRef(null);
    const selectedIdRef = useRef(null);
    const handlerRef = useRef(null);
    const selectedEntityRef = useRef(null);
    const layersRef = useRef(layers);
    layersRef.current = layers;

    // Find the smallest feature that contains a lon/lat point
    function findFeatureAt(lon, lat) {
        let bestId = null;
        let bestArea = Infinity;
        for (const feat of featuresRef.current) {
            // Quick bbox rejection
            if (lon < feat.bbox[0] || lon > feat.bbox[2] ||
                lat < feat.bbox[1] || lat > feat.bbox[3]) continue;
            // Check era visibility
            if (layersRef.current[feat.era] === false) continue;
            // Skip if area is already larger than current best
            if (feat.area >= bestArea) continue;
            if (pointInGeometry(lon, lat, feat.geometry)) {
                bestId = feat.id;
                bestArea = feat.area;
            }
        }
        return bestId;
    }

    // Convert screen position to lon/lat, then find feature
    function hitTest(screenPos) {
        const cartesian = viewer.camera.pickEllipsoid(
            screenPos, viewer.scene.globe.ellipsoid
        );
        if (!cartesian) return null;
        const carto = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(carto.longitude);
        const lat = Cesium.Math.toDegrees(carto.latitude);
        return findFeatureAt(lon, lat);
    }

    function setHighlight(id, on) {
        const entries = idToInstancesRef.current.get(id);
        if (!entries) return;
        const attr = on ? HIGHLIGHT_ATTR : OUTLINE_ATTR;
        for (const { primitive, instanceId } of entries) {
            try {
                const a = primitive.getGeometryInstanceAttributes(instanceId);
                if (a) a.color = attr.value;
            } catch { }
        }
    }

    function setSelectionColor(id, color) {
        const entries = idToInstancesRef.current.get(id);
        if (!entries) return;
        const attr = Cesium.ColorGeometryInstanceAttribute.fromColor(color);
        for (const { primitive, instanceId } of entries) {
            try {
                const a = primitive.getGeometryInstanceAttributes(instanceId);
                if (a) a.color = attr.value;
            } catch { }
        }
    }

    function clearSelection() {
        const oldSel = selectedIdRef.current;
        if (oldSel != null) {
            setHighlight(oldSel, false);
            selectedIdRef.current = null;
        }
    }

    useEffect(() => {
        if (!viewer) return;
        let cancelled = false;

        const selectedEntity = new Cesium.Entity();
        selectedEntityRef.current = selectedEntity;

        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

        // Click handler
        handler.setInputAction((click) => {
            // Clear previous selection
            clearSelection();

            const id = hitTest(click.position);
            if (id != null && featureMapRef.current.has(id)) {
                const props = featureMapRef.current.get(id);
                selectedEntity.name = `${props.FIRST_Unit || ""} — ${props.Name || ""}`;
                selectedEntity.description = buildInfoHtml(props);
                viewer.selectedEntity = selectedEntity;

                // Highlight with era color
                const era = props.FIRST_Un_1 || "";
                const hex = ERA_LABEL_COLORS[era] || "#ffffff";
                const selColor = Cesium.Color.fromCssColorString(hex);
                setSelectionColor(id, selColor);
                selectedIdRef.current = id;
            } else {
                viewer.selectedEntity = undefined;
            }
            viewer.scene.requestRender();
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        // Hover handler
        handler.setInputAction((movement) => {
            const newId = hitTest(movement.endPosition);
            const oldId = hoveredIdRef.current;
            if (newId === oldId) return;
            // Don't un-highlight if it's the selected feature
            if (oldId != null && oldId !== selectedIdRef.current) setHighlight(oldId, false);
            if (newId != null && newId !== selectedIdRef.current) setHighlight(newId, true);
            if (newId !== oldId) viewer.scene.requestRender();
            hoveredIdRef.current = newId;
        }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

        handlerRef.current = handler;

        // Defer loading so the globe + tiles render first
        const loadTimeout = setTimeout(() => {
            fetch("/data/geo_units.json")
                .then((r) => r.json())
                .then(async (geojson) => {
                    if (cancelled) return;

                    // Assign IDs, compute bboxes, group by era
                    const byEra = {};
                    for (const era of ERA_ORDER) byEra[era] = [];
                    let nextId = 0;
                    for (const feat of geojson.features) {
                        const id = nextId++;
                        featureMapRef.current.set(id, feat.properties);
                        feat._id = id;
                        const era = feat.properties?.FIRST_Un_1;
                        if (era && byEra[era]) byEra[era].push(feat);

                        // Compute bbox for fast rejection
                        let minLon = Infinity, minLat = Infinity;
                        let maxLon = -Infinity, maxLat = -Infinity;
                        const rings = getRings(feat.geometry);
                        for (const ring of rings) {
                            for (const [lon, lat] of ring) {
                                if (lon < minLon) minLon = lon;
                                if (lon > maxLon) maxLon = lon;
                                if (lat < minLat) minLat = lat;
                                if (lat > maxLat) maxLat = lat;
                            }
                        }
                        featuresRef.current.push({
                            id, era, geometry: feat.geometry,
                            bbox: [minLon, minLat, maxLon, maxLat],
                            area: polygonArea(feat.geometry),
                        });
                    }

                    // Build outline primitives per era (no fill primitives)
                    for (const era of ERA_ORDER) {
                        if (cancelled) return;

                        const instances = [];
                        for (const feat of byEra[era]) {
                            const rings = getRings(feat.geometry);
                            for (const ring of rings) {
                                if (ring.length < 2) continue;
                                const positions = ringToPositions(ring);
                                instances.push(
                                    new Cesium.GeometryInstance({
                                        geometry: new Cesium.PolylineGeometry({
                                            positions,
                                            width: 1.0,
                                        }),
                                        id: feat._id,
                                        attributes: {
                                            color: Cesium.ColorGeometryInstanceAttribute.fromColor(OUTLINE_COLOR),
                                        },
                                    })
                                );
                            }
                        }

                        if (instances.length === 0) continue;

                        const primitive = new Cesium.Primitive({
                            geometryInstances: instances,
                            appearance: new Cesium.PolylineColorAppearance(),
                            asynchronous: true,
                        });

                        primitive.show = layersRef.current[era] !== false;
                        viewer.scene.primitives.add(primitive);
                        primitivesRef.current[era] = primitive;

                        // Register instances for hover highlight
                        for (const inst of instances) {
                            const fid = inst.id;
                            if (!idToInstancesRef.current.has(fid)) {
                                idToInstancesRef.current.set(fid, []);
                            }
                            idToInstancesRef.current.get(fid).push({
                                primitive,
                                instanceId: fid,
                            });
                        }

                        // Yield so the globe can render between era batches
                        await new Promise((r) => setTimeout(r, 0));
                    }
                });
        }, 500);

        return () => {
            cancelled = true;
            clearTimeout(loadTimeout);
            handler.destroy();
            for (const prim of Object.values(primitivesRef.current)) {
                if (viewer && !viewer.isDestroyed()) {
                    viewer.scene.primitives.remove(prim);
                }
            }
            primitivesRef.current = {};
            featureMapRef.current.clear();
            idToInstancesRef.current.clear();
            featuresRef.current = [];
            hoveredIdRef.current = null;
        };
    }, [viewer]);

    useEffect(() => {
        for (const [era, primitive] of Object.entries(primitivesRef.current)) {
            primitive.show = layers[era] !== false;
        }
        if (viewer && !viewer.isDestroyed()) viewer.scene.requestRender();
    }, [layers]);

    return null;
}
