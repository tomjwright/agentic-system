"use client";

import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";

// OneMap's basemap. Its terms require the OneMap logo and this attribution.
// https://www.onemap.gov.sg/docs/maps/
const TILES = "https://www.onemap.gov.sg/maps/tiles/Default/{z}/{x}/{y}.png";
const ATTRIBUTION =
  '<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" alt="" style="height:20px;width:20px"/>' +
  '&nbsp;<a href="https://www.onemap.gov.sg/" target="_blank" rel="noopener noreferrer">OneMap</a>' +
  '&nbsp;&copy;&nbsp;contributors&nbsp;&#124;&nbsp;' +
  '<a href="https://www.sla.gov.sg/" target="_blank" rel="noopener noreferrer">Singapore Land Authority</a>';
const SINGAPORE_CENTRE: [number, number] = [1.3521, 103.8198]; // [latitude, longitude] for Leaflet
const TILE_BOUNDS: [[number, number], [number, number]] = [
  [1.16, 103.502],
  [1.56073, 104.11475],
];

type Props = {
  point: [number, number] | null; // [longitude, latitude], as the API sends it
  onPick: (point: [number, number]) => void;
};

function ClickToPick({ onPick }: { onPick: Props["onPick"] }) {
  useMapEvents({
    click(event) {
      onPick([event.latlng.lng, event.latlng.lat]);
    },
  });
  return null;
}

function ShowPoint({ point }: { point: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView([point[1], point[0]], Math.max(map.getZoom(), 16));
  }, [map, point]);
  return <CircleMarker center={[point[1], point[0]]} radius={10} pathOptions={{ color: "#c2185b" }} />;
}

export default function StartMap({ point, onPick }: Props) {
  return (
    <MapContainer
      center={SINGAPORE_CENTRE}
      zoom={12}
      minZoom={11}
      maxZoom={18}
      maxBounds={TILE_BOUNDS}
      className="map"
    >
      <TileLayer url={TILES} attribution={ATTRIBUTION} maxZoom={19} detectRetina />
      <ClickToPick onPick={onPick} />
      {point && <ShowPoint point={point} />}
    </MapContainer>
  );
}
