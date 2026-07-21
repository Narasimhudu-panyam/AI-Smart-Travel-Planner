import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { geocodeDestination } from "./api";

function firstPlaceWithCoordinates(attractions) {
  return attractions?.find((place) => Number.isFinite(place.latitude) && Number.isFinite(place.longitude)) || null;
}

export default function TripMap({ destination, selectedAttractions = [] }) {
  const selectedPlace = useMemo(() => firstPlaceWithCoordinates(selectedAttractions), [selectedAttractions]);
  const [center, setCenter] = useState(selectedPlace ? [selectedPlace.latitude, selectedPlace.longitude] : null);

  useEffect(() => {
    let active = true;
    if (selectedPlace) {
      setCenter([selectedPlace.latitude, selectedPlace.longitude]);
      return () => { active = false; };
    }
    setCenter(null);
    geocodeDestination(destination)
      .then(({ latitude, longitude }) => {
        if (active) setCenter([latitude, longitude]);
      })
      .catch(() => {
        if (active) setCenter(null);
      });
    return () => { active = false; };
  }, [destination, selectedPlace]);

  if (!center) return <div className="map-box map-loading">Map preview unavailable for this destination.</div>;

  return (
    <div className="map-box map-frame">
      <MapContainer center={center} zoom={selectedPlace ? 13 : 11} scrollWheelZoom={false} aria-label={`Map of ${destination}`}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <CircleMarker center={center} radius={9} pathOptions={{ color: "#155e52", fillColor: "#e57d4e", fillOpacity: 1 }}>
          <Popup>{selectedPlace?.name || destination}</Popup>
        </CircleMarker>
      </MapContainer>
    </div>
  );
}
