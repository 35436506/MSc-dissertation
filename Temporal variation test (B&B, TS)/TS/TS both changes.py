import random
import matplotlib.pyplot as plt
import numpy as np
from openpyxl import Workbook

# Set random seed for reproducibility
random.seed(42)

# Define the recipes with their eligibility
recipes_f1_only = list(range(1, 30))
recipes_f1_f2 = list(range(30, 50))
recipes_f2_only = list(range(50, 90))
recipes_f3_only = list(range(90, 101))

# Define total orders and initial factory capacities
total_orders = 10000
initial_F1_cap = 3000
F2_cap = int(0.5 * total_orders)  # 50% of total orders

def get_factory_capacities(day):
    if day >= -6:  # LD7 and onwards
        return {
            'F1': 1000,
            'F2': 6000,
            'F3': float('inf')
        }
    elif day >= -10:  # LD10 to LD8
        return {
            'F1': 1000,
            'F2': F2_cap,
            'F3': float('inf')
        }
    else:  # Before LD10
        return {
            'F1': initial_F1_cap,
            'F2': F2_cap,
            'F3': float('inf')
        }

def generate_order_recipes(eligible_recipes, max_recipes=4):
    return random.sample(eligible_recipes, random.randint(1, min(max_recipes, len(eligible_recipes))))

def generate_orders_for_day(real_proportion, simulated_proportion, existing_real_orders=None):
    orders = []
    f1_f3_target = int(0.3 * total_orders)
    f2_f3_target = int(0.6 * total_orders)
    f1_f2_f3_target = int(0.1 * total_orders)
    
    total_real_orders = int(real_proportion * total_orders)
    
    changed_orders = []
    deleted_orders = []
    
    # Create a set of all available IDs
    available_ids = set(range(1, total_orders + 1))
    
    if existing_real_orders:
        # Delete 5% of real orders
        delete_count = int(0.05 * len(existing_real_orders))
        deleted_orders = random.sample(existing_real_orders, delete_count)
        remaining_orders = [order for order in existing_real_orders if order not in deleted_orders]
        
        # Change 30% of remaining real orders
        change_count = int(0.3 * len(remaining_orders))
        changed_orders = random.sample(remaining_orders, change_count)
        
        for order in remaining_orders:
            if order in changed_orders:
                # Change recipe composition and eligibility
                new_recipes = generate_order_recipes(recipes_f1_only + recipes_f1_f2 + recipes_f2_only + recipes_f3_only)
                new_eligibility = ['F3']  # Always eligible for F3
                if any(r in recipes_f1_only + recipes_f1_f2 for r in new_recipes):
                    new_eligibility.append('F1')
                if any(r in recipes_f1_f2 + recipes_f2_only for r in new_recipes):
                    new_eligibility.append('F2')
                order['recipe_ids'] = new_recipes
                order['eligible_factories'] = new_eligibility
            orders.append(order)
            available_ids.remove(order['id'])
    
    # Generate new orders
    while len(orders) < total_orders:
        if len([o for o in orders if set(o['eligible_factories']) == {'F1', 'F2', 'F3'}]) < f1_f2_f3_target:
            recipe_ids = generate_order_recipes(recipes_f1_f2)
            eligible_factories = ['F1', 'F2', 'F3']
        elif len([o for o in orders if set(o['eligible_factories']) == {'F1', 'F3'}]) < f1_f3_target - f1_f2_f3_target:
            recipe_ids = generate_order_recipes(recipes_f1_only)
            eligible_factories = ['F1', 'F3']
        elif len([o for o in orders if set(o['eligible_factories']) == {'F2', 'F3'}]) < f2_f3_target - f1_f2_f3_target:
            recipe_ids = generate_order_recipes(recipes_f2_only)
            eligible_factories = ['F2', 'F3']
        else:
            f3_recipe = random.choice(recipes_f3_only)
            all_recipes = recipes_f1_only + recipes_f1_f2 + recipes_f2_only + recipes_f3_only
            remaining_recipes = random.sample(all_recipes, min(3, random.randint(0, 3)))
            recipe_ids = [f3_recipe] + remaining_recipes
            random.shuffle(recipe_ids)
            eligible_factories = ['F3']
        
        new_order = {
            'recipe_ids': recipe_ids,
            'eligible_factories': eligible_factories,
            'is_real': len([o for o in orders if o['is_real']]) < total_real_orders
        }
        
        # Assign a new ID from the available IDs
        new_id = available_ids.pop()
        new_order['id'] = new_id
        
        orders.append(new_order)
    
    # Adjust real/simulated order proportions
    real_order_count = sum(1 for order in orders if order['is_real'])
    if real_order_count < total_real_orders:
        for order in random.sample([o for o in orders if not o['is_real']], total_real_orders - real_order_count):
            order['is_real'] = True
    elif real_order_count > total_real_orders:
        for order in random.sample([o for o in orders if o['is_real']], real_order_count - total_real_orders):
            order['is_real'] = False
    
    # Shuffle orders to mix real and simulated orders
    random.shuffle(orders)
    
    return orders, changed_orders, deleted_orders

def get_recipe_counts(allocation, by_factory=False):
    if by_factory:
        recipe_counts = {factory: {} for factory in allocation}
        for factory, orders in allocation.items():
            for order in orders:
                for recipe_id in order['recipe_ids']:
                    recipe_counts[factory][recipe_id] = recipe_counts[factory].get(recipe_id, 0) + 1
    else:
        recipe_counts = {}
        for factory, orders in allocation.items():
            for order in orders:
                for recipe_id in order['recipe_ids']:
                    recipe_counts[recipe_id] = recipe_counts.get(recipe_id, 0) + 1
    return recipe_counts

def calculate_total_abs_diff(recipe_counts_t_minus_1, recipe_counts_t):
    all_recipes = set(recipe_counts_t_minus_1['F1'].keys()) | set(recipe_counts_t_minus_1['F2'].keys()) | set(recipe_counts_t_minus_1['F3'].keys()) | \
                  set(recipe_counts_t['F1'].keys()) | set(recipe_counts_t['F2'].keys()) | set(recipe_counts_t['F3'].keys())
    
    total_abs_diff = 0
    
    for recipe_id in all_recipes:
        for factory in ['F1', 'F2', 'F3']:
            t_minus_1_count = recipe_counts_t_minus_1[factory].get(recipe_id, 0)
            t_count = recipe_counts_t[factory].get(recipe_id, 0)
            total_abs_diff += abs(t_count - t_minus_1_count)
    
    return total_abs_diff

def tabu_search(allocation_t_minus_1, allocation_t, factory_capacities, max_iterations=500):
    current_allocation = {factory: orders[:] for factory, orders in allocation_t.items()}
    recipe_counts_t_minus_1 = get_recipe_counts(allocation_t_minus_1, by_factory=True)
    current_recipe_counts = get_recipe_counts(current_allocation, by_factory=True)
    current_total_abs_diff = calculate_total_abs_diff(recipe_counts_t_minus_1, current_recipe_counts)
    
    best_allocation = current_allocation.copy()
    best_total_abs_diff = current_total_abs_diff
    
    tabu_list = {}
    tabu_tenure = 20
    
    def swap_orders(factory1, order1, factory2, order2):
        current_allocation[factory1].remove(order1)
        current_allocation[factory2].remove(order2)
        current_allocation[factory1].append(order2)
        current_allocation[factory2].append(order1)
        
        for recipe_id in order1['recipe_ids']:
            current_recipe_counts[factory1][recipe_id] -= 1
            current_recipe_counts[factory2][recipe_id] = current_recipe_counts[factory2].get(recipe_id, 0) + 1
        for recipe_id in order2['recipe_ids']:
            current_recipe_counts[factory2][recipe_id] -= 1
            current_recipe_counts[factory1][recipe_id] = current_recipe_counts[factory1].get(recipe_id, 0) + 1
    
    def calculate_move_impact(order1, factory1, order2, factory2):
        diff = 0
        for recipe_id in order1['recipe_ids']:
            diff -= abs(current_recipe_counts[factory1][recipe_id] - recipe_counts_t_minus_1[factory1].get(recipe_id, 0))
            diff -= abs(current_recipe_counts[factory2].get(recipe_id, 0) - recipe_counts_t_minus_1[factory2].get(recipe_id, 0))
            diff += abs(current_recipe_counts[factory1][recipe_id] - 1 - recipe_counts_t_minus_1[factory1].get(recipe_id, 0))
            diff += abs(current_recipe_counts[factory2].get(recipe_id, 0) + 1 - recipe_counts_t_minus_1[factory2].get(recipe_id, 0))
        for recipe_id in order2['recipe_ids']:
            diff -= abs(current_recipe_counts[factory2][recipe_id] - recipe_counts_t_minus_1[factory2].get(recipe_id, 0))
            diff -= abs(current_recipe_counts[factory1].get(recipe_id, 0) - recipe_counts_t_minus_1[factory1].get(recipe_id, 0))
            diff += abs(current_recipe_counts[factory2][recipe_id] - 1 - recipe_counts_t_minus_1[factory2].get(recipe_id, 0))
            diff += abs(current_recipe_counts[factory1].get(recipe_id, 0) + 1 - recipe_counts_t_minus_1[factory1].get(recipe_id, 0))
        return diff
    
    for iteration in range(max_iterations):       
        best_move = None
        best_move_diff = 0
        
        # Randomly select a subset of orders to consider for swapping
        orders_to_consider = random.sample(sum(current_allocation.values(), []), min(100, len(sum(current_allocation.values(), []))))
        
        for order1 in orders_to_consider:
            factory1 = next(f for f, orders in current_allocation.items() if order1 in orders)
            for factory2 in factory_capacities:
                if factory1 != factory2:
                    for order2 in random.sample(current_allocation[factory2], min(10, len(current_allocation[factory2]))):
                        if factory2 in order1['eligible_factories'] and factory1 in order2['eligible_factories']:
                            move = (order1['id'], factory1, order2['id'], factory2)
                            if move not in tabu_list or current_total_abs_diff + calculate_move_impact(order1, factory1, order2, factory2) < best_total_abs_diff:
                                diff = calculate_move_impact(order1, factory1, order2, factory2)
                                if diff < best_move_diff:
                                    best_move = (order1, factory1, order2, factory2)
                                    best_move_diff = diff
        
        if best_move:
            order1, factory1, order2, factory2 = best_move
            swap_orders(factory1, order1, factory2, order2)
            current_total_abs_diff += best_move_diff
            
            if current_total_abs_diff < best_total_abs_diff:
                best_total_abs_diff = current_total_abs_diff
                best_allocation = {f: orders[:] for f, orders in current_allocation.items()}
            
            tabu_list[(order1['id'], factory1, order2['id'], factory2)] = iteration + tabu_tenure
            tabu_list[(order2['id'], factory2, order1['id'], factory1)] = iteration + tabu_tenure
        
        # Remove expired tabu moves
        tabu_list = {k: v for k, v in tabu_list.items() if v > iteration}
        
        # Diversification strategy
        if iteration % 100 == 0:
            factory1, factory2 = random.sample(list(factory_capacities.keys()), 2)
            order1 = random.choice(current_allocation[factory1])
            order2 = random.choice(current_allocation[factory2])
            if factory2 in order1['eligible_factories'] and factory1 in order2['eligible_factories']:
                swap_orders(factory1, order1, factory2, order2)
                current_total_abs_diff += calculate_move_impact(order1, factory1, order2, factory2)
    
    total_items_t = sum(sum(counts.values()) for counts in get_recipe_counts(best_allocation, by_factory=True).values())
    best_wmape_site = best_total_abs_diff / total_items_t if total_items_t > 0 else float('inf')

    return best_allocation, best_wmape_site

def allocate_orders(orders, factory_capacities):
    allocation = {factory: [] for factory in factory_capacities}
    remaining_orders = orders.copy()
    # Allocate to F1 first, prioritizing F1,F3 and F1,F2,F3 orders
    f1_eligible = sorted([order for order in remaining_orders if 'F1' in order['eligible_factories']],
                         key=lambda x: len(x['eligible_factories']))  # Prioritize F1,F3 over F1,F2,F3
    allocation['F1'] = [order for order in f1_eligible[:factory_capacities['F1']]]
    remaining_orders = [order for order in remaining_orders if order not in allocation['F1']]
    # Allocate to F2, using remaining F1,F2,F3 orders and F2,F3 orders
    f2_eligible = [order for order in remaining_orders if 'F2' in order['eligible_factories']]
    allocation['F2'] = [order for order in f2_eligible[:factory_capacities['F2']]]
    remaining_orders = [order for order in remaining_orders if order not in allocation['F2']]
    # Allocate remaining to F3
    allocation['F3'] = remaining_orders
    return allocation

def calculate_wmape_site(orders_t_minus_1, allocation_t_minus_1, orders_t, allocation_t):
    total_abs_diff = 0
    total_items_t = 0
    
    recipe_counts_t_minus_1 = get_recipe_counts(allocation_t_minus_1, by_factory=True)
    recipe_counts_t = get_recipe_counts(allocation_t, by_factory=True)
    
    for factory in ['F1', 'F2', 'F3']:
        for recipe_id in set(recipe_counts_t_minus_1[factory].keys()) | set(recipe_counts_t[factory].keys()):
            t_minus_1_count = recipe_counts_t_minus_1[factory].get(recipe_id, 0)
            t_count = recipe_counts_t[factory].get(recipe_id, 0)
            abs_diff = abs(t_count - t_minus_1_count)
            total_abs_diff += abs_diff
            total_items_t += t_count
    
    if total_items_t == 0:
        wmape_site = float('inf')
    else:
        wmape_site = total_abs_diff / total_items_t
    
    return wmape_site

def calculate_wmape_global(orders_t_minus_1, allocation_t_minus_1, orders_t, allocation_t):
    total_abs_diff = 0
    total_t_items = 0
    recipe_counts_t_minus_1 = {}
    recipe_counts_t = {}
    
    for factory in allocation_t_minus_1:
        for order in allocation_t_minus_1[factory]:
            for recipe_id in order['recipe_ids']:
                recipe_counts_t_minus_1[recipe_id] = recipe_counts_t_minus_1.get(recipe_id, 0) + 1
    
    for factory in allocation_t:
        for order in allocation_t[factory]:
            for recipe_id in order['recipe_ids']:
                recipe_counts_t[recipe_id] = recipe_counts_t.get(recipe_id, 0) + 1
                total_t_items += 1
    
    all_recipes = set(recipe_counts_t_minus_1.keys()) | set(recipe_counts_t.keys())
    
    for recipe_id in all_recipes:
        t_minus_1_count = recipe_counts_t_minus_1.get(recipe_id, 0)
        t_count = recipe_counts_t.get(recipe_id, 0)
        abs_diff = abs(t_minus_1_count - t_count)
        total_abs_diff += abs_diff
    
    if total_t_items == 0:
        wmape_global = float('inf')
    else:
        wmape_global = total_abs_diff / total_t_items
    
    return wmape_global

def calculate_wmape_site_between_allocations(orders_1, allocation_1, orders_2, allocation_2):
    recipe_counts_1 = get_recipe_counts(allocation_1, by_factory=True)
    recipe_counts_2 = get_recipe_counts(allocation_2, by_factory=True)
    
    total_abs_diff = 0
    total_items_2 = 0
    
    for factory in ['F1', 'F2', 'F3']:
        for recipe_id in set(recipe_counts_1[factory].keys()) | set(recipe_counts_2[factory].keys()):
            count_1 = recipe_counts_1[factory].get(recipe_id, 0)
            count_2 = recipe_counts_2[factory].get(recipe_id, 0)
            abs_diff = abs(count_2 - count_1)
            total_abs_diff += abs_diff
            total_items_2 += count_2
    
    if total_items_2 == 0:
        return float('inf')
    else:
        return total_abs_diff / total_items_2

def run_allocation_process_over_time(start_day, end_day, total_orders):
    allocations_ts = {}
    allocations_greedy = {}
    wmape_site_values_ts = []
    wmape_site_values_greedy = []
    wmape_global_values = []
    real_orders_proportions = []
    previous_real_orders = None

    for day in range(start_day, end_day + 1):
        real_proportion = min(1.0, max(0.1, 0.1 + (0.9 / 15) * (18 + day)))
        simulated_proportion = 1 - real_proportion

        orders, changed_orders, deleted_orders = generate_orders_for_day(real_proportion, simulated_proportion, previous_real_orders)
        factory_capacities = get_factory_capacities(day)

        # Create initial allocation using the greedy method
        initial_allocation = allocate_orders(orders, factory_capacities)

        if day > start_day:
            allocation_ts, wmape_site_ts = tabu_search(
                allocations_ts[day-1]['allocation'],
                initial_allocation,
                factory_capacities
            )
            allocation_greedy = initial_allocation

            wmape_site_greedy = calculate_wmape_site(
                allocations_greedy[day-1]['orders'],
                allocations_greedy[day-1]['allocation'],
                orders,
                allocation_greedy
            )

            wmape_global = calculate_wmape_global(
                allocations_ts[day-1]['orders'],
                allocations_ts[day-1]['allocation'],
                orders,
                allocation_ts
            )
            wmape_site_values_ts.append(wmape_site_ts)
            wmape_site_values_greedy.append(wmape_site_greedy)
            wmape_global_values.append(wmape_global)
        else:
            allocation_ts = initial_allocation
            allocation_greedy = initial_allocation

        allocations_ts[day] = {'orders': orders, 'allocation': allocation_ts}
        allocations_greedy[day] = {'orders': orders, 'allocation': allocation_greedy}
        real_orders_proportions.append(len([o for o in orders if o['is_real']]) / total_orders)
        previous_real_orders = [order for order in orders if order['is_real']]

    return allocations_ts, allocations_greedy, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values, real_orders_proportions

def plot_temporal_component(days, real_orders_proportions):
    plt.figure(figsize=(15, 8))
    
    real_orders = []
    simulated_orders = []
    
    for prop in real_orders_proportions:
        total_real = int(prop * total_orders)
        real_orders.append(total_real)
        simulated_orders.append(total_orders - total_real)
    
    x = np.arange(len(days))
    width = 0.7
    
    fig, ax = plt.subplots(figsize=(15, 8))
    ax.bar(x, real_orders, width, label='Real orders', color='blue')
    ax.bar(x, simulated_orders, width, bottom=real_orders, label='Simulated orders', color='orange')
    
    ax.set_xlabel('Days to delivery', fontsize=12)
    ax.set_ylabel('Order quantity', fontsize=12)
    ax.set_title('Composition of total orders through days', fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([str(day) for day in days], fontsize=10)
    ax.tick_params(axis='y', labelsize=10)
    
    ax.set_ylim(0, 1.1 * total_orders)
    
    ax.axvline(x=16, color='purple', linestyle='--', linewidth=1)
    ax.text(16, ax.get_ylim()[1], 'Delivery date', va='bottom', ha='left', color='purple')
    ax.axvline(x=-1, color='purple', linestyle=':', linewidth=1)
    ax.text(-1, ax.get_ylim()[1], 'Menu opens', va='bottom', ha='left', color='purple')
    
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    
    plt.tight_layout()
    plt.show()

def plot_wmape_over_time(days, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values):
    plt.figure(figsize=(12, 6))
    plt.plot(days[1:], wmape_site_values_greedy, label='WMAPE site (Initial)', marker='s')
    plt.plot(days[1:], wmape_site_values_ts, label='WMAPE site (TS)', marker='o')
    plt.plot(days[1:], wmape_global_values, label='WMAPE global', marker='^')
    
    plt.xlabel('Days to delivery')
    plt.ylabel('WMAPE')
    plt.title("WMAPE site and global through days", pad=20, fontsize=14)
    plt.legend()
    plt.grid(True)
    plt.axvline(x=-10, color='red', linestyle='--', linewidth=1)
    plt.text(-10, plt.ylim()[1], 'F1 capacity decreases', ha='right', va='bottom', color='red', rotation=0, fontsize=10)
    plt.axvline(x=-6, color='purple', linestyle='--', linewidth=1)
    plt.text(-6, plt.ylim()[1], 'F2 capacity increases', ha='right', va='bottom', color='purple', rotation=0, fontsize=10)
    plt.tight_layout()
    plt.show()

def plot_factory_allocations(days, allocations_ts):
    plt.figure(figsize=(15, 8))
    
    f1_allocations = []
    f2_allocations = []
    f3_allocations = []
    
    for day in days:
        allocation = allocations_ts[day]['allocation']
        f1_allocations.append(len(allocation['F1']))
        f2_allocations.append(len(allocation['F2']))
        f3_allocations.append(len(allocation['F3']))
    
    plt.plot(days, f1_allocations, label='F1', color='blue', marker='o')
    plt.plot(days, f2_allocations, label='F2', color='orange', marker='s')
    plt.plot(days, f3_allocations, label='F3', color='green', marker='^')
    
    plt.xlabel('Days to delivery', fontsize=12)
    plt.ylabel('Total number of orders', fontsize=12)
    plt.title("Total orders allocated to each factory through days", pad=20, fontsize=14)
    plt.legend(fontsize=10)
    plt.grid(True)
    
    plt.axvline(x=-10, color='red', linestyle='--', linewidth=1)
    plt.text(-10, plt.ylim()[1], 'F1 capacity decreases', ha='right', va='bottom', color='red', rotation=0, fontsize=10)
    
    plt.axvline(x=-6, color='purple', linestyle='--', linewidth=1)
    plt.text(-6, plt.ylim()[1], 'F2 capacity increases', ha='right', va='bottom', color='purple', rotation=0, fontsize=10)
    
    plt.xlim(min(days), max(days))
    plt.xticks(range(min(days), max(days)+1, 2))
    
    plt.tight_layout()
    plt.show()

def plot_wmape_vs_final(days, wmape_site_vs_final_ts, wmape_global_vs_final):
    plt.figure(figsize=(12, 6))
    plt.plot(days, wmape_site_vs_final_ts, label='WMAPE site', marker='o')
    plt.plot(days, wmape_global_vs_final, label='WMAPE global', marker='s')
    plt.xlabel('Days to delivery')
    plt.ylabel('WMAPE')
    plt.title("Comparing each day's allocation with LD3's allocation", pad=20, fontsize=14)
    plt.legend()
    plt.grid(True)
    plt.axvline(x=-10, color='red', linestyle='--', linewidth=1)
    plt.text(-10, plt.ylim()[1], 'F1 capacity decreases', ha='right', va='bottom', color='red', rotation=0, fontsize=10)
    plt.axvline(x=-6, color='purple', linestyle='--', linewidth=1)
    plt.text(-6, plt.ylim()[1], 'F2 capacity increases', ha='right', va='bottom', color='purple', rotation=0, fontsize=10)
    plt.tight_layout()
    plt.show()
    
def calculate_wmape_global_vs_final(allocations, final_day):
    wmape_global_vs_final = []
    for day in allocations.keys():
        wmape = calculate_wmape_global(
            allocations[day]['orders'],
            allocations[day]['allocation'],
            allocations[final_day]['orders'],
            allocations[final_day]['allocation'])
        wmape_global_vs_final.append(wmape)
    return wmape_global_vs_final

def export_to_excel(days, real_orders_proportions, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values, wmape_site_vs_final_ts, wmape_global_vs_final):
    wb = Workbook()
    ws = wb.active
    ws.title = "WMAPE results"

    headers = ["Day", "Real orders proportion", "WMAPE site (TS)", "WMAPE site (Initial)", "WMAPE global", "WMAPE site vs LD3", "WMAPE global vs LD3"]
    ws.append(headers)

    for i, day in enumerate(days):
        row = [
            day,
            real_orders_proportions[i],
            wmape_site_values_ts[i-1] if i > 0 else "N/A",
            wmape_site_values_greedy[i-1] if i > 0 else "N/A",
            wmape_global_values[i-1] if i > 0 else "N/A",
            wmape_site_vs_final_ts[i],
            wmape_global_vs_final[i]
        ]
        ws.append(row)

    wb.save("Both capacity and order change (TS).xlsx")

# Main execution code
start_day = -18
end_day = -3

allocations_ts, allocations_greedy, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values, real_orders_proportions = run_allocation_process_over_time(start_day, end_day, total_orders)

days = list(range(start_day, end_day + 1))

# Plot 1: Temporal component of order allocation
plot_temporal_component(days, real_orders_proportions)

# Plot 2: Factory allocations over time
plot_factory_allocations(days, allocations_ts)

# Plot 3: WMAPE over time
plot_wmape_over_time(days, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values)

# Calculate WMAPE site vs final allocation for TS
final_day = end_day
wmape_site_vs_final_ts = []
for day in range(start_day, end_day + 1):
    wmape_ts = calculate_wmape_site_between_allocations(
        allocations_ts[day]['orders'],
        allocations_ts[day]['allocation'],
        allocations_ts[final_day]['orders'],
        allocations_ts[final_day]['allocation'])
    wmape_site_vs_final_ts.append(wmape_ts)

# Calculate WMAPE global vs final allocation
wmape_global_vs_final = calculate_wmape_global_vs_final(allocations_ts, final_day)

# Plot 4: WMAPE site and global comparison
plot_wmape_vs_final(days, wmape_site_vs_final_ts, wmape_global_vs_final)

# Export results to Excel
export_to_excel(days, real_orders_proportions, wmape_site_values_ts, wmape_site_values_greedy, wmape_global_values, wmape_site_vs_final_ts, wmape_global_vs_final)