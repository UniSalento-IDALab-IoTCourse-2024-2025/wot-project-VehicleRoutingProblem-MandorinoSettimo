def validate_pdp(customers, vehicles):
    errors = []

    # Verifica depot
    depot_nodes = set(vehicles.starts + vehicles.ends)
    print(f"Depot nodes: {depot_nodes}")

    # Verifica pdp_pairs esistenti
    if not hasattr(customers, 'pdp_pairs'):
        print("⚠️ Nessuna coppia PDP definita.")
        return True, errors

    pdp_pairs = customers.pdp_pairs
    print(f"Totale coppie PDP: {len(pdp_pairs)}")

    # Controlla duplicati e nodi invalidi
    used_nodes = set()
    for i, (pickup, delivery) in enumerate(pdp_pairs):
        if pickup == delivery:
            errors.append(f"Coppia {i}: pickup e delivery uguali ({pickup}).")
        if pickup in depot_nodes:
            errors.append(f"Coppia {i}: pickup {pickup} è un depot.")
        if delivery in depot_nodes:
            errors.append(f"Coppia {i}: delivery {delivery} è un depot.")
        if pickup < 0 or pickup >= customers.number:
            errors.append(f"Coppia {i}: pickup {pickup} fuori range.")
        if delivery < 0 or delivery >= customers.number:
            errors.append(f"Coppia {i}: delivery {delivery} fuori range.")
        # if pickup in used_nodes:
        #     errors.append(f"Coppia {i}: pickup {pickup} già usato in un'altra coppia.")
        # if delivery in used_nodes:
        #     errors.append(f"Coppia {i}: delivery {delivery} già usato in un'altra coppia.")
        used_nodes.add(pickup)
        used_nodes.add(delivery)

        # Controllo finestre temporali (non None)
        c_pickup = customers.customers[pickup]
        c_delivery = customers.customers[delivery]
        if c_pickup.tw_open is None or c_pickup.tw_close is None:
            errors.append(f"Coppia {i}: pickup {pickup} ha finestra temporale nulla.")
        if c_delivery.tw_open is None or c_delivery.tw_close is None:
            errors.append(f"Coppia {i}: delivery {delivery} ha finestra temporale nulla.")

    # Stampa errori o conferma
    if errors:
        print("❌ Errori trovati nella configurazione PDP:")
        for err in errors:
            print("  - " + err)
        return False, errors
    else:
        print("✅ Configurazione PDP valida!")
        return True, errors
