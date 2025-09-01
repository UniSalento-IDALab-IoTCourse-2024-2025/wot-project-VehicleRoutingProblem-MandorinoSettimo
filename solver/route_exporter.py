import os
import requests
import json
import time

class RouteExporter:
    def __init__(self, route, vehicle_ids=None, profile="car"):
        self.route = route
        self.vehicle_ids = vehicle_ids or []  # 👈 lista di targhe o ID reali
        self.profile = profile
        self.routes_data = []

    def fetch_routes(self):
        headers = {"Content-Type": "application/json"}

        GH_BASE = os.getenv("GRAPHHOPPER_URL", "http://localhost:8989")  # default per test locale
        ROUTE_URL = f"{GH_BASE}/route"

        for i in range(len(self.route) - 1):
            start = self.route[i]
            end = self.route[i + 1]

            params = {
                "point": [f"{start['lat']},{start['lon']}", f"{end['lat']},{end['lon']}"],
                "profile": self.profile,
                "locale": "it",
                "points_encoded": "false",
                "instructions": "false"
            }

            try:
                resp = requests.get(ROUTE_URL, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                path = data["paths"][0]
                geometry = path["points"]["coordinates"]
                distance_m = path["distance"]
                time_s = int(path["time"] / 1000)

                segment = {
                    "fromNodeIndex": start["index"],
                    "toNodeIndex": end["index"],
                    "fromLabel": start["label"],
                    "toLabel": end["label"],
                    "geometry": geometry,
                    "distanceM": distance_m,
                    "timeS": time_s,
                    "vehicleId": self.vehicle_ids[start["vehicleId"]] if self.vehicle_ids else start["vehicleId"]
                }
                self.routes_data.append(segment)
                time.sleep(0.2)

            except Exception as e:
                print(f"❌ Errore nel calcolo della rotta {start['index']} → {end['index']}: {e}")

    def export_json(self, filepath="routes.json"):
        with open(filepath, "w") as f:
            json.dump(self.routes_data, f, indent=2)
        print(f"✅ Rotte esportate in {filepath}")

    def export_distances_csv(self, filepath="route_metrics.csv"):
        rows = []
        for segment in self.routes_data:
            rows.append({
                "from_index": segment["fromNodeIndex"],
                "to_index": segment["toNodeIndex"],
                "from_label": segment["fromLabel"],
                "to_label": segment["toLabel"],
                "distance_m": segment.get("distanceM"),
                "time_s": segment.get("timeS")
            })

        if not rows:
            print("⚠️ Nessuna distanza da esportare.")
            return

        with open(filepath, mode="w", newline="") as file:
            import csv
            writer = csv.DictWriter(file, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"✅ Distanze e tempi esportati in: {filepath}")

    def get_geojson(self):
        """Restituisce GeoJSON FeatureCollection"""
        features = []
        for segment in self.routes_data:
            feat = {
                "type": "Feature",
                "properties": {
                    "from": segment["fromNodeIndex"],
                    "to": segment["toNodeIndex"],
                    "from_label": segment["fromLabel"],
                    "to_label": segment["toLabel"]
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": segment["geometry"]
                }
            }
            features.append(feat)

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def export_geojson(self, filepath="routes.geojson"):
        geojson = self.get_geojson()
        with open(filepath, "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"✅ GeoJSON esportato in {filepath}")

    def visualize_folium(self, save_path="mappa.html"):
        import folium
        import itertools

        if not self.route:
            print("⚠️ Nessun punto da visualizzare.")
            return

        start_lat = self.route[0]["lat"]
        start_lon = self.route[0]["lon"]
        m = folium.Map(location=[start_lat, start_lon], zoom_start=7)

        # Marker
        for point in self.route:
            folium.Marker(
                location=[point["lat"], point["lon"]],
                popup=f"{point['label']} ({point['index']})",
                icon=folium.Icon(
                    color="blue" if point["label"] == "Depot" else "green" if point["label"] == "Pickup" else "red")
            ).add_to(m)

        # Colori diversi per veicolo
        colors = itertools.cycle(["blue", "red", "green", "purple", "orange", "black", "brown", "pink"])
        vehicle_colors = {}

        for segment in self.routes_data:
            veh = segment.get("vehicleId", "unknown")
            if veh not in vehicle_colors:
                vehicle_colors[veh] = next(colors)

        # Linee per veicolo
        for segment in self.routes_data:
            coords = [[lat, lon] for lon, lat in segment["geometry"]]
            color = vehicle_colors.get(segment.get("vehicleId", "unknown"), "gray")
            folium.PolyLine(coords, color=color, weight=4, opacity=0.7).add_to(m)

        m.save(save_path)
        print(f"✅ Mappa salvata in: {save_path}")


def build_route_for_export(vehicle_routes, customers):
    route = []
    pdp_pairs = getattr(customers, "pdp_pairs", [])

    for vehicle_id, cust_list in vehicle_routes.items():
        for cust in cust_list:
            label = "Depot"
            if any(cust.index == p for p, _ in pdp_pairs):
                label = "Pickup"
            elif any(cust.index == d for _, d in pdp_pairs):
                label = "Delivery"

            route.append({
                "vehicleId": vehicle_id,
                "index": cust.index,
                "lat": cust.lat,
                "lon": cust.lon,
                "label": label
            })

    return route



