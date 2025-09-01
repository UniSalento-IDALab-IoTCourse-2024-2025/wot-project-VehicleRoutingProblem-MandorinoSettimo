from datetime import timedelta

class SolutionPrinter:
    def __init__(self, manager, routing, assignment, customers, vehicles):
        self.manager = manager
        self.routing = routing
        self.assignment = assignment
        self.customers = customers
        self.vehicles = vehicles

        self.capacity_dimension = routing.GetDimensionOrDie('Capacity')
        self.time_dimension = routing.GetDimensionOrDie('Time')

    def get_dropped_nodes(self):
        dropped = []
        for node_index in range(self.routing.Size()):
            if self.assignment.Value(self.routing.NextVar(node_index)) == node_index:
                dropped.append(str(self.manager.IndexToNode(node_index)))
        return dropped

    def get_vehicle_routes(self):
        vehicle_routes = {}
        for vehicle_id in range(self.vehicles.number):
            index = self.routing.Start(vehicle_id)
            route = []

            while not self.routing.IsEnd(index):
                node = self.manager.IndexToNode(index)
                route.append(self.customers.customers[node])
                index = self.assignment.Value(self.routing.NextVar(index))

            # Add the end node
            end_node = self.manager.IndexToNode(index)
            route.append(self.customers.customers[end_node])

            vehicle_routes[vehicle_id] = route
        return vehicle_routes

    def print(self):
        print(f'Objective value: {self.assignment.ObjectiveValue()}')
        print()

        for vehicle_id in range(self.vehicles.number):
            index = self.routing.Start(vehicle_id)
            if self.routing.IsEnd(self.assignment.Value(self.routing.NextVar(index))):
                print(f'Route for vehicle {vehicle_id}: Empty\n')
                continue

            route_str = f'Route for vehicle {vehicle_id}:\n'
            while not self.routing.IsEnd(index):
                node = self.manager.IndexToNode(index)
                load = self.assignment.Value(self.capacity_dimension.CumulVar(index))
                time_var = self.time_dimension.CumulVar(index)
                tmin = timedelta(seconds=self.assignment.Min(time_var))
                tmax = timedelta(seconds=self.assignment.Max(time_var))

                route_str += f' {node} Load({load}) Time({tmin}, {tmax}) ->'
                index = self.assignment.Value(self.routing.NextVar(index))

            end_node = self.manager.IndexToNode(index)
            route_str += f' {end_node} End\n'
            print(route_str)

        dropped = self.get_dropped_nodes()
        print(f'Dropped nodes: {", ".join(dropped)}')

    def get_solution_json(self):
        vehicle_routes = self.get_vehicle_routes()
        solution = {"path": [], "assignedOrders": []}

        # Mappa ID nodo (stringa) → index interno (int)
        id_to_index = self.customers.node_id_to_index


        # Mappatura da coppia (pickup_idx, delivery_idx) → order_id
        node_to_order = {}
        for order in self.customers.orders:
            pickup_idx = id_to_index[order.pickup_node_id]
            delivery_idx = id_to_index[order.delivery_node_id]
            node_to_order[(pickup_idx, delivery_idx)] = {
                "order_id": order.id,
                "pickup_id": pickup_idx,
                "delivery_id": delivery_idx
            }

        for vehicle_id, route in vehicle_routes.items():
            real_id = self.vehicles.ids[vehicle_id]
            stops = []

            for node in route:
                stops.append({
                    "nodeIndex": node.index,
                    "lat": node.lat,
                    "lon": node.lon
                })

            # Verifica quali ordini sono stati rispettati da questo veicolo
            indices = [n.index for n in route]
            for pickup, delivery in self.customers.pdp_pairs:
                if pickup in indices and delivery in indices:
                    entry = node_to_order.get((pickup, delivery))
                    if entry:
                        solution["assignedOrders"].append({
                            "orderId": entry["order_id"],
                            "pickupNodeId": self.customers.index_to_node_id[entry["pickup_id"]],
                            "deliveryNodeId": self.customers.index_to_node_id[entry["delivery_id"]],
                            "assignedVehicleId": real_id
                        })

            solution["path"].append({
                "vehicleId": real_id,
                "route": stops
            })

        return solution

