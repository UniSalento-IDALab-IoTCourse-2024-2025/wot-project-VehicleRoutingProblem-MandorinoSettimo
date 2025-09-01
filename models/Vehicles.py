from typing import List

import numpy as np
from collections import namedtuple

class Vehicles:


    """
    Classe per creare e gestire i veicoli in un problema CVRPTW o CVRPTW-PDP.

    Ogni veicolo ha:
    - una capacità
    - un costo fisso
    - una velocità media (km/h)

    Supporta flotte eterogenee o omogenee, e genera depot dinamicamente tramite callback.

    Args:
        capacity (int | list | np.ndarray): capacità per veicolo o valore scalare per flotta omogenea
        cost (int | list | np.ndarray): costo fisso per veicolo o valore scalare
        number (int, optional): numero veicoli, necessario solo per flotta omogenea
        speed_kmph (int, optional): velocità media in km/h, default 30
    """

    def __init__(self, capacity=100, cost=100, number=None, speed_kmph=70, ids=None):
        self.speed_kmph = speed_kmph

        Vehicle = namedtuple('Vehicle', ['index', 'capacity', 'cost', 'id'])

        # Determina numero veicoli
        if number is None:
            self.number = np.size(capacity)
        else:
            self.number = number

        idxs = np.arange(self.number)

        # Costruisci capacità
        if np.isscalar(capacity):
            capacities = np.full(self.number, capacity)
        elif np.size(capacity) == self.number:
            capacities = np.array(capacity)
        else:
            raise ValueError("❌ capacity deve essere scalare o array di lunghezza = number")

        # Costruisci costi
        if np.isscalar(cost):
            costs = np.full(self.number, cost)
        elif np.size(cost) == self.number:
            costs = np.array(cost)
        else:
            raise ValueError("❌ cost deve essere scalare o array di lunghezza = number")

        # Prepara IDs reali
        real_ids = ids if ids is not None else [f"vehicle_{i}" for i in idxs]

        # Genera oggetti Vehicle con ID
        self.vehicles = [
            Vehicle(index=int(i), capacity=int(c), cost=int(k), id=real_ids[i])
            for i, c, k in zip(idxs, capacities, costs)
        ]
        self.ids = real_ids

    def get_total_capacity(self):
        return sum(v.capacity for v in self.vehicles)

    def return_starting_callback(self, customers, sameStartFinish=False):
        """Assegna depot start/end dinamici e annulla domanda nei nodi depot."""
        self.starts = [int(customers.central_start_node()) for _ in range(self.number)]
        self.ends = self.starts if sameStartFinish else [
            int(customers.central_start_node(invert=True)) for _ in range(self.number)
        ]

        customers.used_as_depots = list(set(self.starts + self.ends))

        # Ottieni nodi PDP (pickup e delivery) se esistono
        pdp_nodes = set()
        if hasattr(customers, 'pdp_pairs'):
            pdp_nodes = set([idx for pair in customers.pdp_pairs for idx in pair])

        # Azzera solo se il nodo non è coinvolto in una PDP
        for depot in self.starts + self.ends:
            if depot not in pdp_nodes:
                customers.zero_depot_demands(depot)

        def start_return(v):
            return self.starts[v]

        return start_return

    @classmethod
    def from_json(cls, vehicles):
        capacities = [v.capacity for v in vehicles]
        costs = [v.cost for v in vehicles]
        ids = [v.id for v in vehicles]  # tieni traccia dei real ID!
        return cls(capacity=capacities, cost=costs, number=len(vehicles), ids=ids)
