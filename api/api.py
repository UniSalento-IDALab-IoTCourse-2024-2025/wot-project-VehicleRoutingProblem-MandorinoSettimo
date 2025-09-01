from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from api.models import OptimizeRequest, NodeType
from models.Customers import Customers
from models.Vehicles import Vehicles
from solver.route_exporter import RouteExporter, build_route_for_export
from solver.routing_model_builder import RoutingModelBuilder
from solver.solution_printer import SolutionPrinter


app = FastAPI()
@app.post("/optimize")
def optimize(request: OptimizeRequest):
    # 🔁 Mapping da string ID → index
    node_id_map = {str(node.id): idx for idx, node in enumerate(request.nodes)}
    pdp_pairs = []
    for order in request.orders:
        pickup_id = str(order.pickup_node_id)
        delivery_id = str(order.delivery_node_id)
        if pickup_id in node_id_map and delivery_id in node_id_map:
            pdp_pairs.append((node_id_map[pickup_id], node_id_map[delivery_id]))
        else:
            return {"error": f"ID non trovato in mapping: {pickup_id} o {delivery_id}"}

    customers = Customers.from_nodes_and_orders(request.nodes, request.orders)
    customers.pdp_pairs = pdp_pairs  # 👈 assegniamo le coppie costruite correttamente
    vehicles = Vehicles.from_json(request.vehicles)

    # Ricerca del depot
    depot_idxs = [i for i, node in enumerate(request.nodes) if node.type == NodeType.DEPOT]
    if not depot_idxs:
        return {"error": "Manca un nodo di tipo depot"}
    depot = depot_idxs[0]
    vehicles.starts = [depot] * vehicles.number
    vehicles.ends = [depot] * vehicles.number
    customers.zero_depot_demands(depot)

    # Validazione
    from solver.pdp_validator import validate_pdp
    valid, _ = validate_pdp(customers, vehicles)
    if not valid:
        return {"error": "Configurazione PDP non valida"}

    # Costruzione modello e risoluzione
    builder = RoutingModelBuilder(customers, vehicles)
    manager, routing = builder.get_model()
    params = builder.get_default_parameters()
    assignment = routing.SolveWithParameters(params)

    if not assignment:
        return {"error": "Nessuna soluzione trovata"}

    printer = SolutionPrinter(manager, routing, assignment, customers, vehicles)

    vehicle_routes = printer.get_vehicle_routes()
    # Costruisci la lista route con vehicle_id per GraphHopper
    route = build_route_for_export(vehicle_routes, customers)

    # Fetch tratte da GraphHopper
    exporter = RouteExporter(route, vehicle_ids=vehicles.ids)
    exporter.fetch_routes()

    # Esporta (se vuoi salvarli su disco, puoi commentare se no)
    exporter.export_json("routes.json")
    exporter.export_geojson("routes.geojson")
    exporter.export_distances_csv("route_metrics.csv")
    exporter.visualize_folium("percorso_reale.html")
    printer.print()
    return {
        "solution": printer.get_solution_json(),
        "geoRoutes": exporter.routes_data  # con segmenti geometrici per mappa
    }


