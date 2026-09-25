package com.example;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;

/**
 * In-memory order storage.
 */
public class OrderRepository {

    private final Map<String, Order> orders = new TreeMap<>();

    public void save(Order order) {
        orders.put(order.getId(), order);
    }

    public Optional<Order> findById(String id) {
        return Optional.ofNullable(orders.get(id));
    }

    public List<Order> findByCustomer(Customer customer) {
        List<Order> result = new ArrayList<>();
        for (Order order : orders.values()) {
            if (order.belongsTo(customer)) {
                result.add(order);
            }
        }
        return result;
    }
}
