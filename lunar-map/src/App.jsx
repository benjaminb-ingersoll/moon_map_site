import { useState } from "react";
import Globe from "./components/Globe";
import GeoLayers from "./components/GeoLayers";
import CoordDisplay from "./components/CoordDisplay";
import Sidebar from "./components/Sidebar";
import { useLayerState } from "./hooks/useLayerState";
import "./App.css";

export default function App() {
  const [viewer, setViewer] = useState(null);
  const { layers, toggleLayer } = useLayerState();

  return (
    <div className="app">
      <Globe onViewerReady={setViewer} />

      <GeoLayers viewer={viewer} layers={layers} />

      <Sidebar layers={layers} toggleLayer={toggleLayer} viewer={viewer} />
      <CoordDisplay viewer={viewer} />
    </div>
  );
}
