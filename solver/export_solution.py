import csv
from datetime import timedelta

def export_vehicle_routes_csv(vehicle_routes, manager, routing, assignment, customers, output_path="solution.csv"):
    capacity_dim = routing.GetDimensionOrDie("Capacity")
    time_dim = routing.GetDimensionOrDie("Time")

    rows = []
    for veh_id, route in vehicle_routes.items():
        if not route or len(route) < 2:
            continue

        for order_idx, cust in enumerate(route[:-1]):  # exclude last depot
            index = manager.NodeToIndex(cust.index)
            load = assignment.Value(capacity_dim.CumulVar(index))
            tmin = str(timedelta(seconds=assignment.Min(time_dim.CumulVar(index))))
            tmax = str(timedelta(seconds=assignment.Max(time_dim.CumulVar(index))))

            rows.append({
                "vehicle": veh_id,
                "customer_id": cust.index,
                "order": order_idx,
                "load": load,
                "arrival_min": tmin,
                "arrival_max": tmax,
                "lat": cust.lat,
                "lon": cust.lon
            })

    with open(output_path, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Rotte esportate in: {output_path}")


def export_dropped_nodes_csv(dropped_nodes, output_path="dropped_nodes.csv"):
    if not dropped_nodes:
        print("✅ Nessun nodo scartato da esportare.")
        return

    with open(output_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["dropped_customer_id"])
        for node in dropped_nodes:
            writer.writerow([node])

    print(f"⚠️ Nodi scartati salvati in: {output_path}")
