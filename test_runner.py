from models.Customers import Customers
from models.Vehicles import Vehicles
from solver.routing_model_builder import RoutingModelBuilder
from solver.solution_printer import SolutionPrinter
from solver.route_plotter import RoutePlotter
from solver.export_solution import export_vehicle_routes_csv, export_dropped_nodes_csv
from solver.pdp_validator import validate_pdp
from datetime import datetime
import os

def run_test(test_id, num_stops=30, num_pairs=5, box_size=10, min_qty=5, max_qty=15, penalty=1_000_000):
    print(f"\n🔍 TEST #{test_id}: {num_stops} clienti, {num_pairs} PDP richieste")

    # 1. Clienti
    customers = Customers(
        num_stops=num_stops,
        min_demand=0,
        max_demand=0,
        box_size=box_size,     # più compatto
        min_tw=1,
        max_tw=4
    )

    # 2. Veicoli omogenei a costo 0 (debug)
    capacities = [25] * 8
    costs = [0] * len(capacities)  # per test: nessun costo fisso

    vehicles = Vehicles(capacity=capacities, cost=costs, speed_kmph=40)
    vehicles.return_starting_callback(customers, sameStartFinish=False)

    # 3. Crea PDP con domande > 0
    customers.add_pickup_delivery_requests(num_pairs=num_pairs, min_qty=min_qty, max_qty=max_qty)
    print("📋 Domande assegnate ai nodi PDP:")
    for idx in customers.pdp_pairs_flat:
        print(f" - Nodo {idx}: demand = {customers.customers[idx].demand}")

    actual_pairs = len(customers.pdp_pairs)
    print(f"✅ PDP create: {actual_pairs}")

    if actual_pairs == 0:
        print("❌ Nessuna coppia PDP generata. Test annullato.")
        return

    # 4. Verifica capacità sufficiente
    total_demand = customers.get_total_demand()
    total_capacity = vehicles.get_total_capacity()
    print(f"📦 Domanda totale: {total_demand}, Capacità veicoli: {total_capacity}")

    if total_demand > total_capacity:
        print("❌ Capacità veicoli insufficiente. Test annullato.")
        return

    # 5. Valida PDP
    valid, errors = validate_pdp(customers, vehicles)
    if not valid:
        print("❌ PDP non valida.")
        for err in errors:
            print("  -", err)
        return

    # 6. Costruisci modello
    print(f"👉 PDP pairs: {customers.pdp_pairs}")
    print(f"🧯 Depot nodes: {vehicles.starts + vehicles.ends}")

    builder = RoutingModelBuilder(customers, vehicles, penalty=penalty)
    manager, routing = builder.get_model()
    parameters = builder.get_default_parameters()

    assignment = routing.SolveWithParameters(parameters)

    # 7. Output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"test{test_id}_{num_stops}_{num_pairs}_{timestamp}"
    os.makedirs("solutions", exist_ok=True)

    if assignment:
        print("✅ Soluzione trovata!")
        printer = SolutionPrinter(manager, routing, assignment, customers, vehicles)
        printer.print()

        vehicle_routes = printer.get_vehicle_routes()
        dropped = printer.get_dropped_nodes()

        export_vehicle_routes_csv(vehicle_routes, manager, routing, assignment, customers,
                                  output_path=f"solutions/{prefix}_solution.csv")
        export_dropped_nodes_csv(dropped, output_path=f"solutions/{prefix}_dropped.csv")

        plotter = RoutePlotter(customers, vehicles)
        plotter.plot(vehicle_routes, save_path=f"solutions/{prefix}_plot.png")
    else:
        print("❌ Nessuna soluzione trovata.")


if __name__ == "__main__":
    # Test parametrizzati
    test_cases = [
        (1, 10, 2),
        (2, 30, 5),
        (3, 60, 10),
        (4, 100, 15),
    ]

    for test_id, num_stops, num_pairs in test_cases:
        run_test(test_id=test_id, num_stops=num_stops, num_pairs=num_pairs)
