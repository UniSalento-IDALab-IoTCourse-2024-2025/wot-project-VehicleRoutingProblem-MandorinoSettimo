import os
import numpy as np
from matplotlib import pyplot as plt
from collections import namedtuple
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
from datetime import datetime, timedelta
import pandas as pd


class Customers():

    def __init__(self,
                 extents=None,
                 center=(53.381393, -1.474611),
                 box_size=10,
                 num_stops=100,
                 min_demand=0,
                 max_demand=25,
                 min_tw=1,
                 max_tw=5,
                 prebuilt_customers=None):

        if prebuilt_customers is not None:
            self.customers = prebuilt_customers
            self.number = len(prebuilt_customers)
            self.time_horizon = 24 * 3600
            self.service_time_per_dem = 60

            # Calcola centro geografico
            lats = [c.lat for c in prebuilt_customers]
            lons = [c.lon for c in prebuilt_customers]
            avg_lat = sum(lats) / len(lats)
            avg_lon = sum(lons) / len(lons)
            Location = namedtuple('Location', ['lat', 'lon'])
            self.center = Location(avg_lat, avg_lon)
            return

        # === COSTRUZIONE RANDOM (se non si usa prebuilt) ===
        self.number = num_stops
        Location = namedtuple('Location', ['lat', 'lon'])

        if extents is not None:
            self.extents = extents
            self.center = Location(
                extents['urcrnrlat'] - 0.5 * (extents['urcrnrlat'] - extents['llcrnrlat']),
                extents['urcrnrlon'] - 0.5 * (extents['urcrnrlon'] - extents['llcrnrlon']))
        else:
            (clat, clon) = self.center = Location(center[0], center[1])
            rad_earth = 6367  # km
            circ_earth = np.pi * rad_earth
            self.extents = {
                'llcrnrlon': (clon - 180 * box_size / (circ_earth * np.cos(np.deg2rad(clat)))),
                'llcrnrlat': clat - 180 * box_size / circ_earth,
                'urcrnrlon': (clon + 180 * box_size / (circ_earth * np.cos(np.deg2rad(clat)))),
                'urcrnrlat': clat + 180 * box_size / circ_earth
            }

        stops = np.array(range(0, num_stops))
        stdv = 6

        lats = (self.extents['llcrnrlat'] + np.random.randn(num_stops) *
                (self.extents['urcrnrlat'] - self.extents['llcrnrlat']) / stdv)
        lons = (self.extents['llcrnrlon'] + np.random.randn(num_stops) *
                (self.extents['urcrnrlon'] - self.extents['llcrnrlon']) / stdv)

        if min_demand < max_demand:
            demands = np.random.randint(min_demand, max_demand, num_stops)
        else:
            demands = np.zeros(num_stops, dtype=int)

        self.time_horizon = 24 * 3600

        time_windows = np.random.randint(min_tw * 3600, max_tw * 3600, num_stops)
        latest_time = self.time_horizon - time_windows
        start_times = [timedelta(seconds=np.random.randint(0, latest_time[i])) for i in range(num_stops)]
        stop_times = [start + timedelta(seconds=int(w)) for start, w in zip(start_times, time_windows)]

        Customer = namedtuple('Customer', ['index', 'demand', 'lat', 'lon', 'tw_open', 'tw_close'])

        self.customers = [
            Customer(idx, dem, lat, lon, open_t, close_t)
            for idx, dem, lat, lon, open_t, close_t in zip(stops, demands, lats, lons, start_times, stop_times)
        ]

        self.service_time_per_dem = 60

    def set_manager(self, manager):
        self.manager = manager

    def make_real_distance_time_matrix(self):
        import requests
        import json

        coords = [[c.lon, c.lat] for c in self.customers]  # [lon, lat] come richiesto
        url = "http://localhost:8989/matrix"
        #params = {"key": api_key}
        payload = {
            "from_points": coords,
            "to_points": coords,
            "out_arrays": ["distances", "times"],
            "profile": "car"
        }

        print("📡 Invio richiesta a GraphHopper")
        #print(json.dumps(payload, indent=2))  # stampa JSON formattato

        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            result = response.json()
            self.distmat = result["distances"]
            self.timemat = result["times"]
            print("✅ Matrici reali caricate correttamente da GraphHopper.")
        except Exception as e:
            print(f"❌ Errore durante la chiamata a GraphHopper: {e}")
            n = len(coords)
            self.distmat = [[0 for _ in range(n)] for _ in range(n)]
            self.timemat = [[0 for _ in range(n)] for _ in range(n)]

    @classmethod
    def from_csv(cls, path):
        import pandas as pd
        df = pd.read_csv(path)

        number = len(df)
        time_horizon = 24 * 3600
        Customer = namedtuple('Customer', ['index', 'demand', 'lat', 'lon', 'tw_open', 'tw_close'])

        customers = []
        pickup_dict = {}
        delivery_dict = {}

        for idx, row in df.iterrows():
            demand = int(row['demand'])
            lat = float(row['lat'])
            lon = float(row['lon'])

            # Finestra temporale dal CSV, fallback controllato
            try:
                open_sec = int(row['tw_open'])
                close_sec = int(row['tw_close'])
                assert 0 <= open_sec <= close_sec <= time_horizon, \
                    f"Time window non valida per idx={idx}: {open_sec} → {close_sec}"
                assert 0 <= open_sec <= close_sec <= time_horizon
                tw_open = timedelta(seconds=open_sec)
                tw_close = timedelta(seconds=close_sec)
            except:
                # Fallback: finestra 00:00 - 24:00
                tw_open = timedelta(seconds=0)
                tw_close = timedelta(seconds=time_horizon)

            customers.append(Customer(idx, demand, lat, lon, tw_open, tw_close))

            # Se presenti colonne PDP
            if 'type' in row and 'pair_id' in row and not pd.isna(row['type']) and not pd.isna(row['pair_id']):
                pair_id = int(row['pair_id'])
                if row['type'].strip().lower() == 'pickup':
                    pickup_dict[pair_id] = idx
                elif row['type'].strip().lower() == 'delivery':
                    delivery_dict[pair_id] = idx

        # Crea le coppie PDP
        pdp_pairs = []
        for pair_id in pickup_dict:
            if pair_id in delivery_dict:
                pdp_pairs.append((pickup_dict[pair_id], delivery_dict[pair_id]))

        obj = cls(prebuilt_customers=customers)
        obj.pdp_pairs = pdp_pairs
        obj.pdp_pairs_flat = list(set(i for pair in pdp_pairs for i in pair))
        return obj

    def add_pickup_delivery_requests(self, num_pairs=10, min_qty=5, max_qty=15):
        self.pdp_pairs = []

        used_indexes = set()
        depot_indexes = set(getattr(self, "used_as_depots", []))

        attempts = 0
        max_attempts = 500  # Evita loop infiniti

        now = timedelta(seconds=0)
        end = timedelta(seconds=self.time_horizon)

        while len(self.pdp_pairs) < num_pairs and attempts < max_attempts:
            pickup = np.random.randint(0, self.number)
            delivery = np.random.randint(0, self.number)

            if pickup == delivery:
                attempts += 1
                continue
            if pickup in used_indexes or delivery in used_indexes:
                attempts += 1
                continue
            if pickup in depot_indexes or delivery in depot_indexes:
                attempts += 1
                continue

            qty = np.random.randint(min_qty, max_qty + 1)
            self.pdp_pairs.append((pickup, delivery))

            # Assegna quantità
            self.customers[pickup] = self.customers[pickup]._replace(demand=qty)
            self.customers[delivery] = self.customers[delivery]._replace(demand=-qty)

            # Imposta finestre temporali larghe per sicurezza
            self.customers[pickup] = self.customers[pickup]._replace(tw_open=now, tw_close=end)
            self.customers[delivery] = self.customers[delivery]._replace(tw_open=now + timedelta(hours=2), tw_close=end)

            used_indexes.add(pickup)
            used_indexes.add(delivery)

            attempts += 1

        if len(self.pdp_pairs) < num_pairs:
            print(f"⚠️ Solo {len(self.pdp_pairs)} coppie PDP create su {num_pairs} richieste.")

        # Salva anche lista flat per analisi/debug
        self.pdp_pairs_flat = list(set(i for pair in self.pdp_pairs for i in pair))

    def central_start_node(self, invert=False):

        num_nodes = len(self.customers)
        dist = np.empty((num_nodes, 1))
        for idx_to in range(num_nodes):
            dist[idx_to] = self._haversine(self.center.lon, self.center.lat,
                                           self.customers[idx_to].lon,
                                           self.customers[idx_to].lat)
        furthest = np.max(dist)

        if invert:
            prob = dist * 1.0 / sum(dist)
        else:
            prob = (furthest - dist * 1.0) / sum(furthest - dist)
        indexes = np.array([range(num_nodes)])
        start_node = np.random.choice(
            indexes.flatten(), size=1, replace=True, p=prob.flatten())
        return start_node[0]

    def make_distance_mat(self, method='haversine'):
        if hasattr(self, 'distmat') and self.distmat is not None:
            return self.distmat  # evita ricalcoli

        self.distmat = np.zeros((self.number, self.number))
        methods = {'haversine': self._haversine}
        assert (method in methods)

        for frm_idx in range(self.number):
            for to_idx in range(self.number):
                if frm_idx != to_idx:
                    frm_c = self.customers[frm_idx]
                    to_c = self.customers[to_idx]
                    self.distmat[frm_idx, to_idx] = self._haversine(
                        frm_c.lon, frm_c.lat, to_c.lon, to_c.lat)
        return self.distmat

    def _haversine(self, lon1, lat1, lon2, lat2):

        # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])

        # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = (np.sin(dlat / 2)**2 +
             np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2)
        c = 2 * np.arcsin(np.sqrt(a))

        # 6367 km is the radius of the Earth
        km = 6367 * c
        return km

    def get_total_demand(self):
        """
        Return the total demand of all customers.
        """
        return (sum([c.demand for c in self.customers]))

    def return_dist_callback(self):
        def distance_callback(from_index, to_index):
            try:
                from_node = self.manager.IndexToNode(from_index)
                to_node = self.manager.IndexToNode(to_index)
                return int(self.distmat[from_node][to_node])
            except Exception as e:
                print(f"❌ Errore in distance_callback: {e}")
                return 0

        return distance_callback

    def return_dem_callback(self):
        def dem_return(from_index):
            try:
                from_node = self.manager.IndexToNode(from_index)
                if from_node < 0 or from_node >= len(self.customers):
                    return 0
                return self.customers[from_node].demand
            except Exception as e:
                print(f"❌ Errore in dem_return: {e}")
                import traceback
                traceback.print_exc()
                return 0

        return dem_return

    def zero_depot_demands(self, depot):

        start_depot = self.customers[depot]
        self.customers[depot] = start_depot._replace(
            demand=0, tw_open=None, tw_close=None)

    def make_service_time_call_callback(self):
        def service_time_return(from_node, to_node):
            try:
                return self.customers[from_node].demand * self.service_time_per_dem
            except Exception as e:
                print(f"❌ Errore nella callback tempo di servizio: {e}")
                return 0

        return service_time_return

    def make_transit_time_callback(self, speed_kmph=40):


        def transit_time_return(a, b):
            return (self.distmat[a][b] / (speed_kmph * 1.0 / 60**2))

        return transit_time_return

    @classmethod
    def from_nodes_and_orders(cls, nodes, orders):
        """
        Converte nodes + orders in una lista di Customer usabile dall'algoritmo.
        """
        Customer = namedtuple("Customer", ['index', 'demand', 'lat', 'lon', 'tw_open', 'tw_close'])
        customer_list = []
        id_to_index = {}

        for idx, node in enumerate(nodes):
            id_to_index[node.id] = idx
            # default: nessuna domanda, finestra piena
            demand = 0
            tw_open = timedelta(seconds=0)
            tw_close = timedelta(seconds=86400)
            customer_list.append(Customer(idx, demand, node.lat, node.lon, tw_open, tw_close))

        # Ora aggiorna pickup/delivery
        for order in orders:
            pickup_idx = id_to_index[order.pickup_node_id]
            delivery_idx = id_to_index[order.delivery_node_id]

            customer_list[pickup_idx] = customer_list[pickup_idx]._replace(
                demand=order.quantity,
                tw_open=timedelta(seconds=order.tw_open),
                tw_close=timedelta(seconds=order.tw_close)
            )
            customer_list[delivery_idx] = customer_list[delivery_idx]._replace(
                demand=-order.quantity,
                tw_open=timedelta(seconds=order.tw_open + 3600),  # +1 ora
                tw_close=timedelta(seconds=order.tw_close + 3600)  # +1 ora
            )

        obj = cls(prebuilt_customers=customer_list)
        obj.pdp_pairs = [(id_to_index[o.pickup_node_id], id_to_index[o.delivery_node_id]) for o in orders]
        obj.pdp_pairs_flat = list(set(i for pair in obj.pdp_pairs for i in pair))
        obj.orders = orders

        obj.node_id_to_index = id_to_index  # <-- 👈 AGGIUNTA IMPORTANTE
        obj.index_to_node_id = {v: k for k, v in id_to_index.items()}
        obj.index_to_order_id = {i: o.id for i, o in enumerate(orders)}
        # 💡 Imposta time_horizon dinamico basato sul massimo tw_close
        max_tw_close = max(c.tw_close for c in customer_list)
        obj.time_horizon = int(max_tw_close.total_seconds()) + 3600  # buffer di sicurezza

        return obj