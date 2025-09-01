from datetime import timedelta

from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2


class RoutingModelBuilder:
    def __init__(self, customers, vehicles, penalty=9999999):
        self.customers = customers
        self.vehicles = vehicles
        self.penalty = penalty

        # 1. Manager
        self.manager = pywrapcp.RoutingIndexManager(
            customers.number,
            vehicles.number,
            vehicles.starts,
            vehicles.ends
        )
        customers.set_manager(self.manager)
        #customers.make_real_distance_time_matrix()
        customers.make_distance_mat(method='haversine')

        # 2. Modello
        self.model_params = pywrapcp.DefaultRoutingModelParameters()
        self.routing = pywrapcp.RoutingModel(self.manager, self.model_params)

        # 3. Callback e vincoli
        self._register_callbacks()
        self._set_costs()
        self._add_capacity_dimension()
        self._add_time_dimension()
        self._add_disjunctions()
        self._add_pickup_delivery_constraints()

    def _register_callbacks(self):
        print("🔧 Registrazione callback...")

        # distanza
        self.dist_fn_index = self.routing.RegisterTransitCallback(
            self.customers.return_dist_callback()
        )

        # domanda
        self.demand_fn_index = self.routing.RegisterUnaryTransitCallback(
            self.customers.return_dem_callback()
        )

        # tempo = transito + servizio
        service_time_fn = self.customers.make_service_time_call_callback()
        transit_time_fn = self.customers.make_transit_time_callback()

        # FIX: usa closure corretta senza 'self' nel signature
        def total_time_fn(from_index, to_index):
            try:
                # Salta se indici speciali (ORTools li usa internamente)
                if from_index < 0 or to_index < 0 or \
                        from_index >= self.routing.Size() or to_index >= self.routing.Size():
                    return 0

                if self.routing.IsStart(from_index) or self.routing.IsEnd(to_index):
                    return 0

                from_node = self.manager.IndexToNode(from_index)
                to_node = self.manager.IndexToNode(to_index)

                service = self.customers.customers[from_node].demand * self.customers.service_time_per_dem
                speed = getattr(self.vehicles, "speed_kmph", 30)  # valore di fallback
                travel = self.customers.distmat[from_node][to_node] / (speed / 3600)
                return int(service + travel)
            except Exception as e:
                print(f"❌ Errore nella total_time_fn: {e}")
                import traceback
                traceback.print_exc()
                return 0

        self.time_fn_index = self.routing.RegisterTransitCallback(total_time_fn)

    def _set_costs(self):
        self.routing.SetArcCostEvaluatorOfAllVehicles(self.dist_fn_index)
        for v in self.vehicles.vehicles:
            self.routing.SetFixedCostOfVehicle(int(v.cost), int(v.index))

    def _add_capacity_dimension(self):
        self.routing.AddDimensionWithVehicleCapacity(
            self.demand_fn_index,
            0,  # no slack
            [v.capacity for v in self.vehicles.vehicles],
            True,
            "Capacity"
        )

    def _add_time_dimension(self):
        if not hasattr(self, "time_fn_index"):
            raise RuntimeError("❌ time_fn_index non definito! Callback 'total_time_fn' mancante.")

        self.routing.AddDimension(
            self.time_fn_index,
            self.customers.time_horizon,
            self.customers.time_horizon,
            True,
            "Time"
        )

        time_dimension = self.routing.GetDimensionOrDie("Time")
        for cust in self.customers.customers:
            if cust.tw_open is None or cust.tw_close is None:
                continue

            index = self.manager.NodeToIndex(cust.index)

            if isinstance(cust.tw_open, timedelta):
                o = int(cust.tw_open.total_seconds())
            else:
                o = int(cust.tw_open)

            if isinstance(cust.tw_close, timedelta):
                c = int(cust.tw_close.total_seconds())
            else:
                c = int(cust.tw_close)

            print(f"⏰ Nodo {cust.index} → finestra: {o} - {c} sec")

            time_dimension.CumulVar(index).SetRange(o, c)

    def _add_disjunctions(self):
        pdp_nodes = set()
        if hasattr(self.customers, 'pdp_pairs'):
            for p, d in self.customers.pdp_pairs:
                pdp_nodes.add(p)
                pdp_nodes.add(d)

        non_depot = set(range(self.customers.number))
        non_depot.difference_update(self.vehicles.starts)
        non_depot.difference_update(self.vehicles.ends)
        non_depot.difference_update(pdp_nodes)

        for c in non_depot:
            self.routing.AddDisjunction([self.manager.NodeToIndex(c)], self.penalty)

    def _add_pickup_delivery_constraints(self):
        if not hasattr(self.customers, 'pdp_pairs'):
            print("⚠️ Nessuna coppia PDP trovata.")
            return

        print("📦 Aggiunta vincoli pickup & delivery...")
        time_dimension = self.routing.GetDimensionOrDie("Time")

        for pickup, delivery in self.customers.pdp_pairs:
            print(f"  → PDP: {pickup} → {delivery}")
            pickup_index = self.manager.NodeToIndex(pickup)
            delivery_index = self.manager.NodeToIndex(delivery)

            self.routing.AddPickupAndDelivery(pickup_index, delivery_index)
            self.routing.solver().Add(
                self.routing.VehicleVar(pickup_index) == self.routing.VehicleVar(delivery_index)
            )
            self.routing.solver().Add(
                time_dimension.CumulVar(pickup_index) <= time_dimension.CumulVar(delivery_index)
            )

    def get_model(self):
        return self.manager, self.routing

    def get_default_parameters(self):
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        parameters.time_limit.seconds = 10
        parameters.use_full_propagation = True
        return parameters