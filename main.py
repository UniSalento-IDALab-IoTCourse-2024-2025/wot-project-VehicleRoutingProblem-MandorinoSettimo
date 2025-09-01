from models.Customers import Customers
from models.Vehicles import Vehicles
from solver.route_exporter import RouteExporter, build_route_for_export
from solver.routing_model_builder import RoutingModelBuilder
from solver.solution_printer import SolutionPrinter
from solver.route_plotter import RoutePlotter
from solver.export_solution import export_vehicle_routes_csv, export_dropped_nodes_csv
from solver.pdp_validator import validate_pdp

def main():
    # 1. Inizializza clienti
    customers = Customers.from_csv("dati_clienti.csv")

    # 2. Inizializza veicoli (capacità e costi disomogenei)
    capacities = [20, 20]

    costs = [10, 10]
    vehicles = Vehicles(capacity=capacities, cost=costs, number=2)

    # Evita di usare pickup/delivery come depot
    all_pdp_nodes = set(i for pair in customers.pdp_pairs for i in pair)
    available_nodes = [i for i in range(customers.number) if i not in all_pdp_nodes]

    if not available_nodes:
        raise ValueError("⚠️ Nessun nodo disponibile per essere depot!")

    # Scegli uno disponibile come depot
    depot = available_nodes[0]
    vehicles.starts = [depot] * vehicles.number
    vehicles.ends = [depot] * vehicles.number
    customers.zero_depot_demands(depot)  # azzera domande e TW

    # opzionale: se vuoi aggiornare gli oggetti
    customers.used_as_depots = [depot]

    # 3. Assegna depot ai veicoli (aggiorna anche i depot nei clienti)
    #vehicles.return_starting_callback(customers, sameStartFinish=True)

    # 4. Ora aggiungi le coppie pickup-delivery evitando i depot
    #customers.add_pickup_delivery_requests(num_pairs=1, min_qty=5, max_qty=10)

    # 5. Verifica capacità sufficiente
    assert customers.get_total_demand() < vehicles.get_total_capacity(), "Capacità veicoli insufficiente per domanda clienti!"

    # 6. Valida configurazione PDP prima di costruire il modello
    valid, errors = validate_pdp(customers, vehicles)
    if not valid:
        print("Interrompo: problemi con PDP. Correggi e riprova.")
        exit(1)

    # 7. Crea modello OR-Tools
    builder = RoutingModelBuilder(customers, vehicles)
    manager, routing = builder.get_model()
    parameters = builder.get_default_parameters()

    # 8. Risolvi
    assignment = routing.SolveWithParameters(parameters)

    # 9. Output, esportazione e plotting
    if assignment:
        printer = SolutionPrinter(manager, routing, assignment, customers, vehicles)
        printer.print()

        vehicle_routes = printer.get_vehicle_routes()

        route = build_route_for_export(vehicle_routes, customers)
        # Richiama GraphHopper Directions API e visualizza con Folium
        exporter = RouteExporter(route)
        exporter.fetch_routes()
        exporter.export_json("routes.json")
        exporter.export_geojson()
        exporter.export_distances_csv("route_metrics.csv")
        exporter.visualize_folium(save_path="percorso_reale.html")
        export_vehicle_routes_csv(vehicle_routes, manager, routing, assignment, customers)

        dropped_nodes = printer.get_dropped_nodes()
        export_dropped_nodes_csv(dropped_nodes)

        plotter = RoutePlotter(customers, vehicles)
        plotter.plot(vehicle_routes, save_path="pdp_routes.png", plot_annotations=True)
        print(f"Numero clienti: {customers.number}")
    else:
        print("❌ Nessuna soluzione trovata.")

if __name__ == '__main__':
    main()
