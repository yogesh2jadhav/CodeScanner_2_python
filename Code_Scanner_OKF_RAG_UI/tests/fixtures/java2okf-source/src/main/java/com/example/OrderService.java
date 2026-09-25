package com.example;

import java.util.List;

/**
 * Application service coordinating customers, orders, and storage.
 */
public class OrderService {

    private final OrderRepository repository;
    private int sequence;

    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }

    public Order placeOrder(Customer customer, double amount) {
        if (amount <= 0) {
            throw new IllegalArgumentException("amount must be positive");
        }
        Order order = new Order(nextId(), customer, amount);
        repository.save(order);
        return order;
    }

    public Order pay(String orderId) {
        Order order = repository.findById(orderId)
                .orElseThrow(() -> new IllegalArgumentException("Unknown order " + orderId));
        order.markPaid();
        return order;
    }

    public double totalFor(Customer customer) {
        List<Order> orders = repository.findByCustomer(customer);
        return orders.stream().mapToDouble(Order::getAmount).sum();
    }

    private String nextId() {
        sequence++;
        return "ORD-" + sequence;
    }
}
