import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def discrete_cmap(N, base_cmap='tab10'):
    base = plt.cm.get_cmap(base_cmap)
    color_list = base(np.linspace(0, 1, N))
    return mcolors.ListedColormap(color_list, name=f'{base.name}_{N}')


class RoutePlotter:
    def __init__(self, customers, vehicles):
        self.customers = customers
        self.vehicles = vehicles

        # Recupera pickup/delivery se esistono
        self.pickup_nodes = set()
        self.delivery_nodes = set()
        if hasattr(customers, 'pdp_pairs'):
            for p, d in customers.pdp_pairs:
                self.pickup_nodes.add(p)
                self.delivery_nodes.add(d)

    def plot(self, vehicle_routes, save_path=None, plot_annotations=True):
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_title("Vehicle Routes (PDP)")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True)

        cmap = discrete_cmap(self.vehicles.number + 1)

        for veh_id, route in vehicle_routes.items():
            if not route or len(route) < 2:
                continue

            color = cmap(veh_id % 10)
            lats, lons = zip(*[(c.lat, c.lon) for c in route])
            lats = np.array(lats)
            lons = np.array(lons)

            # Frecce tra i nodi
            ax.quiver(lons[:-1], lats[:-1],
                      np.diff(lons), np.diff(lats),
                      scale_units='xy', angles='xy', scale=1,
                      color=color, width=0.003, alpha=0.8)

            for cust in route:
                shape = 'o'
                msize = 6
                mcolor = color

                if cust.index in self.pickup_nodes:
                    shape = '^'  # triangolo
                    mcolor = 'blue'
                elif cust.index in self.delivery_nodes:
                    shape = 'D'  # diamante
                    mcolor = 'red'

                ax.plot(cust.lon, cust.lat, marker=shape, color=mcolor,
                        markersize=msize, markeredgecolor='black')

                if plot_annotations:
                    label = f"{'P' if cust.index in self.pickup_nodes else 'D' if cust.index in self.delivery_nodes else ''}@{cust.index}"
                    if label:
                        ax.annotate(label,
                                    xy=(cust.lon, cust.lat),
                                    xytext=(5, 5),
                                    textcoords='offset points',
                                    fontsize=7,
                                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", alpha=0.7))

        ax.legend(["Pickup ▲", "Delivery ◆"], loc="upper right", fontsize=8)
        plt.axis('equal')

        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            print(f"✅ Mappa PDP salvata in: {save_path}")
        else:
            plt.show()
